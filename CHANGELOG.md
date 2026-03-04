# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.
This project adheres to Semantic Versioning.

---

## [1.2.2] - 2026-03-04

### Fixed
- Telegram admin bot: preserve ownership/permissions when updating Xray `config.json` to prevent `permission denied` and failed Xray startups.
- systemd hardening: bot operations (`/status`, `/restart`) are compatible with a bot-safe sandbox profile (without forcing `NoNewPrivs=1`).

### Added
- Documentation updates: architecture, commands and runbook pages for operations and troubleshooting.
- Hardening notes for `NoNewPrivs` / sandbox directives that can break `sudo`.

---

## [1.2.0] - 2026-03-03

### Highlights

- Repository is now public
- Full history sanitization
- Monitoring stack stabilization
- MIFA NOC dashboard (Grafana)
- Security policy finalized
- Official status channel: https://t.me/mifanetwork

---

## [1.1.8] - 2026-03-03

### Added
- MIFA NOC dashboard (Grafana)
  - System metrics (CPU, RAM, Disk, Network)
  - Xray analytics panels:
    - Accepted / min
    - Rejected / min
    - Top users (5m)
    - Top inbounds (5m)
    - Top destinations (5m)

### Fixed
- Grafana dashboard provisioning conflicts (UID duplication)
- Loki LogQL empty-compatible matcher errors
- Provisioned dashboard sync issues

### Changed
- Monitoring stack made stable and fully reproducible
- Removed legacy `user-activity.json` dashboard

---

## [1.1.7] - 2026-03-02
### Changed
- Cleanup duplicated secrets block in `.gitignore`

---

## [1.1.6] - 2026-03-02
### Added
- Track Prometheus alert rules in repository:
  - `monitoring/prometheus/alerts-mifa.yml`

### Changed
- Ensure monitoring configuration is fully versioned and reproducible from Git

---

## [1.1.5] - 2026-03-02
### Added
- `log-processor/README.md` (build instructions, config location, systemd hints)

---

## [1.1.4] - 2026-03-02
### Added
- Alertmanager configuration tracked in repository:
  - `monitoring/alertmanager/alertmanager.yml`
- `mifa-log-processor` Go sources
- Prometheus alert rules (initial packaging)

### Changed
- Monitoring stack made fully reproducible from repository

---

## [1.1.3] - 2026-03-01
### Added
- Telegram alert-router improvements:
  - Severity-based emoji formatting
  - Grouping by `user` and `severity`
  - Optional resolved notifications
  - `PUBLIC_PROMETHEUS_URL` support
  - Loki context enrichment for watchlist alerts (domain, geo, ISP)
- Watchlist critical alert integration (Prometheus → Alertmanager → Telegram)

---

## [1.1.2] - 2026-03-01
### Changed
- Make `bot.py` executable
- Minor Telegram admin bot improvements

---

## [1.1.1] - 2026-03-01
### Changed
- Documentation version bump

---

## [1.1.0] - 2026-03-01
### Added
- Telegram admin bot for Xray management:
  - `/add`, `/del`, `/list`, `/key`, `/info`, `/restart`, `/status`
- QR codes for VLESS links
- Safe configuration apply workflow:
  - backup → write → `xray -test` → restart → automatic rollback
- `mifa-deploy` helper:
  - git pull → dependencies → compile → restart

---

## [1.0.2] - 2026-02-28
### Added
- Initial platform release
- Xray (VLESS + Reality) automation
- Basic monitoring stack
- Monitoring config tracking fixes
