#!/usr/bin/env python3
"""MIFA Xray Telegram Admin Bot (MIFA platform)

Env (systemd EnvironmentFile):
  - /etc/mifa/state.env: XRAY_CONFIG/SERVER_HOST/PUBLIC_KEY/SHORT_ID/DEFAULT_SNI/PORTS
  - /etc/mifa/bot.env:   BOT_TOKEN + ADMIN_IDS (+ optional ALLOWED_CHAT_ID)

Access control:
  - ADMIN_IDS: comma-separated Telegram user IDs
  - ALLOWED_CHAT_ID (optional): restrict to a chat/group id

Safety:
  - drop_pending_updates=True (no backlog execution after restart)
  - safe apply: backup -> write -> xray -test -> restart -> rollback on failure
  - any exception -> ❌ error message in Telegram + traceback in journalctl
"""

import json
import os
import re
import subprocess
import tempfile
import pwd
import grp
import traceback
import uuid
from io import BytesIO
import qrcode
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import logging

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.INFO)

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


# ---------- safe wrappers ----------

async def safe_reply(update: Update, text: str, **kwargs):
    try:
        if update and update.message:
            await update.message.reply_text(text, **kwargs)
    except Exception:
        pass


async def run_safe(update: Update, func):
    try:
        return await func()
    except Exception as e:
        traceback.print_exc()
        await safe_reply(update, f"❌ Ошибка: {e}")


# ---------- env ----------

BOT_TOKEN = os.getenv("BOT_TOKEN")

ALLOWED_CHAT_ID = int((os.getenv("ALLOWED_CHAT_ID") or "0").strip() or "0")

_admins_raw = (os.getenv("ADMIN_IDS") or "").strip()
ADMIN_IDS: Set[int] = set()
if _admins_raw:
    for x in _admins_raw.split(","):
        x = x.strip()
        if x.isdigit():
            ADMIN_IDS.add(int(x))

CONFIG_PATH = os.getenv("XRAY_CONFIG") or os.getenv("CONFIG_PATH") or "/usr/local/etc/xray/config.json"
CFG_OWNER = os.getenv("XRAY_CFG_OWNER", "xray")
CFG_GROUP = os.getenv("XRAY_CFG_GROUP", "xray")
CFG_MODE = int(os.getenv("XRAY_CFG_MODE", "640"), 8)
XRAY_SERVICE = os.getenv("XRAY_SERVICE", "xray")

SERVER_HOST = os.getenv("SERVER_HOST") or os.getenv("SERVER_IP") or "127.0.0.1"
PUBLIC_KEY = os.getenv("PUBLIC_KEY", "")
SHORT_ID = os.getenv("SHORT_ID", "")
DEFAULT_SNI = os.getenv("DEFAULT_SNI", "www.github.com")


def _parse_ports(s: str) -> List[int]:
    out: List[int] = []
    for p in (s or "").split(","):
        p = p.strip()
        if not p:
            continue
        try:
            out.append(int(p))
        except Exception:
            continue
    return out or [443]


DEFAULT_PORTS = _parse_ports(os.getenv("PORTS", "8443,50273"))


# ---------- helpers ----------

def run(cmd: List[str]) -> Tuple[int, str]:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, (p.stdout or "").strip()


def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    uid = pwd.getpwnam(CFG_OWNER).pw_uid
    gid = grp.getgrnam(CFG_GROUP).gr_gid

    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(p.parent), encoding="utf-8") as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        tf.flush()
        os.fsync(tf.fileno())
        tmp_name = tf.name

    # закрепляем права/владельца на tmp (чтобы replace не “утащил” 0600)
    try:
        os.chown(tmp_name, uid, gid)
    except PermissionError:
        pass

    os.chmod(tmp_name, CFG_MODE)

    os.replace(tmp_name, path)

    # и на целевом тоже (на всякий)
    try:
        os.chown(path, uid, gid)
    except PermissionError:
        pass

    os.chmod(path, CFG_MODE)

def xray_test_config() -> Tuple[bool, str]:
    rc, out = run(["xray", "run", "-test", "-config", CONFIG_PATH])
    if rc == 0:
        return True, (out or "OK")
    return False, (out or "Xray config test failed")


def restart_xray() -> Tuple[bool, str]:
    rc, out = run(["/bin/systemctl", "start", "mifa-xray-restart.service"])
    return (rc == 0), (out or "")


def get_status_xray() -> str:
    rc, out = run(["/bin/systemctl", "is-active", "xray"])
    return out if rc == 0 else (out or "unknown")


def find_vless_inbounds(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [ib for ib in (cfg.get("inbounds", []) or []) if ib.get("protocol") == "vless"]

def extract_reality_from_any_inbound(cfg: Dict[str, Any]) -> Dict[str, str]:
    for ib in cfg.get("inbounds", []) or []:
        ss = ib.get("streamSettings", {}) or {}
        if ss.get("security") != "reality":
            continue
        rs = ss.get("realitySettings", {}) or {}

        short_id = ""
        short_ids = rs.get("shortIds", []) or []
        if short_ids:
            short_id = short_ids[0]

        sni = ""
        server_names = rs.get("serverNames", []) or []
        if server_names:
            sni = server_names[0]

        priv = rs.get("privateKey")
        pub = ""
        if priv:
            rc, out = run(["xray", "x25519", "-i", priv])
            if rc == 0:
                m = re.search(r"Public\s*key:\s*([A-Za-z0-9+/=_-]+)", out)
                if m:
                    pub = m.group(1)

        return {"short_id": short_id, "sni": sni, "public_key": pub}

    return {"short_id": "", "sni": "", "public_key": ""}


def normalize_alias(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-zA-Z0-9_\-.@]", "", s)
    return s[:64].lower()


def find_client(clients: List[Dict[str, Any]], label: str) -> Optional[Dict[str, Any]]:
    label_l = label.lower()
    for c in clients:
        if (c.get("email") or "").lower() == label_l:
            return c
    return None


def apply_config_safely(new_cfg: Dict[str, Any]) -> Tuple[bool, str]:
    cfg_path = Path(CONFIG_PATH)
    backup_path = cfg_path.with_suffix(cfg_path.suffix + ".bak")

    try:
        if cfg_path.exists():
            backup_path.write_bytes(cfg_path.read_bytes())
    except Exception as e:
        return False, f"Backup failed: {e}"

    try:
        atomic_write_json(str(cfg_path), new_cfg)
    except Exception as e:
        try:
            if backup_path.exists():
                cfg_path.write_bytes(backup_path.read_bytes())
        except Exception:
            pass
        return False, f"Write failed: {e}"

    ok, test_out = xray_test_config()
    if not ok:
        try:
            if backup_path.exists():
                cfg_path.write_bytes(backup_path.read_bytes())
        except Exception:
            pass
        return False, f"Config test failed, rolled back. Output:\n{test_out}"

    ok2, restart_out = restart_xray()
    if not ok2:
        try:
            if backup_path.exists():
                cfg_path.write_bytes(backup_path.read_bytes())
                restart_xray()
        except Exception:
            pass
        return False, f"Xray restart failed, rolled back. Output:\n{restart_out}"

    return True, (test_out or "OK")


def generate_vless_link(uid: str, alias: str, port: int, sni: str, pbk: str, sid: str) -> str:
    name = alias or "user"
    return (
        f"vless://{uid}@{SERVER_HOST}:{port}"
        f"?security=reality&sni={sni}&fp=chrome&pbk={pbk}&sid={sid}"
        f"&type=tcp&flow=xtls-rprx-vision&encryption=none#{name}-{port}"
    )


async def is_allowed(update: Update) -> bool:
    user_id = update.effective_user.id if update.effective_user else 0
    chat_id = update.effective_chat.id if update.effective_chat else 0

    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await safe_reply(update, "⛔️ Нет доступа")
        return False

    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        await safe_reply(update, "⛔️ Нет доступа")
        return False

    return True


# ---------- commands ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    await safe_reply(
        update,
        "MIFA Xray Bot ✅\n\n"
        "Команды:\n"
        "/add <alias> — добавить пользователя\n"
        "/list — список пользователей\n"
        "/del <alias> — удалить пользователя\n"
        "/key <alias> [port|all] — ключ (без port: для всех портов)\n"
        "/info — параметры Reality (без секретов)\n"
        "/restart — перезапустить Xray\n"
        "/status — статус Xray\n"
        "/help — это сообщение",
    )


async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def inner():
        if not await is_allowed(update):
            return
        if not context.args:
            await safe_reply(update, "Использование: /add <alias>")
            return

        alias = normalize_alias(" ".join(context.args))

        # uuid
        new_uuid = str(uuid.uuid4())
        rc, out = run(["xray", "uuid"])
        if rc == 0 and out:
            new_uuid = out.splitlines()[0].strip()

        # load config (handle broken json)
        try:
            cfg = load_config()
        except Exception as e:
            raise RuntimeError(f"config.json невалиден/не читается: {e}")

        vless_inbounds = find_vless_inbounds(cfg)
        if not vless_inbounds:
            await safe_reply(update, "В config.json не найден inbound protocol=vless")
            return

        first_clients = vless_inbounds[0].setdefault("settings", {}).setdefault("clients", [])
        if find_client(first_clients, alias):
            await safe_reply(update, f"Уже есть: {alias}")
            return

        new_client = {"flow": "xtls-rprx-vision", "id": new_uuid, "email": alias}
        for ib in vless_inbounds:
            ib.setdefault("settings", {}).setdefault("clients", []).append(dict(new_client))

        ok, apply_out = apply_config_safely(cfg)
        if not ok:
            await safe_reply(update, f"❌ Не применилось:\n{apply_out}")
            return

        # fill missing link params from config if env missing
        global PUBLIC_KEY, SHORT_ID, DEFAULT_SNI
        if not (PUBLIC_KEY and SHORT_ID):
            fb = extract_reality_from_any_inbound(cfg)
            PUBLIC_KEY = PUBLIC_KEY or fb.get("public_key", "")
            SHORT_ID = SHORT_ID or fb.get("short_id", "")
            DEFAULT_SNI = DEFAULT_SNI or fb.get("sni", "")

        keys = ""
        if PUBLIC_KEY and SHORT_ID:
            keys = "\n".join(
                [generate_vless_link(new_uuid, alias, p, DEFAULT_SNI, PUBLIC_KEY, SHORT_ID) for p in DEFAULT_PORTS]
            )

        msg = (
            f"*Пользователь добавлен!*\n\n"
            f"*Alias:* `{alias}`\n"
            f"*UUID:* `{new_uuid}`\n"
            f"*Xray:* `{get_status_xray()}`\n\n"
        )
        if keys:
            msg += f"*Ключи:*\n{keys}"
        else:
            msg += "⚠️ PUBLIC_KEY/SHORT_ID не заданы (проверь /etc/mifa/state.env или realitySettings)."

        await safe_reply(update, msg, parse_mode="Markdown")

    await run_safe(update, inner)


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def inner():
        if not await is_allowed(update):
            return
        cfg = load_config()
        vless_inbounds = find_vless_inbounds(cfg)
        if not vless_inbounds:
            await safe_reply(update, "Нет inbound vless")
            return

        clients = (vless_inbounds[0].get("settings", {}) or {}).get("clients", []) or []
        if not clients:
            await safe_reply(update, "Нет пользователей")
            return

        msg = "*Список пользователей:*\n\n"
        for i, c in enumerate(clients, 1):
            msg += f"{i}. *{c.get('email','')}*\n   `{c.get('id','')}`\n"
        await safe_reply(update, msg, parse_mode="Markdown")

    await run_safe(update, inner)


async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def inner():
        if not await is_allowed(update):
            return
        if not context.args:
            await safe_reply(update, "Использование: /del <alias>")
            return

        alias = normalize_alias(context.args[0])

        cfg = load_config()
        vless_inbounds = find_vless_inbounds(cfg)
        if not vless_inbounds:
            await safe_reply(update, "Нет inbound vless")
            return

        deleted = False
        for ib in vless_inbounds:
            settings = ib.setdefault("settings", {})
            clients = settings.get("clients", []) or []
            before = len(clients)
            settings["clients"] = [c for c in clients if (c.get("email") or "").lower() != alias]
            if len(settings["clients"]) < before:
                deleted = True

        if not deleted:
            await safe_reply(update, f"Пользователь {alias} не найден")
            return

        ok, apply_out = apply_config_safely(cfg)
        if not ok:
            await safe_reply(update, f"❌ Не применилось:\n{apply_out}")
            return

        await safe_reply(update, f"✅ Пользователь {alias} удалён. Xray: {get_status_xray()}")

    await run_safe(update, inner)


async def get_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def inner():
        if not await is_allowed(update):
            return

        if not context.args:
            await safe_reply(update, "Использование: /key <alias> [port]")
            return

        alias = normalize_alias(context.args[0])

        port: Optional[int] = None
        if len(context.args) > 1:
            try:
                port = int(context.args[1])
            except Exception:
                port = None

        cfg = load_config()
        vless_inbounds = find_vless_inbounds(cfg)
        if not vless_inbounds:
            await safe_reply(update, "Нет inbound vless")
            return

        user = None
        for c in (vless_inbounds[0].get("settings", {}) or {}).get("clients", []) or []:
            if (c.get("email") or "").lower() == alias:
                user = c
                break

        if not user:
            await safe_reply(update, f"Пользователь {alias} не найден")
            return

        global PUBLIC_KEY, SHORT_ID, DEFAULT_SNI
        if not (PUBLIC_KEY and SHORT_ID):
            fb = extract_reality_from_any_inbound(cfg)
            PUBLIC_KEY = PUBLIC_KEY or fb.get("public_key", "")
            SHORT_ID = SHORT_ID or fb.get("short_id", "")
            DEFAULT_SNI = DEFAULT_SNI or fb.get("sni", "")

        if not (PUBLIC_KEY and SHORT_ID):
            await safe_reply(
                update,
                "PUBLIC_KEY/SHORT_ID не заданы (проверь /etc/mifa/state.env или realitySettings)"
            )
            return

        port_arg = context.args[1].strip().lower() if len(context.args) > 1 else ""
        if port_arg == "all":
            ports = DEFAULT_PORTS
        elif port_arg:
            try:
                ports = [int(port_arg)]
            except Exception:
                await safe_reply(update, "Порт должен быть числом, например: /key test10 8443 (или /key test10 all)")
                return
        else:
            # без указания порта — выдаём все доступные порты (обычно 8443 и 50273)
            ports = DEFAULT_PORTS

        keys = "\n".join(
            [
                generate_vless_link(
                    user["id"],
                    user["email"],
                    p,
                    DEFAULT_SNI,
                    PUBLIC_KEY,
                    SHORT_ID
                )
                for p in ports
            ]
        )

        # ---- QR отправка ----
        for p in ports:
            link = generate_vless_link(
                user["id"],
                user["email"],
                p,
                DEFAULT_SNI,
                PUBLIC_KEY,
                SHORT_ID
            )

            img = qrcode.make(link)
            bio = BytesIO()
            img.save(bio, format="PNG")
            bio.seek(0)

            try:
                await update.message.reply_photo(photo=bio, caption=f"{alias}-{p}")
            except Exception:
                pass

        # ---- Текстовый вывод ----
        title = f"Ключи для {alias}:"
        await safe_reply(update, f"{title}\n\n```\n{keys}\n```", parse_mode="Markdown")

    await run_safe(update, inner)

async def restart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def inner():
        if not await is_allowed(update):
            return
        await safe_reply(update, "Перезапускаю Xray...")
        ok, out = restart_xray()
        if ok:
            await safe_reply(update, f"Xray: {get_status_xray()}")
        else:
            await safe_reply(update, f"Ошибка рестарта:\n{out}")

    await run_safe(update, inner)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    await safe_reply(update, f"Xray: {get_status_xray()}")


async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async def inner():
        if not await is_allowed(update):
            return
        cfg = load_config()
        fb = extract_reality_from_any_inbound(cfg)
        sni = DEFAULT_SNI or fb.get("sni", "")
        sid = SHORT_ID or fb.get("short_id", "")
        pbk = PUBLIC_KEY or fb.get("public_key", "")
        await safe_reply(
            update,
            "Reality params:\n"
            f"host: {SERVER_HOST}\n"
            f"sni: {sni}\n"
            f"shortId: {sid}\n"
            f"publicKey: {pbk}\n"
            f"ports: {','.join(str(p) for p in DEFAULT_PORTS)}",
        )

    await run_safe(update, inner)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled bot exception", exc_info=context.error)

def build_app() -> Application:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(10)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(10)
        .build()
    )

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("list", list_users))
    app.add_handler(CommandHandler("del", delete_user))
    app.add_handler(CommandHandler("key", get_key))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("restart", restart_cmd))
    app.add_handler(CommandHandler("status", status_cmd))

    return app

def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не найден (проверь /etc/mifa/bot.env)")
        return

    app = build_app()
    logger.info("Бот запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
