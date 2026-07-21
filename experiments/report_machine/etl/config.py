"""
ETL 配置中心
"""
from pathlib import Path

# ===== 路径 =====
BASE_DIR = Path(__file__).resolve().parent  # etl/
DB_DIR = Path("/home/stockagent/project_space/database")
DB_PATH = DB_DIR / "report_market.db"
ETL_DIR = BASE_DIR
MIDDAY_DIR = BASE_DIR.parent / "data_fetch" / "midday"
LOG_DIR = BASE_DIR / "logs"

for d in [DB_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ===== API 请求控制 =====
API_INTERVAL = 0.3     # Tushare API 调用间隔（秒）
BATCH_SIZE = 50        # 腾讯财经每批股票数
MAX_RETRIES = 3

# ===== Tencent Finance =====
TENCENT_URL = "https://web.sqt.gtimg.cn/q="
TENCENT_HEADERS = {"User-Agent": "Mozilla/5.0"}
