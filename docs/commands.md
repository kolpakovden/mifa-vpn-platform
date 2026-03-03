# Command Reference

## Service Status

Xray:
systemctl status xray

Bot:
systemctl status mifa-xray-bot

Monitoring:
cd monitoring
docker compose ps


## Logs

Xray live:
journalctl -u xray -f

Bot live:
journalctl -u mifa-xray-bot -f

Xray access log:
tail -f /var/log/xray/access.log

Loki logs:
docker logs loki


## Restart

Restart Xray:
systemctl restart xray

Restart Bot:
systemctl restart mifa-xray-bot

Restart Monitoring:
cd monitoring
docker compose restart


## Config Validation

Test Xray config before restart:
xray -test -config /usr/local/etc/xray/config.json


## Ports Check

Listening ports:
ss -tulpn | grep xray

Check external port:
curl -vk https://127.0.0.1:8443
