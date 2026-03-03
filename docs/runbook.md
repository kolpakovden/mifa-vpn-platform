# MIFA Incident Runbook

---

## 0–5 Minutes (Service Down)

1. Check Xray:
   systemctl status xray

2. If failed:
   journalctl -u xray -n 50

3. Validate config:
   xray -test -config /usr/local/etc/xray/config.json

4. Restart:
   systemctl restart xray

---

## Users Report "No Internet"

1. Check access log activity:
   tail -n 50 /var/log/xray/access.log

2. Check inbound port listening:
   ss -tulpn | grep 8443

3. Check firewall:
   ufw status

4. Check if IP blocked (external test from another network)

---

## Bot Not Working

1. systemctl status mifa-xray-bot
2. journalctl -u mifa-xray-bot -n 50
3. Verify bot.env exists

---

## Monitoring Down

cd monitoring
docker compose ps

If containers stopped:
docker compose up -d

---

## Worst Case: Config Broke Xray

1. Restore backup config
2. xray -test
3. systemctl restart xray
4. Confirm port open

---

## Before Any Config Change

ALWAYS:
- Backup config
- Test config
- Then restart

Never:
- Edit and blindly restart
