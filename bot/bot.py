#!/usr/bin/env python3
"""MIFA Xray Telegram Admin Bot

Designed for the MIFA platform layout.

Env sources (systemd EnvironmentFile):
  - /etc/mifa/state.env: CONFIG_PATH/SERVER_IP/PUBLIC_KEY/SHORT_ID/DEFAULT_SNI/PORTS
  - /etc/mifa/bot.env:   BOT_TOKEN (+ access control)

Access control (recommended):
  - ADMIN_IDS: comma-separated Telegram *user* IDs
Optional:
  - ALLOWED_CHAT_ID: allow commands only from this chat/group id

Notes:
  - Applies config changes safely: backup -> write -> xray -test -> restart -> rollback on failure.
  - Adds/removes clients across ALL protocol=vless inbounds (fits multi-port template).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from dotenv import load_dotenv

    load_dotenv()  # optional local .env for dev
except Exception:
    pass

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


# ---- env ----

BOT_TOKEN = os.getenv("BOT_TOKEN")

ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", "0"))
_admins_raw = (os.getenv("ADMIN_IDS") or "").strip()
ADMIN_IDS: Set[int] = set()
if _admins_raw:
    for x in _admins_raw.split(","):
        x = x.strip()
        if x.isdigit():
            ADMIN_IDS.add(int(x))

CONFIG_PATH = os.getenv("XRAY_CONFIG") or os.getenv("CONFIG_PATH") or "/usr/local/etc/xray/config.json"
XRAY_SERVICE = os.getenv("XRAY_SERVICE", "xray")

SERVER_HOST = os.getenv("SERVER_HOST") or os.getenv("SERVER_IP") or "127.0.0.1"
PUBLIC_KEY = os.getenv("PUBLIC_KEY", "")
SHORT_ID = os.getenv("SHORT_ID", "")
DEFAULT_SNI = os.getenv("DEFAULT_SNI", "www.github.com")
EMAIL_DOMAIN = os.getenv("EMAIL_DOMAIN", "myserver.com")


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


DEFAULT_PORTS = _parse_ports(os.getenv("PORTS", "443,8443,2053,2083,50273"))


# ---- helpers ----

def run(cmd: List[str]) -> Tuple[int, str]:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, (p.stdout or "").strip()


def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(p.parent), encoding="utf-8") as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        tf.flush()
        os.fsync(tf.fileno())
        tmp_name = tf.name
    os.replace(tmp_name, path)


def xray_test_config() -> Tuple[bool, str]:
    rc, out = run(["xray", "run", "-test", "-config", CONFIG_PATH])
    if rc == 0:
        return True, (out or "OK")
    return False, (out or "Xray config test failed")


def restart_xray() -> Tuple[bool, str]:
    rc, out = run(["systemctl", "restart", XRAY_SERVICE])
    return (rc == 0), (out or "")


def get_status_xray() -> str:
    rc, out = run(["systemctl", "is-active", XRAY_SERVICE])
    return out if rc == 0 else (out or "unknown")


def find_vless_inbounds(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    res: List[Dict[str, Any]] = []
    for ib in cfg.get("inbounds", []) or []:
        if ib.get("protocol") == "vless":
            res.append(ib)
    return res


def extract_reality_from_any_inbound(cfg: Dict[str, Any]) -> Dict[str, str]:
    """Fallback to pull SHORT_ID / SNI / public key from config.json if env is missing."""
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
                else:
                    m2 = re.search(r"PublicKey:\s*([A-Za-z0-9+/=_-]+)", out)
                    if m2:
                        pub = m2.group(1)

        return {"short_id": short_id, "sni": sni, "public_key": pub}

    return {"short_id": "", "sni": "", "public_key": ""}


def normalize_name(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-zA-Z0-9_\-.@]", "", s)
    return s[:64]


def make_email_from_name(name_or_email: str) -> str:
    n = normalize_name(name_or_email).lower()
    if "@" in n:
        return n
    return f"{n}@{EMAIL_DOMAIN}"


def find_client(clients: List[Dict[str, Any]], email: str) -> Optional[Dict[str, Any]]:
    email_l = email.lower()
    for c in clients:
        if (c.get("email") or "").lower() == email_l:
            return c
    return None


def apply_config_safely(new_cfg: Dict[str, Any]) -> Tuple[bool, str]:
    """Write config.json, test it, restart xray; rollback on failure."""
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
                restart_xray()  # best-effort restore
        except Exception:
            pass
        return False, f"Xray restart failed, rolled back. Output:\n{restart_out}"

    return True, (test_out or "OK")


def generate_vless_link(uid: str, email: str, port: int, sni: str, pbk: str, sid: str) -> str:
    name = (email.split("@")[0] if email else "user")
    return (
        f"vless://{uid}@{SERVER_HOST}:{port}"
        f"?security=reality&sni={sni}&fp=chrome&pbk={pbk}&sid={sid}"
        f"&type=tcp&flow=xtls-rprx-vision&encryption=none#{name}-{port}"
    )


async def is_allowed(update: Update) -> bool:
    user_id = update.effective_user.id if update.effective_user else 0
    chat_id = update.effective_chat.id if update.effective_chat else 0

    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔️ Нет доступа")
        return False

    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        await update.message.reply_text("⛔️ Нет доступа")
        return False

    return True


# ---- commands ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    await update.message.reply_text(
        "MIFA Xray Bot ✅\n\n"
        "Команды:\n"
        "/add <name|email> — добавить пользователя\n"
        "/list — список пользователей\n"
        "/del <email> — удалить пользователя\n"
        "/key <email> [port] — ключ (без port: для всех портов)\n"
        "/info — параметры Reality (без секретов)\n"
        "/restart — перезапустить Xray\n"
        "/status — статус Xray\n"
        "/help — это сообщение"
    )


async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    if not context.args:
        await update.message.reply_text("Использование: /add <name|email>")
        return

    raw = " ".join(context.args)
    email = make_email_from_name(raw)

    # UUID generation
    new_uuid = str(uuid.uuid4())
    rc, out = run(["xray", "uuid"])
    if rc == 0 and out:
        new_uuid = out.splitlines()[0].strip()

    cfg = load_config()
    vless_inbounds = find_vless_inbounds(cfg)
    if not vless_inbounds:
        await update.message.reply_text("В config.json не найден inbound protocol=vless")
        return

    first_clients = vless_inbounds[0].setdefault("settings", {}).setdefault("clients", [])
    if find_client(first_clients, email):
        await update.message.reply_text(f"Уже есть: {email}")
        return

    new_client = {"flow": "xtls-rprx-vision", "id": new_uuid, "email": email}
    for ib in vless_inbounds:
        ib.setdefault("settings", {}).setdefault("clients", []).append(dict(new_client))

    ok, apply_out = apply_config_safely(cfg)
    if not ok:
        await update.message.reply_text(f"❌ Не применилось:\n{apply_out}")
        return

    # fill missing link params from config.json if env is missing
    global PUBLIC_KEY, SHORT_ID, DEFAULT_SNI
    if not (PUBLIC_KEY and SHORT_ID):
        fb = extract_reality_from_any_inbound(cfg)
        PUBLIC_KEY = PUBLIC_KEY or fb.get("public_key", "")
        SHORT_ID = SHORT_ID or fb.get("short_id", "")
        DEFAULT_SNI = DEFAULT_SNI or fb.get("sni", "")

    if not (PUBLIC_KEY and SHORT_ID):
        await update.message.reply_text(
            f"✅ Добавлен: {email}\nUUID: {new_uuid}\n"
            "Но PUBLIC_KEY/SHORT_ID не заданы (проверь /etc/mifa/state.env)."
        )
        return

    keys = "\n".join(
        [generate_vless_link(new_uuid, email, p, DEFAULT_SNI, PUBLIC_KEY, SHORT_ID) for p in DEFAULT_PORTS]
    )

    msg = (
        f"*Пользователь добавлен!*\n\n"
        f"*Email:* `{email}`\n"
        f"*UUID:* `{new_uuid}`\n"
        f"*Xray:* `{get_status_xray()}`\n\n"
        f"*Ключи:*\n{keys}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    cfg = load_config()
    vless_inbounds = find_vless_inbounds(cfg)
    if not vless_inbounds:
        await update.message.reply_text("Нет inbound vless")
        return

    clients = (vless_inbounds[0].get("settings", {}) or {}).get("clients", []) or []
    if not clients:
        await update.message.reply_text("Нет пользователей")
        return

    msg = "*Список пользователей:*\n\n"
    for i, c in enumerate(clients, 1):
        msg += f"{i}. *{c.get('email','')}*\n   `{c.get('id','')}`\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    if not context.args:
        await update.message.reply_text("Использование: /del <email>")
        return

    email = normalize_name(context.args[0]).lower()
    cfg = load_config()
    vless_inbounds = find_vless_inbounds(cfg)
    if not vless_inbounds:
        await update.message.reply_text("Нет inbound vless")
        return

    deleted = False
    for ib in vless_inbounds:
        settings = ib.setdefault("settings", {})
        clients = settings.get("clients", []) or []
        before = len(clients)
        settings["clients"] = [c for c in clients if (c.get("email") or "").lower() != email]
        if len(settings["clients"]) < before:
            deleted = True

    if not deleted:
        await update.message.reply_text(f"Пользователь {email} не найден")
        return

    ok, apply_out = apply_config_safely(cfg)
    if not ok:
        await update.message.reply_text(f"❌ Не применилось:\n{apply_out}")
        return

    await update.message.reply_text(f"✅ Пользователь {email} удалён. Xray: {get_status_xray()}")


async def get_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    if not context.args:
        await update.message.reply_text("Использование: /key <email> [port]")
        return

    email = normalize_name(context.args[0]).lower()
    port: Optional[int] = None
    if len(context.args) > 1:
        try:
            port = int(context.args[1])
        except Exception:
            port = None

    cfg = load_config()
    vless_inbounds = find_vless_inbounds(cfg)
    if not vless_inbounds:
        await update.message.reply_text("Нет inbound vless")
        return

    user = None
    for c in (vless_inbounds[0].get("settings", {}) or {}).get("clients", []) or []:
        if (c.get("email") or "").lower() == email:
            user = c
            break
    if not user:
        await update.message.reply_text(f"Пользователь {email} не найден")
        return

    global PUBLIC_KEY, SHORT_ID, DEFAULT_SNI
    if not (PUBLIC_KEY and SHORT_ID):
        fb = extract_reality_from_any_inbound(cfg)
        PUBLIC_KEY = PUBLIC_KEY or fb.get("public_key", "")
        SHORT_ID = SHORT_ID or fb.get("short_id", "")
        DEFAULT_SNI = DEFAULT_SNI or fb.get("sni", "")

    if not (PUBLIC_KEY and SHORT_ID):
        await update.message.reply_text("PUBLIC_KEY/SHORT_ID не заданы (проверь /etc/mifa/state.env)")
        return

    ports = [port] if port else DEFAULT_PORTS
    keys = "\n".join(
        [generate_vless_link(user["id"], user["email"], p, DEFAULT_SNI, PUBLIC_KEY, SHORT_ID) for p in ports]
    )
    title = f"*Ключи для {email}:*" if not port else f"*Ключ для {email} на порт {port}:*"
    await update.message.reply_text(f"{title}\n\n{keys}", parse_mode="Markdown")


async def restart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    await update.message.reply_text("Перезапускаю Xray...")
    ok, out = restart_xray()
    if ok:
        await update.message.reply_text(f"Xray: {get_status_xray()}")
    else:
        await update.message.reply_text(f"Ошибка рестарта:\n{out}")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    await update.message.reply_text(f"Xray: {get_status_xray()}")


async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    cfg = load_config()
    fb = extract_reality_from_any_inbound(cfg)
    sni = DEFAULT_SNI or fb.get("sni", "")
    sid = SHORT_ID or fb.get("short_id", "")
    pbk = PUBLIC_KEY or fb.get("public_key", "")
    await update.message.reply_text(
        "Reality params:\n"
        f"host: {SERVER_HOST}\n"
        f"sni: {sni}\n"
        f"shortId: {sid}\n"
        f"publicKey: {pbk}\n"
        f"ports: {','.join(str(p) for p in DEFAULT_PORTS)}"
    )


def main() -> None:
    if not BOT_TOKEN:
        print("BOT_TOKEN не найден (проверь /etc/mifa/bot.env)")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("list", list_users))
    app.add_handler(CommandHandler("del", delete_user))
    app.add_handler(CommandHandler("key", get_key))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("restart", restart_cmd))
    app.add_handler(CommandHandler("status", status_cmd))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
