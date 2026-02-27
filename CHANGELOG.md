# Changelog

## 1.0.0
- Platform base: one installer (`cmd/install.sh`) with modules: core / monitoring / bot
- Core: Xray VLESS Reality multi-port config + access log enabled
- Monitoring: Docker Compose stack (Grafana + Prometheus + Loki + Promtail)
- Bot: Telegram admin bot (add/list/del/key/restart) + systemd service
- Legacy snapshot kept in `archive/mifa-vpn-2-legacy` (pre-platform history)
