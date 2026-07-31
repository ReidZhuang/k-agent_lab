#!/bin/bash
# 交易日判断包装脚本：只在交易日执行 ETL 任务
# 内置失败重试：失败后等待 60s 重试一次
# 用法: ./run_if_trading_day.sh <etl_args...>

ETL_DIR="$(cd "$(dirname "$0")" && pwd)"
CONDA_PYTHON="/home/stockagent/miniforge3/envs/stock_agent/bin/python"

# 包装脚本自身的运行记录（[RUN]/[RETRY]/[FAIL]/[DONE] + error_log 写入结果）
# 注意：脚本 stdout 走 cron 邮箱不可见，所有记录必须同时落到这个文件
WRAPPER_LOG="$ETL_DIR/logs/etl_wrapper.log"

_log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$WRAPPER_LOG"
}

# 日志写入 error_log 表（module='etl'）
# 参数经环境变量传递，避免消息内引号破坏内联 python
# DB 锁时等待最长 30s（默认 5s 过短，崩溃瞬间锁窗口会静默失败），失败自动重试
_log_error() {
    local level=$1    # WARNING / ERROR
    local msg=$2
    export LOG_LEVEL="$level" LOG_MSG="$msg"
    local out rc
    for attempt in 1 2 3; do
        out=$($CONDA_PYTHON -c "
import os, sys, sqlite3, uuid
sys.path.insert(0, '$ETL_DIR')
from config import DB_PATH
_bid = str(uuid.uuid4())[:8]
try:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute('''INSERT INTO error_log
        (batch_id, timestamp, module, function, level, error_msg)
        VALUES (?, datetime('now','localtime'), 'etl', 'run_if_trading_day.sh', ?, ?)''',
        (_bid, os.environ['LOG_LEVEL'], os.environ['LOG_MSG']))
    conn.commit()
    conn.close()
    print(f'OK {_bid}')
except Exception as e:
    print(f'FAIL {type(e).__name__}: {e}')
" 2>&1)
        rc=$?
        if [ $rc -eq 0 ] && [[ "$out" == OK* ]]; then
            _log "[DB] error_log 写入成功 (batch=${out#OK })"
            return 0
        fi
        _log "[DB] error_log 写入失败 (尝试 $attempt/3): $out"
        [ $attempt -lt 3 ] && sleep 3
    done
    return 1
}

# 用 trade_calendar 判断今天是否是交易日
TODAY=$($CONDA_PYTHON -c "
import sys
sys.path.insert(0, '$ETL_DIR/../data_fetch/midday')
from trade_calendar import is_trading_day
from datetime import date
print('1' if is_trading_day(date.today().strftime('%Y%m%d')) else '0')
")

if [ "$TODAY" != "1" ]; then
    _log "[SKIP] 今日非交易日，跳过 ETL"
    exit 0
fi

mkdir -p "$ETL_DIR/logs"
cd "$ETL_DIR"

# 第一次运行
_log "[RUN] etl_runner.py $@"
$CONDA_PYTHON etl_runner.py "$@" >> logs/etl_runner.log 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    _log "[RETRY] 失败 (exit=$EXIT_CODE)，等待 60s 后重试..."
    _log_error "WARNING" "ETL 首次失败 (args=$@, exit=$EXIT_CODE)，即将重试"
    sleep 60
    _log "[RUN] 重试 etl_runner.py $@"
    $CONDA_PYTHON etl_runner.py "$@" >> logs/etl_runner.log 2>&1
    EXIT_CODE=$?
fi

if [ $EXIT_CODE -ne 0 ]; then
    _log "[FAIL] ETL 重试后仍失败 (exit=$EXIT_CODE)"
    _log_error "ERROR" "ETL 重试后仍失败 (args=$@, exit=$EXIT_CODE)"
else
    _log "[DONE] ETL 成功"
fi

exit $EXIT_CODE
