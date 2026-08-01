#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════
# 股票报告系统 — 启动脚本
# ════════════════════════════════════════════════════════════════
set -e

FRONT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$FRONT_DIR/backend"
FRONTEND_DIR="$FRONT_DIR/frontend"

echo "🚀 股票报告系统启动中..."
echo ""

# 1. 构建前端
echo "📦 构建前端..."
cd "$FRONTEND_DIR"
npx vite build --logLevel silent
echo "  ✅ 前端构建完成: $FRONTEND_DIR/dist"
echo ""

# 2. 启动后端（同时托管前端静态文件）
echo "📡 启动后端 API 服务..."
cd "$BACKEND_DIR"
exec conda run -n stock_agent python main.py
