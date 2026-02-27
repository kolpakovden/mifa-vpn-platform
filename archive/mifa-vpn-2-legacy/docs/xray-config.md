# Xray Configuration

Настройка Xray (VLESS + Reality) для проекта.

**Основной конфиг:**

```bash
/usr/local/etc/xray/config.json
```

**Пример с комментариями:** [`config/example.config.json`](../config/example.config.json)

---

## Server Configuration

### Минимальные параметры inbound

| Field | Description |
|-------|-------------|
| `port` | Порт входящего подключения |
| `protocol` | `vless` |
| `id` | UUID пользователя |
| `email` | Идентификатор пользователя (для логов и Loki) |
| `flow` | Для Reality: `xtls-rprx-vision` |

---

## Adding a New User

### Сгенерировать UUID

```bash
xray uuid
```

### Добавить в секцию `clients`

```json
"clients": [
  {
    "id": "UUID",
    "flow": "xtls-rprx-vision",
    "email": "user@server.com"
  }
]
```

---

## Reality Keys

### Генерация ключей

```bash
# Private + Public key
xray x25519

# ShortID
openssl rand -hex 8
```

### Использовать:

- `privateKey` - в `realitySettings`
- `publicKey` - в клиентском конфиге
- `shortId` - в обоих

---

## Validate Configuration

Перед перезапуском:

```bash
xray run -test -config /usr/local/etc/xray/config.json
```

Если ошибок нет - можно перезапускать.

---

## Restart Service

```bash
systemctl restart xray
systemctl status xray
```

---

## Logging (Required for Monitoring)

Для работы Grafana + Loki должна быть включена секция логов:

```json
"log": {
  "loglevel": "info",
  "access": "/var/log/xray/access.log",
  "dnsLog": false
}
```

После изменения:

```bash
systemctl restart xray
```

---

## Quick Troubleshooting

### Проверить логи в реальном времени

```bash
journalctl -u xray -f
```

### Проверить access.log

```bash
tail -f /var/log/xray/access.log
```

---

## Recommended Workflow

1. Сгенерировать UUID
2. Добавить пользователя в `config.json`
3. Проверить конфиг (`-test`)
4. Перезапустить Xray
5. Проверить лог
