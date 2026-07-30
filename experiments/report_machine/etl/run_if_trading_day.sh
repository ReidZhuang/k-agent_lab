#!/bin/bash
# 交易日判断包装脚本：只在交易日执行 ETL 任务
# 内置失败重试：失败后等待 60s 重试一次
# 用法: ./run_if_trading_day.sh <etl_args...>

ETL_DIR="$(cd "$(dirname "$0")" && pwd)"
CONDA_PYTHON="/home/stockagent/miniforge3/envs/stock_agent/bin/python"

# 日志写入 error_log 表
_log_error() {
    local level=$1    # WARNING / ERROR
    local msg=$2
    $CONDA_PYTHON -c "
import sys, sqlite3, uuid
sys.path.insert(0, '$ETL_DIR')
from config import DB_PATH
_bid = str(uuid.uuid4())[:8]
conn = sqlite3.connect(str(DB_PATH))
conn.execute('''INSERT INTO error_log
    (batch_id, timestamp, module, function, level, error_msg)
    VALUES (?, datetime('now','localtime'), 'etl', 'run_if_trading_day.sh', ?, ?)''',
    (_bid, '$level', '$msg'))
conn.commit()
conn.close()
print(f'  [DB] error_log written (batch={_bid})')
"
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
    echo "$(date '+%Y-%m-%d %H:%M:%S') [SKIP] 今日非交易日，跳过 ETL"
    exit 0
fi

cd "$ETL_DIR"

# 第一次运行
echo "$(date '+%Y-%m-%d %H:%M:%S') [RUN] etl_runner.py $@"
$CONDA_PYTHON etl_runner.py "$@" >> logs/etl_runner.log 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [RETRY] 失败 (exit=$EXIT_CODE)，等待 60s 后重试..."
    _log_error "WARNING" "ETL 首次失败 (args=$@, exit=$EXIT_CODE)，即将重试"
    sleep 60
    echo "$(date '+%Y-%m-%d %H:%M:%S') [RUN] 重试 etl_runner.py $@"
    $CONDA_PYTHON etl_runner.py "$@" >> logs/etl_runner.log 2>&1
    EXIT_CODE=$?
fi

if [ $EXIT_CODE -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [FAIL] ETL 重试后仍失败 (exit=$EXIT_CODE)"
    _log_error "ERROR" "ETL 重试后仍失败 (args=$@, exit=$EXIT_CODE)"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') [DONE] ETL 成功"
fi

exit $EXIT_CODE
