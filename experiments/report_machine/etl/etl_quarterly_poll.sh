#!/usr/bin/env bash
# 季度披露任务轮询: 十大流通股东 + 北向持股 (5/1-5/10、9/1-9/10、11/1-11/10 每小时触发)
# 节假日也跑, 不套交易日包装(与旧 9/1 单次任务一致)
#
# 轮询语义(2026-08-16 用户要求):
#   - 当月已成功 → 直接跳过(标记文件 logs/quarterly_poll.done, 内容=YYYY-MM)
#   - 未成功 → 跑两个 ETL, 且目标报告期/交易日入库行数 > 0 才算"取到结果"写标记;
#     数据源未披露(0 行)或失败 → 不写标记, 下个小时重试
set -u

PY=/home/stockagent/miniforge3/envs/stock_agent/bin/python
HERE="$(cd "$(dirname "$0")" && pwd)"
DB=/home/stockagent/project_space/database/report_market.db
DONE_FILE="$HERE/logs/quarterly_poll.done"
LOG="$HERE/logs/quarterly_poll.log"
MONTH="$(date +%Y-%m)"
mkdir -p "$HERE/logs"

# 当月已成功 → 跳过
if [ -f "$DONE_FILE" ] && [ "$(cat "$DONE_FILE")" = "$MONTH" ]; then
  echo "[$(date '+%F %T')] 本月已成功, 跳过" >> "$LOG"
  exit 0
fi

echo "[$(date '+%F %T')] 开始轮询: top10 + hk_hold"
"$PY" "$HERE/etl_top10.py" --auto >> "$LOG" 2>&1
"$PY" "$HERE/etl_hk_hold.py" --auto >> "$LOG" 2>&1

# 取到结果判定: 目标报告期(十大流通股东)与最近交易日(北向)行数均 > 0
if "$PY" -c "
import sqlite3, sys
from datetime import datetime, timedelta
conn = sqlite3.connect('$DB')
cur = conn.cursor()
today = datetime.now()
q = (today.month - 1) // 3
if q == 0:
    qe = f'{today.year - 1}1231'
else:
    m = q * 3  # 季度末月份: 3/6/9/12 (与 etl_top10.latest_quarter_end 一致)
    day = {3: 31, 6: 30, 9: 30, 12: 31}[m]
    qe = f'{today.year}{m:02d}{day}'
t10 = cur.execute('SELECT COUNT(*) FROM stg_top10_floatholder WHERE end_date=?', (qe,)).fetchone()[0]
hk = 0
d = datetime.strptime(qe, '%Y%m%d')
for _ in range(10):  # 与 etl_hk_hold.auto_latest_trade_date 一致的回退
    s = d.strftime('%Y%m%d')
    hk = cur.execute('SELECT COUNT(*) FROM stg_hk_hold WHERE trade_date=?', (s,)).fetchone()[0]
    if hk > 0:
        break
    d -= timedelta(days=1)
print(f'top10={t10} hk={hk}')
sys.exit(0 if (t10 > 0 and hk > 0) else 1)
"; then
  echo "$MONTH" > "$DONE_FILE"
  echo "[$(date '+%F %T')] 已取到结果, 本月后续轮询跳过" >> "$LOG"
else
  echo "[$(date '+%F %T')] 尚未取到结果, 下小时重试" >> "$LOG"
fi
