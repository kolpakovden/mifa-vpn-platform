upgrade_stack() {
  bash -c "$(curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
  systemctl restart xray
  echo "Upgraded"
}
