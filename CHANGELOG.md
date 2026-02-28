# Changelog

## [1.0.1] - 2026-02-28

### Fixed
- Monitoring stack стабилизирован и стал воспроизводимым: закреплены версии образов (Grafana/Prometheus/Loki/Promtail/Node Exporter).
- Loki: исправлены пути WAL и compactor (хранение в `/var/lib/loki`), устранены падения контейнера и проблемы с правами.
- Installer: улучшены проверки и поток установки.

### Notes
- Не используем `:latest` для monitoring-образов, чтобы избежать несовместимости конфигов при обновлениях.

## [1.0.0] - Initial Release

### Added
- Xray VLESS + Reality core
- Multi-port configuration
- Telegram bot management
- Dockerized monitoring stack
- Centralized state management
