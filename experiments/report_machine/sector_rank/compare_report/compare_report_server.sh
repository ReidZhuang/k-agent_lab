#!/usr/bin/env bash
# 板块对比分析报告生成服务 启停脚本
# 用法: ./compare_report_server.sh {start|stop|restart|status}
set -euo pipefail

PY=/home/stockagent/miniforge3/envs/stock_agent/bin/python
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$DIR/log/compare_report_server.log"
PID_FILE="$DIR/log/compare_report_server.pid"

case "${1:-}" in
  start)
    mkdir -p "$DIR/log"
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "已在运行 (pid $(cat "$PID_FILE"))"; exit 0
    fi
    nohup "$PY" -u "$DIR/compare_report_server.py" >> "$LOG" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2
    echo "已启动 (pid $(cat "$PID_FILE"))"
    echo "日志: $LOG"
    ;;
  stop)
    if [ -f "$PID_FILE" ]; then
      kill "$(cat "$PID_FILE")" 2>/dev/null || true
      rm -f "$PID_FILE"
      echo "已发送停止信号"
    fi
    pkill -f "$DIR/compare_report_server.py" 2>/dev/null || true
    sleep 1
    ;;
  restart)
    "$0" stop; sleep 1; "$0" start
    ;;
  status)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "运行中 (pid $(cat "$PID_FILE"))"
      curl -s -m 3 http://127.0.0.1:8326/health || echo "(health 接口无响应)"
    else
      echo "未运行"
      exit 1
    fi
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status}"; exit 1
    ;;
esac
