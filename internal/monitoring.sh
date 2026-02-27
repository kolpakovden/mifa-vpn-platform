install_monitoring() {
  echo "Installing monitoring stack (Docker Compose): Prometheus + Grafana + Loki + Promtail..."

  # Install docker if missing
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker not found. Installing..."
    bash -c "$(curl -fsSL https://get.docker.com)"
  fi

  # Compose plugin or docker-compose
  if ! docker compose version >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
      apt-get update -y
      apt-get install -y docker-compose-plugin
    fi
  fi

  mkdir -p /opt/mifa/monitoring
  rm -rf /opt/mifa/monitoring/*
  cp -a "$BASE_DIR/monitoring/." /opt/mifa/monitoring/

  # Ensure Xray log folder exists (promtail reads /var/log/xray/access.log)
  mkdir -p /var/log/xray
  touch /var/log/xray/access.log

  cd /opt/mifa/monitoring
  docker compose up -d

  echo "Monitoring is up."
  echo "Grafana:  http://<server-ip>:3000  (admin/admin)"
  echo "Prometheus: http://<server-ip>:9090"
  echo "Loki: http://<server-ip>:3100"
}
