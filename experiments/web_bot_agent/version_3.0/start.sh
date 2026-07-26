#!/bin/bash
#
# v3.0 API 服务启动脚本
#
# 流程:
#   1. 检查代理（Clash for Windows）是否运行
#   2. 如果代理未运行，自动启动 Windows 版 Clash
#   3. 等待代理就绪（最多 30 秒）
#   4. 启动 uvicorn API 服务
#
# 用法:
#   ./start.sh                    # 默认端口 8300, worker 数从 config.json 读取
#   PORT=8000 ./start.sh          # 自定义端口
#   PROXY_SKIP=1 ./start.sh       # 跳过代理检查
#

set -e

cd "$(dirname "$0")"

# ── 配置 ──
PROXY_HOST="172.25.32.1"
PROXY_PORT="${PROXY_PORT:-7890}"
API_PORT="${PORT:-8300}"
CLASH_LNK="C:\\Users\\Li Fei\\Desktop\\Clash for Windows.lnk"
PROXY_URL="http://${PROXY_HOST}:${PROXY_PORT}"

# ── 检查代理 ──
if [ -z "$PROXY_SKIP" ]; then
    echo "[start] 🔍 检查代理 $PROXY_URL ..."

    if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "$PROXY_URL" > /dev/null 2>&1; then
        echo "[start] ✅ 代理已在运行"
    else
        echo "[start] ⚠ 代理未运行，尝试启动 Windows Clash..."

        # 通过 PowerShell 启动 Clash for Windows
        if powershell.exe -Command "
            \$proc = Get-Process 'Clash for Windows' -ErrorAction SilentlyContinue;
            if (-not \$proc) {
                Start-Process '$CLASH_LNK';
                Write-Output 'launched';
            } else {
                Write-Output 'already_running';
            }
        " 2>/dev/null | grep -q "launched\|already_running"; then
            echo "[start] 🔄 等待代理就绪..."

            # 等待代理端口开放（最多 30 秒）
            for i in $(seq 1 15); do
                sleep 2
                if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 "$PROXY_URL" > /dev/null 2>&1; then
                    echo "[start] ✅ 代理已就绪（${i}×2s）"
                    break
                fi
                echo -n "."
            done

            # 最终检查
            if ! curl -s -o /dev/null --connect-timeout 3 "$PROXY_URL" > /dev/null 2>&1; then
                echo ""
                echo "[start] ❌ 代理未能启动，请手动启动 Clash for Windows"
                echo "[start]    快捷方式: ${CLASH_LNK}"
                exit 1
            fi
        else
            echo "[start] ❌ 无法启动 Clash for Windows"
            echo "[start]    请手动启动后重试"
            exit 1
        fi
    fi
else
    echo "[start] ⏭ 跳过代理检查（PROXY_SKIP=1）"
fi

# ── 读取 worker 数配置（从 config.json） ──
_WORKERS=$(python3 -c "import json; print(json.load(open('config/config.json')).get('server',{}).get('workers',12))" 2>/dev/null || echo "12")
echo "[start] 🚀 启动 API 服务 (端口 ${API_PORT}, workers ${_WORKERS})..."
exec conda run -n stock_agent uvicorn api:app \
    --host 0.0.0.0 --port "${API_PORT}" \
    --workers "${_WORKERS}"
