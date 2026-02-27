#!/usr/bin/env python3
import os
import json
import subprocess
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Load env from systemd EnvironmentFile and optionally local .env
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ALLOWED_CHAT_ID = int(os.getenv('ALLOWED_CHAT_ID', '0'))

CONFIG_PATH = os.getenv('CONFIG_PATH', '/usr/local/etc/xray/config.json')
SERVER_IP = os.getenv('SERVER_IP', '127.0.0.1')
PUBLIC_KEY = os.getenv('PUBLIC_KEY', '')
SHORT_ID = os.getenv('SHORT_ID', '')
DEFAULT_SNI = os.getenv('DEFAULT_SNI', 'www.github.com')

PORTS_ENV = os.getenv('PORTS', '443,8443,2053,2083,50273')
try:
    DEFAULT_PORTS = [int(p.strip()) for p in PORTS_ENV.split(',') if p.strip()]
except Exception:
    DEFAULT_PORTS = [443]

async def is_allowed(update: Update) -> bool:
    user_id = update.effective_user.id
    if ALLOWED_CHAT_ID and user_id != ALLOWED_CHAT_ID:
        await update.message.reply_text("Доступ запрещён")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    await update.message.reply_text(
        "Привет, админ!\n\n"
        "/add Имя — добавить пользователя\n"
        "/list — список всех пользователей\n"
        "/del email — удалить пользователя\n"
        "/key email [порт] — получить ключ\n"
        "/restart — перезапустить Xray\n"
        "/help — это сообщение"
    )


def generate_vless_link(uuid: str, email: str, port: int = 443, sni: str = None) -> str:
    sni = sni or DEFAULT_SNI
    name = email.split('@')[0]
    return (
        f"vless://{uuid}@{SERVER_IP}:{port}"
        f"?security=reality&sni={sni}&fp=chrome&pbk={PUBLIC_KEY}&sid={SHORT_ID}"
        f"&type=tcp&flow=xtls-rprx-vision&encryption=none#{name}-{port}"
    )


async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return

    if not context.args:
        await update.message.reply_text("Использование: /add Имя")
        return

    name = " ".join(context.args)
    email = f"{name.lower().replace(' ', '_')}@myserver.com"

    # Generate UUID
    try:
        uuid = subprocess.check_output(["xray", "uuid"]).decode().strip()
    except Exception:
        uuid = subprocess.check_output(["uuidgen"]).decode().strip()

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    new_client = {"flow": "xtls-rprx-vision", "id": uuid, "email": email}

    # Add client to all vless inbounds
    for inbound in config.get('inbounds', []):
        if inbound.get('protocol') == 'vless':
            inbound.setdefault('settings', {}).setdefault('clients', []).append(new_client)

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    subprocess.run(["sudo", "systemctl", "restart", "xray"], check=False)

    ports = DEFAULT_PORTS
    keys = "\n".join([generate_vless_link(uuid, email, p) for p in ports])

    msg = (
        f"*Пользователь добавлен!*\n\n"
        f"*Имя:* {name}\n"
        f"*Email:* `{email}`\n"
        f"*UUID:* `{uuid}`\n\n"
        f"*Ключи:*\n{keys}"
    )

    await update.message.reply_text(msg, parse_mode='Markdown')


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    clients = []
    for inbound in config.get('inbounds', []):
        if inbound.get('protocol') == 'vless':
            clients = inbound.get('settings', {}).get('clients', [])
            break

    if not clients:
        await update.message.reply_text("Нет пользователей")
        return

    msg = "*Список пользователей:*\n\n"
    for i, c in enumerate(clients, 1):
        msg += f"{i}. *{c.get('email','')}*\n   `{c.get('id','')}`\n"

    await update.message.reply_text(msg, parse_mode='Markdown')


async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return

    if not context.args:
        await update.message.reply_text("Использование: /del email")
        return

    email_to_delete = context.args[0]

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    deleted = False
    for inbound in config.get('inbounds', []):
        if inbound.get('protocol') == 'vless':
            clients = inbound.get('settings', {}).get('clients', [])
            original_len = len(clients)
            inbound['settings']['clients'] = [c for c in clients if c.get('email') != email_to_delete]
            if len(inbound['settings']['clients']) < original_len:
                deleted = True

    if not deleted:
        await update.message.reply_text(f"Пользователь {email_to_delete} не найден")
        return

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    subprocess.run(["sudo", "systemctl", "restart", "xray"], check=False)
    await update.message.reply_text(f"Пользователь {email_to_delete} удалён")


async def get_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return

    if not context.args:
        await update.message.reply_text("Использование: /key email [порт]")
        return

    email = context.args[0]
    port = 443
    if len(context.args) > 1:
        try:
            port = int(context.args[1])
        except Exception:
            pass

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    user = None
    for inbound in config.get('inbounds', []):
        if inbound.get('protocol') == 'vless':
            for c in inbound.get('settings', {}).get('clients', []):
                if c.get('email') == email:
                    user = c
                    break
            break

    if not user:
        await update.message.reply_text(f"Пользователь {email} не найден")
        return

    key = generate_vless_link(user['id'], user['email'], port)
    await update.message.reply_text(
        f"*Ключ для {email} на порт {port}:*\n\n`{key}`",
        parse_mode='Markdown'
    )


async def restart_xray(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return

    await update.message.reply_text("Перезапускаю Xray...")
    result = subprocess.run(["sudo", "systemctl", "restart", "xray"], capture_output=True)

    if result.returncode == 0:
        await update.message.reply_text("Xray успешно перезапущен")
    else:
        await update.message.reply_text(f"Ошибка: {result.stderr.decode(errors='ignore')}")


def main():
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
    app.add_handler(CommandHandler("restart", restart_xray))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
