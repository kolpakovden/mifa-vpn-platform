This document describes the current architecture of MIFA Platform.

# Architecture Overview — MIFA Platform

Self-hosted VPN platform built on Xray (VLESS + Reality)  
with Telegram-based user management and full observability stack  
(Prometheus + Grafana + Loki).

---

# 1. Architectural Layers

MIFA Platform consists of three logical layers:

---

## A. Traffic Layer (VPN Data Plane)

### Xray Core

- Protocol: VLESS
- TLS Camouflage: Reality (no certificates required)
- Multi-port inbounds support
- Structured access logging (for Loki ingestion)

### Configuration

Central config:
```
/usr/local/etc/xray/config.json
```
Access logs:
```
/var/log/xray/access.log
```

### Role

- Single source of truth for client credentials
- All user management ultimately modifies Xray configuration
- Xray is the only component handling network traffic

Xray must remain deterministic and reload-safe.

---

## B. Control Layer (User & Config Management)

### Telegram Bot

Built with:
- python-telegram-bot

Acts as operator console.

### Commands

- `/add <user>` - generate UUID/key and inject into config
- `/del <user>` - remove user from config
- `/list` - list configured users
- `/key <user>` - return VLESS URI
- `/restart` - safe service restart

### Runtime

Systemd service:
mifa-xray-bot

Environment:
/etc/mifa/bot.env

State metadata:
/etc/mifa/state.env


### Role

- Single control entry point
- Modifies Xray config file
- Performs safe reload/restart

In v1.0.2 the bot is tightly coupled to file-based configuration.
There is no external database.

---

## C. Observability Layer (Metrics + Logs)

Fully containerized via Docker Compose.

### Components

- Prometheus - metrics collection
- Grafana - dashboards & log exploration
- Loki - log storage
- Promtail - log shipper (reads Xray logs)
- Node Exporter - system metrics

### Endpoints

- Grafana: :3000
- Prometheus: :9090
- Loki: :3100
- Node Exporter: :9100

### Storage

Loki runs in single-node mode.
Persistent storage:
/var/lib/loki
This avoids permission and restart issues.

### Role

- Full visibility into traffic activity
- Server health metrics
- Log-based diagnostics
- Production observability by default

---

# 2. Operational Flows

## Flow 1 - User Provisioning

1. Admin sends:
   `/add alice`
2. Bot generates UUID/key
3. Bot modifies `config.json`
4. Bot reloads Xray
5. `/key alice` returns VLESS URI

Result:
User is active immediately after reload.

---

## Flow 2 — User Removal

1. `/del alice`
2. Client entry removed from config
3. Xray reload

Result:
Access revoked instantly.

---

## Flow 3 — Observability Pipeline

Xray → access.log  
Promtail → Loki  
Grafana → Explore/Dashboards  

Node Exporter → Prometheus → Grafana

Result:
Traffic + infrastructure visibility.

---

# 3. Architectural Invariants

The following principles must remain true:

- Xray config is the single source of truth for clients
- Bot acts as control plane only
- No hidden state outside config/state.env
- Observability is containerized and isolated
- Secrets are stored outside repository
- External exposure should be minimized (prefer firewall restrictions)

---

# 4. Security Posture

- Reality provides TLS camouflage
- No public admin panel
- Management via Telegram only
- Services isolated via systemd and Docker
- Monitoring endpoints should be firewall-restricted
