# MIFA VPN Platform

Модульная платформа-установщик для **Xray (VLESS + Reality)** + **Telegram-бот админа** + **мониторинг (Grafana/Prometheus/Loki/Promtail)**.

> Историческая (pre-platform) версия сохранена в `archive/mifa-vpn-2-legacy`.

---

## Что ставит

### Core
- Xray (systemd)
- VLESS Reality конфиг **на порты**: `443, 8443, 2053, 2083, 50273`
- Access log: `/var/log/xray/access.log`
- State-файл для бота: `/etc/mifa/state.env`

### Monitoring (Docker Compose)
- Grafana (порт `3000`, логин/пароль по умолчанию `admin/admin`)
- Prometheus (порт `9090`)
- Loki (порт `3100`)
- Promtail (читает `/var/log/xray/access.log`)

### Bot
- Telegram бот (systemd) с командами: `/add /list /del /key /restart`
- Конфиги окружения:
  - `/etc/mifa/state.env` (генерируется core)
  - `/etc/mifa/bot.env` (токен/чат айди — заполняешь ты)

---

## Быстрый старт

```bash
sudo ./cmd/install.sh --core
sudo ./cmd/install.sh --monitoring
sudo ./cmd/install.sh --bot
```

или одной командой:

```bash
sudo ./cmd/install.sh --all
```

После установки бота заполни:

```bash
sudo nano /etc/mifa/bot.env
sudo systemctl restart mifa-xray-bot
```

---

## Команды установщика

- `--core` — установить/обновить конфиг Xray
- `--monitoring` — поднять мониторинг через Docker Compose
- `--bot` — поставить Telegram-бота
- `--all` — всё сразу
- `--upgrade` — апгрейд стека (как было в каркасе)
- `--uninstall` — удалить всё (как было в каркасе)

---

## Полезные пути

- Xray config: `/usr/local/etc/xray/config.json`
- Xray logs: `/var/log/xray/access.log`
- Platform state: `/etc/mifa/state.env`
- Bot env: `/etc/mifa/bot.env`
- Monitoring files: `/opt/mifa/monitoring`

---

## Замечания

- Если у тебя домен вместо IP, просто замени `SERVER_IP` в `/etc/mifa/state.env` на домен.
- `DEFAULT_SNI` и `PORTS` для бота тоже лежат в `/etc/mifa/state.env`.
