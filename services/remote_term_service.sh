#!/usr/bin/env bash
# remote_term Web SSH Server 服务管理脚本
# 用法: ./remote_term_service.sh {install|uninstall|start|stop|restart|enable|disable|status|logs}

set -e

SERVICE_NAME="remote_term"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"
ENTRY_POINT="${PROJECT_DIR}/server/server.py"
RUN_USER="$(whoami)"
LISTEN_PORT=8080

show_help() {
  cat <<USAGE
Usage: $0 <command>

Commands:
  install    生成 systemd unit 文件并启用开机自启
  uninstall  停止、禁用并删除 systemd unit 文件
  start      启动服务
  stop       停止服务
  restart    重启服务
  enable     设置开机自启
  disable    取消开机自启
  status     查看服务状态
  logs       跟踪日志输出
USAGE
}

do_install() {
  if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "错误: 虚拟环境不存在: ${VENV_PYTHON}"
    echo "请先运行: python3 -m venv ${PROJECT_DIR}/.venv && ${PROJECT_DIR}/.venv/bin/pip install -r ${PROJECT_DIR}/server/requirements.txt"
    exit 1
  fi

  sudo tee "$SERVICE_FILE" > /dev/null <<UNIT
[Unit]
Description=Remote Term Web SSH Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PYTHON} ${ENTRY_POINT} -p ${LISTEN_PORT}
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT

  sudo systemctl daemon-reload
  sudo systemctl enable "${SERVICE_NAME}.service"
  echo "已安装并启用服务: ${SERVICE_NAME} (端口 ${LISTEN_PORT})"
  echo "运行 $0 start 启动服务"
}

do_uninstall() {
  if [[ -f "$SERVICE_FILE" ]]; then
    sudo systemctl stop "${SERVICE_NAME}.service" 2>/dev/null || true
    sudo systemctl disable "${SERVICE_NAME}.service" 2>/dev/null || true
    sudo rm -f "$SERVICE_FILE"
    sudo systemctl daemon-reload
    sudo systemctl reset-failed 2>/dev/null || true
    echo "已卸载服务: ${SERVICE_NAME}"
  else
    echo "服务未安装: ${SERVICE_NAME}"
  fi
}

require_installed() {
  if [[ ! -f "$SERVICE_FILE" ]]; then
    echo "错误: 服务未安装，请先运行 $0 install"
    exit 1
  fi
}

if [[ $# -lt 1 ]]; then
  show_help
  exit 1
fi

case "$1" in
  install)
    do_install
    ;;
  uninstall)
    do_uninstall
    ;;
  start)
    require_installed
    sudo systemctl start "${SERVICE_NAME}.service"
    echo "已启动: ${SERVICE_NAME}"
    ;;
  stop)
    require_installed
    sudo systemctl stop "${SERVICE_NAME}.service"
    echo "已停止: ${SERVICE_NAME}"
    ;;
  restart)
    require_installed
    sudo systemctl restart "${SERVICE_NAME}.service"
    echo "已重启: ${SERVICE_NAME}"
    ;;
  enable)
    require_installed
    sudo systemctl enable "${SERVICE_NAME}.service"
    echo "已启用开机自启: ${SERVICE_NAME}"
    ;;
  disable)
    require_installed
    sudo systemctl disable "${SERVICE_NAME}.service"
    echo "已禁用开机自启: ${SERVICE_NAME}"
    ;;
  status)
    systemctl status "${SERVICE_NAME}.service" --no-pager || true
    ;;
  logs)
    journalctl -u "${SERVICE_NAME}.service" -f
    ;;
  *)
    show_help
    exit 1
    ;;
esac
