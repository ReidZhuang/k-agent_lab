#!/usr/bin/env bash
# 启动 keeper 独立 OpenClaw 环境（--profile keeper 隔离，不碰生产）
set -euo pipefail

KEEPER_DIR="/home/stockagent/project_space/research/experiments/openclaw-plugin/keeper"
PROFILE="keeper"
PORT="${1:-19501}"

echo "=== 启动 keeper OpenClaw 独立环境 ==="
echo "profile : ${PROFILE}"
echo "port    : ${PORT}"
echo "state   : ~/.openclaw-${PROFILE}"

# 确保 keeper profile 的配置来自 keeper/config/openclaw.json
KEEPER_CFG_DIR="${HOME}/.openclaw-${PROFILE}"
mkdir -p "${KEEPER_CFG_DIR}"
if [ ! -f "${KEEPER_CFG_DIR}/openclaw.json" ]; then
  echo "[init] 首次运行：复制 keeper 配置到 profile 配置路径"
  cp "${KEEPER_DIR}/config/openclaw.json" "${KEEPER_CFG_DIR}/openclaw.json"
  echo "[init] 请编辑 ${KEEPER_CFG_DIR}/openclaw.json 填入正确的 gateway auth token（或设置 OPENCLAW_GATEWAY_TOKEN）"
else
  echo "[init] 已存在 profile 配置：${KEEPER_CFG_DIR}/openclaw.json"
fi

echo ""
echo "=== 启动 gateway（后台）==="
# 继承 shell 环境（含 IWENCAI_API_KEY / IWENCAI_BASE_URL）
export IWENCAI_API_KEY="${IWENCAI_API_KEY:-}"
export IWENCAI_BASE_URL="${IWENCAI_BASE_URL:-}"
nohup openclaw --profile "${PROFILE}" gateway run --port "${PORT}" \
  > "${KEEPER_DIR}/logs/gateway-stdout.log" 2>&1 &
echo "gateway PID: $!"
echo "日志: ${KEEPER_DIR}/logs/gateway-stdout.log"
echo "（等待数秒后可用: openclaw --profile keeper gateway status）"
