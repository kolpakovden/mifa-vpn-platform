# MIFA VPN Platform

![Version](https://img.shields.io/badge/version-1.2.4-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Last Commit](https://img.shields.io/github/last-commit/kolpakovden/mifa-vpn-platform)
![Repo Size](https://img.shields.io/github/repo-size/kolpakovden/mifa-vpn-platform)


MIFA VPN is available in two editions:

- **Platform (current)** — modular architecture with monitoring stack and Telegram control layer.
- **Basic v1.0.0** — lightweight monolithic setup without monitoring and modular components.  
  → https://github.com/kolpakovden/mifa-vpn-basic-v1.0.0

## Which edition should I choose?

- Choose **Basic** if you need a fast, minimal, single-server VPN setup.
- Choose **Platform** if you need monitoring, automation, and production-grade control.

> Historical experimental version available at  
> https://github.com/kolpakovden/mifa-vpn-legacy
---

## Features

- Xray Core (VLESS + Reality)
- Multi-port configuration (8443, 50273)
- Telegram bot for user lifecycle management
- Centralized state handling
- Monitoring stack (Grafana + Prometheus + Loki + Promtail)
- Structured access logging
- Idempotent installer (safe re-run)
- Fully containerized observability layer
  
---

## Architecture Overview

MIFA Platform is a layered VPN infrastructure consisting of:
- **Traffic Layer** — Xray (VLESS + Reality)
- **Control Layer** — Telegram Bot
- **Observability Layer** — Prometheus + Grafana + Loki
  
---

## Architecture Diagram

                ┌────────────────────┐
                │      Telegram      │
                │        Admin       │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │   Telegram Bot     │
                │ (Control Layer)    │
                └─────────┬──────────┘
                          │
                modifies  │ config
                          ▼
                ┌────────────────────┐
                │       Xray         │
                │ (Traffic Engine)   │
                └─────────┬──────────┘
                          │
                          ▼
                   Internet Traffic

Logs → Promtail → Loki → Grafana  
Metrics → Node Exporter → Prometheus → Grafana

---

## Components

### Xray (Traffic Engine)
- VLESS protocol
- Reality TLS obfuscation
- Multi-port inbounds
- Structured logging
- Config: /usr/local/etc/xray/config.json
- Logs: /var/log/xray/access.log

### Telegram Bot (Control Layer)

- Built with python-telegram-bot.
Commands:
```
/add <user>
/del <user>
/list
/key <user>
/restart
```
- Service: mifa-xray-bot (systemd)
- Credentials: /etc/mifa/bot.env
- State file: /etc/mifa/state.env

### Observability Stack (Monitoring)

Containerized via Docker Compose:
- Prometheus - metrics collection
- Grafana - visualization
- Loki - log storage
- Promtail - log shipping
- Node Exporter - system metrics

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
Modular installation:
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
## Monitoring

### Endpoints
```
Service	URL
Grafana	http://SERVER_IP:3000
Prometheus	http://SERVER_IP:9090
Loki	http://SERVER_IP:3100
Node Exporter	http://SERVER_IP:9100
```
Grafana: admin credentials are configured during installation.

It is recommended to restrict Prometheus, Loki and Node Exporter via firewall.

### Loki Storage

Single-node mode.
All data stored in Docker volume:
```
/var/lib/loki
```
Ensures durability and safe restarts.

### Version Pinning
Monitoring images are pinned for reproducible deployments and config compatibility.

---

## Security Model
- Reality-based TLS camouflage
- No exposed web management panel
- Telegram bot restricted via CHAT_ID
- Secrets stored outside repository
- Monitoring endpoints recommended behind firewall
- No direct public configuration surface

---

## Versioning
This project follows **Semantic Versioning (SemVer)**.
Version format:
```
MAJOR.MINOR.PATCH
```
```
Version	Description
v1.0.0	Initial stable platform
v1.0.2	Monitoring stabilization
v1.1.0	Telegram bot + QR + deploy helper
v1.1.8	Monitoring stabilization + MIFA NOC dashboard
v1.2.0	Public infrastructure milestone release
v1.2.4	Configuration synchronization and platform stabilization
```

---

## Roadmap (Planned)
Planned:
- Bot-first control plane
- REST API layer
- Multi-server cluster support
- Role-based access control
- Web management panel
- Automated backups
- Usage-based billing hooks
- Dockerized core mode

---

## Edition Comparison

| Feature | Platform | Basic |
|----------|------------------|----------------|
| Architecture | Modular | Monolithic |
| Xray (VLESS + Reality) | ✅ | ✅ |
| Multi-port support | ✅ | ✅ |
| Telegram Bot | ✅ | ❌ |
| Monitoring (Grafana + Prometheus + Loki) | ✅ | ❌ |
| Structured Logging | ✅ | Minimal |
| Dockerized Observability | ✅ | ❌ |
| Idempotent Installer | ✅ | ✅ |
| Target Use Case | Production Infrastructure | Simple Personal Setup |
| Complexity | Medium | Low |
| Key Distribution (links/QR) | ✅ | ❌ |

---
#  Early Supporters

Эти люди были с проектом с самых первых версий.
Они тестировали легаси-сборки, находили баги, давали честный фидбек
и помогали сделать платформу лучше.

## Early Testers

- @prianikschastia2-tech — один из первых тестировщиков проекта; тестирование легаси-версии и "MIFA", фидбек по рекламному блоку и ядру платформы
- ...

---

## ⚠️ Disclaimer
For educational and private infrastructure use only.
Ensure compliance with local laws.
