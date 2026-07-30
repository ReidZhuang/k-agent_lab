#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════
# 股票报告系统 — 开发模式启动脚本
# 同时启动:
#   后端 API (FastAPI, 热重载) → http://localhost:8320
#   前端 Vite (HMR)           → http://localhost:5173
# ════════════════════════════════════════════════════════════════
set -e

FRONT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$FRONT_DIR/backend"
FRONTEND_DIR="$FRONT_DIR/frontend"

echo "🚀 股票报告系统 [开发模式]"
echo ""

# 1. 启动后端
echo "📡 启动后端 API (端口 8320)..."
cd "$BACKEND_DIR"
conda run -n stock_agent python main.py &
BACKEND_PID=$!
echo "  ✅ 后端 PID: $BACKEND_PID"
echo ""

# 2. 启动前端 Vite
echo "🎨 启动前端开发服务器 (端口 5173)..."
cd "$FRONTEND_DIR"
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!
echo "  ✅ 前端 PID: $FRONTEND_PID"
echo ""
echo "  📊 前端: http://localhost:5173"
echo "  📡 后端: http://localhost:8320"
echo "  📁 用户空间: /home/stockagent/project_space/research/experiments/report_machine/user_001"
echo ""
echo "  按 Ctrl+C 停止所有服务"

trap "echo ''; echo '🛑 正在停止...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
