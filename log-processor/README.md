# mifa-log-processor

Parses Xray access.log and produces:
- Prometheus metrics (default :9105)
- normalized JSONL events (/var/log/mifa/traffic.jsonl) for Loki/Grafana

## Build
Requires Go 1.18+.
```bash
cd log-processor
go mod tidy
GOMAXPROCS=1 go build -p 1 -o mifa-log-processor .
sudo install -m 0755 mifa-log-processor /usr/local/bin/mifa-log-processor
Config

Expected runtime config:

/etc/mifa/log-processor.yaml

systemd

Expected service unit:

/etc/systemd/system/mifa-log-processor.service
