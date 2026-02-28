install_bot() {
  echo "Installing Telegram bot module..."

  mkdir -p /opt/mifa/bot
  mkdir -p /etc/mifa

  # Dependencies
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip sudo
  fi

  # Copy bot sources
  cp "$BASE_DIR/bot/bot.py" /opt/mifa/bot/bot.py
  cp "$BASE_DIR/bot/requirements.txt" /opt/mifa/bot/requirements.txt
  chmod +x /opt/mifa/bot/bot.py

  # venv
  if [[ ! -d /opt/mifa/bot/venv ]]; then
    python3 -m venv /opt/mifa/bot/venv
  fi
  /opt/mifa/bot/venv/bin/pip install --upgrade pip
  /opt/mifa/bot/venv/bin/pip install -r /opt/mifa/bot/requirements.txt

  # Bot env template (token + chat id)
  if [[ ! -f /etc/mifa/bot.env ]]; then
    cat > /etc/mifa/bot.env <<'EOF'
# Fill these and then: systemctl restart mifa-xray-bot
BOT_TOKEN=
# Recommended: comma-separated Telegram user IDs who can управлять ботом
ADMIN_IDS=
# Optional: allow commands only from this chat/group id
ALLOWED_CHAT_ID=
# Optional: override host shown in links (else SERVER_IP from state.env)
# SERVER_HOST=
EOF
    chmod 600 /etc/mifa/bot.env
    echo "Created /etc/mifa/bot.env (fill BOT_TOKEN + ADMIN_IDS)"
  else
    echo "Found existing /etc/mifa/bot.env"
  fi

  # Ensure core state exists
  if [[ ! -f /etc/mifa/state.env ]]; then
    echo "WARNING: /etc/mifa/state.env not found. Run --core first (or create state.env manually)."
  fi

  # NOTE: bot service in this setup runs as root (see systemd unit), so sudoers is not required.
  # If you switch bot to a non-root user later, add a dedicated sudoers rule for restarting xray.

  # Install systemd unit
  cp "$BASE_DIR/bot/systemd/mifa-xray-bot.service" /etc/systemd/system/mifa-xray-bot.service
  systemctl daemon-reload
  systemctl enable --now mifa-xray-bot.service

  echo "Bot module installed."
  echo "Next: edit /etc/mifa/bot.env and restart: systemctl restart mifa-xray-bot"
}
