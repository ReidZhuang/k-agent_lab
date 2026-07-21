"""生成板块分类树状结构 MD 文件"""
import sys
sys.path.insert(0, '/home/stockagent/project_space/research/experiments/report_machine/etl')
from db_manager import DatabaseManager
from collections import defaultdict
from datetime import datetime

db = DatabaseManager('/home/stockagent/project_space/database/report_market.db')
lines = []

def w(s=''): lines.append(s)

w('# A股板块分类树状结构')
w()
w('基于本地数据库贴源层（stg_）生成，包含同花顺(THS)、东方财富(DC)、通达信(TDX)三大源。')
w()

# === THS ===
THS_TYPE_DESC = {
    'N': '概念指数 — 市场主题/概念驱动的板块，盘中波动最大，个股最敏感的归类和炒作抓手',
    'I': '行业指数 — 基于GICS行业分类标准，产业基本面驱动，适合判断个股的产业背景',
    'R': '地域指数 — 按地域划分的区域性板块',
    'S': '特色指数 — 特色标签类板块，如大盘股、成交额排名等统计型分类',
    'ST': '风格指数 — 投资风格分类（市值/估值/成长/价值等维度）',
    'TH': '主题指数 — 跨行业的宏观主题类板块',
    'BB': '宽基指数 — 全市场宽基类指数，如全A、沪深300等，个股层面参考意义较低',
}

w('## 一、同花顺（THS）板块分类')
w()
w(f'总数: {db.count_rows("stg_ths_index")} 个板块')
w()

ths_data = defaultdict(list)
for r in db.execute('SELECT type, ts_code, name FROM stg_ths_index ORDER BY type, ts_code'):
    ths_data[r[0]].append((r[1], r[2]))

for tp in ['N', 'I', 'TH', 'S', 'ST', 'R', 'BB']:
    items = ths_data.get(tp, [])
    if not items:
        continue
    desc = THS_TYPE_DESC.get(tp, '')
    w(f'### {tp} — {desc.split("—")[0].strip()}（{len(items)}个）')
    w()
    w(f'{desc}')
    w()
    for sc, nm in items:
        w(f'- `{sc}` {nm}')
    w()

# === DC ===
w('## 二、东方财富（DC）板块分类')
w()

dc_types = [r[0] for r in db.execute('SELECT DISTINCT idx_type FROM stg_dc_index')]
w(f'分类类型: {", ".join(dc_types)}')
w(f'总数: {db.count_rows("stg_dc_index")} 个板块')
w()

dc_data = defaultdict(list)
for r in db.execute('SELECT idx_type, ts_code, name FROM stg_dc_index ORDER BY idx_type, ts_code'):
    dc_data[r[0]].append((r[1], r[2]))

for tp, items in dc_data.items():
    w(f'### {tp}（{len(items)}个）')
    w()
    for sc, nm in items:
        w(f'- `{sc}` {nm}')
    w()

# === TDX ===
w('## 三、通达信（TDX）板块分类')
w()

tdx_types = [r[0] for r in db.execute('SELECT DISTINCT idx_type FROM stg_tdx_index')]
w(f'分类类型: {", ".join(tdx_types)}')
w(f'总数: {db.count_rows("stg_tdx_index")} 个板块')
w()

tdx_data = defaultdict(list)
for r in db.execute('SELECT idx_type, ts_code, name FROM stg_tdx_index ORDER BY idx_type, ts_code'):
    tdx_data[r[0]].append((r[1], r[2]))

for tp, items in tdx_data.items():
    w(f'### {tp}（{len(items)}个）')
    w()
    for sc, nm in items:
        w(f'- `{sc}` {nm}')
    w()

w('---')
w(f'> 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")} | 数据来源: report_market.db')

path = '/home/stockagent/project_space/research/experiments/report_machine/design/midday/sector_tree.md'
with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f'✅ 已保存: {path}')
print(f'   共 {len(lines)} 行')
