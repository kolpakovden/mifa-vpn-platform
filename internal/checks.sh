require_root() {
  [[ "$EUID" -ne 0 ]] && { echo "Run as root"; exit 1; }
}

check_systemd() {
  command -v systemctl >/dev/null || { echo "Systemd required"; exit 1; }
}

check_dependencies() {
  for cmd in curl openssl ss; do
    command -v "$cmd" >/dev/null || {
      echo "Missing dependency: $cmd"
      exit 1
    }
  done
}
