# MIFA VPN Platform — Archived

> ⚠️ **PROJECT ARCHIVED / DEVELOPMENT COMPLETED**
>
> MIFA VPN Platform is no longer actively developed. The platform proved stable and reliable in production, and its development cycle is considered complete.
>
> Active development has moved to the simplified **[MIFA VPN Core](https://github.com/kolpakovden/mifa-vpn-core)** architecture.

![Version](https://img.shields.io/badge/legacy_version-1.2.4-blue)
![Status](https://img.shields.io/badge/status-archived-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## Why the architecture was retired

MIFA VPN Platform was built as a full self-hosted VPN platform with traffic, control and observability layers. It successfully demonstrated production stability, but the Grafana / Prometheus / Loki / Promtail stack eventually created more operational complexity and digital noise than the current deployment required.

The project therefore moved to a smaller production architecture focused on the components that are actually used:

- Xray
- VLESS + Reality
- XHTTP over nginx/TLS
- Telegram administration
- backup / restore
- health checks

The successor project is **MIFA VPN Core**:

https://github.com/kolpakovden/mifa-vpn-core

## Legacy architecture

```text
Telegram Admin
      │
      ▼
Telegram Bot
      │
      ▼
    Xray ─────────► Internet

Logs    ─► Promtail ─► Loki ─────► Grafana
Metrics ─► Prometheus ───────────► Grafana
```

## Historical features

- Xray Core / VLESS / Reality
- multi-port configuration
- Telegram user lifecycle management
- centralized state handling
- Grafana dashboards
- Prometheus metrics
- Loki log storage
- Promtail log shipping
- Node Exporter
- Docker Compose observability stack
- structured Xray access logs
- modular installer

## Repository status

- **Development:** completed
- **New features:** not planned
- **Monitoring stack updates:** not planned
- **Purpose:** historical stable release and reference implementation
- **Successor:** [MIFA VPN Core](https://github.com/kolpakovden/mifa-vpn-core)

Existing code remains available for reference and for users who specifically need the former observability stack. For new installations, use MIFA VPN Core instead.

## Historical project structure

```text
mifa-vpn-platform/
│
├── cmd/
│   └── install.sh
├── internal/
│   ├── core.sh
│   ├── bot.sh
│   └── monitoring.sh
├── core/
│   └── templates/
├── monitoring/
│   ├── docker-compose.yml
│   ├── loki-config.yaml
│   ├── promtail-config.yaml
│   └── dashboards/
├── bot/
│   ├── bot.py
│   └── systemd/
└── archive/
    └── mifa-vpn-2-legacy/
```

## Legacy versions

| Version | Milestone |
|---|---|
| v1.0.0 | Initial stable platform |
| v1.0.2 | Monitoring stabilization |
| v1.1.0 | Telegram bot + QR + deploy helper |
| v1.1.8 | Monitoring stabilization + MIFA NOC dashboard |
| v1.2.0 | Public infrastructure milestone release |
| v1.2.4 | Configuration synchronization and platform stabilization |

## Early Supporters

These people were with the project during its early versions, tested legacy builds, reported bugs and provided feedback.

### Early Testers

- @prianikschastia2-tech — one of the first project testers; legacy/MIFA testing and feedback
- ...

## Disclaimer

Intended for educational and infrastructure automation purposes. Ensure compliance with local laws. Usage rights are governed by the MIT License.

## License

This repository's original code, configuration templates and documentation are licensed under the [MIT License](LICENSE). Keep the copyright and permission notice when redistributing copies or substantial portions.

Third-party software and any third-party materials retain their own licenses and copyright notices. This license does not relicense Xray, Grafana, Loki or other dependencies.
