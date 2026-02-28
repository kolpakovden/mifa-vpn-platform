#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

source "$BASE_DIR/internal/logger.sh"
source "$BASE_DIR/internal/checks.sh"
source "$BASE_DIR/internal/core.sh"
source "$BASE_DIR/internal/monitoring.sh"
source "$BASE_DIR/internal/bot.sh"
source "$BASE_DIR/internal/uninstall.sh"
source "$BASE_DIR/internal/upgrade.sh"

LOG_FILE="/var/log/mifa-installer.log"
exec > >(tee -a "$LOG_FILE") 2>&1

show_help() {
  echo "MIFA-VPN Installer"
  echo "Usage:"
  echo "  install.sh --core"
  echo "  install.sh --monitoring"
  echo "  install.sh --bot"
  echo "  install.sh --all"
  echo "  install.sh --upgrade"
  echo "  install.sh --uninstall"
}

main() {
  require_root
  check_systemd
  check_dependencies

  case "${1:-}" in
    --core) install_core ;;
    --monitoring) install_monitoring ;;
    --bot) install_bot ;;
    --all)
      install_core
      install_monitoring
      install_bot
      ;;
    --upgrade) upgrade_stack ;;
    --uninstall) uninstall_all ;;
    *) show_help; exit 1 ;;
  esac
}

main "$@"
