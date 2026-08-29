#!/usr/bin/env bash
# 在 keeper 环境跑一次"简化版公司分析报告"，并记录全过程日志
# 用法: ./run_report.sh <股票名> [run_tag]
set -euo pipefail

KEEPER_DIR="/home/stockagent/project_space/research/experiments/openclaw-plugin/keeper"
STOCK="${1:?用法: ./run_report.sh <股票名> [run_tag]}"
RUN_TAG="${2:-$(date +%Y%m%d_%H%M%S)}"

echo "=== keeper 生成公司分析报告 ==="
echo "stock    : ${STOCK}"
echo "run_tag  : ${RUN_TAG}"
echo "data源   : 同花顺 IWENCAI (无 mx MCP)"

# 记录运行到日志体系
LOGS_DIR="${KEEPER_DIR}/logs/${RUN_TAG}"
mkdir -p "${LOGS_DIR}"

# 调用报告生成脚本（记录全过程）
python3 "${KEEPER_DIR}/scripts/gen_report.py" "${STOCK}" \
  --run-tag "${RUN_TAG}" \
  --logs-dir "${LOGS_DIR}" \
  --reports-dir "${KEEPER_DIR}/data/reports"

echo ""
echo "=== 运行完成 ==="
echo "日志目录 : ${LOGS_DIR}"
echo "报告目录 : ${KEEPER_DIR}/data/reports"
