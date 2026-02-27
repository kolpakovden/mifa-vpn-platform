## Monitoring Stack (Grafana + Loki + Prometheus)

Полный стек мониторинга сервера и пользовательской активности:

- **Loki + Promtail** — сбор и агрегация логов
- **Prometheus + Node Exporter** — системные метрики (CPU, RAM, диск, сеть)
- **Grafana** — визуализация

---

## Архитектура

```
Logs    → Promtail → Loki    → Grafana
Metrics → Node Exporter → Prometheus → Grafana
```

---

### 1. Установка Loki

**Скачать и установить**
```bash
sudo wget -O /usr/local/bin/loki \
https://github.com/grafana/loki/releases/download/v3.6.7/loki-linux-amd64
sudo chmod +x /usr/local/bin/loki
```

**Создать директории**
```bash
sudo mkdir -p /etc/loki
sudo mkdir -p /var/lib/loki/{index,chunks,cache}
```

**Скопировать конфигурации**
```bash
sudo cp config/loki-config.yaml /etc/loki/loki-config.yaml
sudo cp config/loki.service /etc/systemd/system/loki.service
```

**Запуск**
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now loki
```

**Проверка**
```bash
curl http://localhost:3100/ready
```

---

### 2. Установка Promtail

Promtail собирает логи и отправляет их в Loki.

**Конфигурация**
```bash
sudo cp config/promtail-config.yaml /etc/loki/promtail-config.yaml
```

**Запуск в Docker**
```bash
docker run -d \
  --name promtail \
  --network host \
  --restart always \
  -v /var/log/xray:/var/log/xray:ro \
  -v /etc/loki/promtail-config.yaml:/etc/promtail/config.yaml:ro \
  -v /var/lib/loki/positions.yaml:/var/lib/loki/positions.yaml \
  grafana/promtail:3.6.7 \
  -config.file=/etc/promtail/config.yaml
```

**Проверка**
```bash
curl -s http://localhost:9080/metrics | grep promtail_read_bytes_total
```

---

### 3. Prometheus + Node Exporter

**Установка Node Exporter**
```bash
wget https://github.com/prometheus/node_exporter/releases/download/v1.8.2/node_exporter-1.8.2.linux-amd64.tar.gz
tar xvf node_exporter-1.8.2.linux-amd64.tar.gz
sudo mv node_exporter-1.8.2.linux-amd64/node_exporter /usr/local/bin/
```

**Systemd сервис**
```bash
sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<EOF
[Unit]
Description=Node Exporter
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/node_exporter --web.listen-address=:9101
Restart=always

[Install]
WantedBy=multi-user.target
EOF
```

**Запуск**
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now node_exporter
```

**Проверка**
```bash
curl -s http://localhost:9101/metrics | grep node_cpu | head -5
```

---

### 4. Настройка Prometheus

Добавить в `/etc/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: "node_custom"
    static_configs:
      - targets: ["localhost:9101"]
    scrape_interval: 15s
```

**Проверка**
```bash
curl -s http://localhost:9090/api/v1/targets \
| python3 -m json.tool | grep -A 5 node_custom
```

---

### 5. Подключение к Grafana

Открыть: `http://<SERVER-IP>:3000`

**Configuration → Data Sources → Add data source**

Добавить:

| Data source | URL |
|-------------|-----|
| **Loki** | `http://localhost:3100` |
| **Prometheus** | `http://localhost:9090` |

Нажать **Save & Test**

---

### 6. Полезные PromQL-запросы

| Метрика | PromQL |
|---------|--------|
| **CPU %** | `100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)` |
| **RAM %** | `(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100` |
| **Disk %** | `(node_filesystem_size_bytes{mountpoint="/"} - node_filesystem_free_bytes{mountpoint="/"}) / node_filesystem_size_bytes{mountpoint="/"} * 100` |
| **Network RX** | `rate(node_network_receive_bytes_total{device="ens3"}[1m])` |
| **Network TX** | `rate(node_network_transmit_bytes_total{device="ens3"}[1m])` |

---

### 7. Готовый дашборд

Импортируй дашборд [`dashboards/user-activity.json`](dashboards/user-activity.json) в Grafana.

После импорта будут доступны:
- Активность пользователей
- Топ доменов
- Логи в реальном времени
- CPU / RAM / Disk / Network

---

## Полезные команды

```bash
# Статус сервисов
systemctl status loki
systemctl status node_exporter

# Просмотр логов
journalctl -u loki -f
journalctl -u node_exporter -f

# Статус Promtail
docker ps | grep promtail
docker logs promtail --tail 20
```
