#!/usr/bin/env bash
# 板块涨幅排名服务 启停脚本
# 用法: ./sector_rank_server.sh {start|stop|restart|status}
# 统一由 systemd 管理 (mx-sector-rank-server.service, 开机自启 + 崩溃 5s 自动重启),
# 本脚本只是便利入口, 委托 systemctl --user。
set -euo pipefail

UNIT=mx-sector-rank-server.service

case "${1:-}" in
  start)
    systemctl --user start "$UNIT"
    echo "已通过 systemd 启动 ($UNIT)"
    ;;
  stop)
    systemctl --user stop "$UNIT"
    echo "已通过 systemd 停止 ($UNIT)"
    ;;
  restart)
    systemctl --user restart "$UNIT"
    echo "已通过 systemd 重启 ($UNIT)"
    ;;
  status)
    systemctl --user status "$UNIT" --no-pager
    echo "---"
    curl -s -m 3 http://127.0.0.1:8324/health || echo "(health 接口无响应)"
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status}"; exit 1
    ;;
esac
