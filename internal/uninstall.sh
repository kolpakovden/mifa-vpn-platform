uninstall_all() {
  echo "Stopping services..."

  # Bot
  systemctl stop mifa-xray-bot 2>/dev/null || true
  systemctl disable mifa-xray-bot 2>/dev/null || true
  rm -f /etc/systemd/system/mifa-xray-bot.service

  # Xray
  systemctl stop xray 2>/dev/null || true
  systemctl disable xray 2>/dev/null || true

  systemctl daemon-reload || true

  echo "Removing files..."
  rm -rf /usr/local/etc/xray
  rm -rf /var/log/xray
  rm -rf /opt/mifa/bot

  # Monitoring
  if command -v docker >/dev/null 2>&1 && [[ -d /opt/mifa/monitoring ]]; then
    (cd /opt/mifa/monitoring && docker compose down || true)
  fi
  rm -rf /opt/mifa/monitoring

  # State
  rm -rf /etc/mifa
  rm -f /etc/sudoers.d/mifa-bot

  echo "Uninstalled."
}
