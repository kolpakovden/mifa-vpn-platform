# MIFA VPN Platform

Production-ready self-hosted VPN platform built on Xray (VLESS + Reality)
with integrated Telegram user management and full observability stack.

> Историческая (pre-platform) версия  в `[archive/mifa-vpn-2-legacy](https://github.com/kolpakovden/mifa-vpn-legacy)`.

---

## Features

- Xray Core (VLESS + Reality)
- Multi-port configuration (443, 8443, 2053, 2083, 50273)
- Telegram bot for user management
- Monitoring stack (Grafana + Prometheus + Loki + Promtail)
- Centralized state management
- Fully containerized monitoring via Docker Compose
- Idempotent installer (safe re-run)
  
---

## Architecture
Core Components
1. Xray (Traffic Engine)
  Xray-core powers the VPN layer using:
  VLESS protocol
  Reality TLS obfuscation
  Multi-port inbounds
  Structured access logging
  Reality provides TLS camouflage without requiring certificates.

2. Telegram Bot (Control Layer)
  Built using:
  python-telegram-bot
Capabilities:
```
/add <user>
/del <user>
/list
/key <user>
/restart
```
Bot communicates directly with Xray config and reloads service safely.
Runs as:
```
systemd service: mifa-xray-bot
```
3. Observability Stack (Monitoring)
Fully containerized:
  Grafana
  Prometheus
  Loki
  Promtail
All deployed via Docker Compose.

---

## Project Structure

```
mifa-vpn-platform/
│
├── cmd/
│   └── install.sh
│
├── internal/
│   ├── core.sh
│   ├── bot.sh
│   └── monitoring.sh
│
├── core/
│   └── templates/
│
├── monitoring/
│   ├── docker-compose.yml
│   ├── loki-config.yaml
│   ├── promtail-config.yaml
│   └── dashboards/
│
├── bot/
│   ├── bot.py
│   └── systemd/
│
└── archive/
    └── mifa-vpn-2-legacy/
```

---

## Installation
Install everything: 
```
sudo ./cmd/install.sh --all
```
Or modular:
```
sudo ./cmd/install.sh --core
sudo ./cmd/install.sh --monitoring
sudo ./cmd/install.sh --bot
```

---

## Configuration Files
```
| File                              | Purpose                  |
| --------------------------------- | ------------------------ |
| `/usr/local/etc/xray/config.json` | Xray config              |
| `/etc/mifa/state.env`             | Generated platform state |
| `/etc/mifa/bot.env`               | Telegram bot credentials |
| `/var/log/xray/access.log`        | Traffic logs             |
```

---

## Access
```
| Service    | URL                     |
| ---------- | ----------------------- |
| Grafana    | `http://SERVER_IP:3000` |
| Prometheus | `http://SERVER_IP:9090` |
| Loki       | `http://SERVER_IP:3100` |
```
Default Grafana: 
```
admin / admin
```
---

## Security Model
- Reality-based TLS obfuscation
- No exposed management panel
- Telegram bot restricted by CHAT_ID
- Sensitive data stored outside repository
- Logs centralized but not publicly exposed

---

## Versioning
```
| Version | Description                      |
| ------- | -------------------------------- |
| v1.0.0  | First stable platform release    |
| legacy  | Pre-platform experimental builds |
```
Semantic Versioning:
        MAJOR.MINOR.PATCH

---

## Roadmap (Planned)
- Multi-server cluster support
- REST API layer
- Web management panel
- Role-based access control
- Auto-backup of users
- Usage-based billing hooks
- Dockerized core mode

---

## ⚠️ Disclaimer
For educational and private infrastructure use only.
Ensure compliance with local laws.
        
