# levistock 接口调用手册

> 安装: `pip install levistock`
> 类型: Python SDK，函数调用返回 `list` 或 `dict`（非 DataFrame）
> 无需 Token，无需 Cookie，全部免费

---

## 一、通用规则

1. **返回格式**: 全部返回 Python 原生 `list[dict]` 或 `dict`，不是 pandas DataFrame
2. **无需认证**: 直接调用，无任何 Token/Cookie 要求
3. **代码格式**: 板块代码使用东方财富格式（如 `BK0441`），股票代码使用纯数字（如 `300750`）
4. **日期格式**: `YYYYMMDD`（如 `'20260626'`）
5. 建议单次请求间隔 ≥ 0.3 秒

---

## 二、板块类

### 2.1 板块列表

```python
import levistock as lk

# 行业板块（496个）
industries = lk.sector_em('industry')
for s in industries[:5]:
    print(f"{s['sector_name']}: {s['change_pct']:+.2f}% "
          f"主力资金:{s['main_inflow']/100000000:.1f}亿 "
          f"领涨:{s['lead_stock_name']}({s['lead_stock_chg']:+.2f}%)")

# 概念板块（494个）
concepts = lk.sector_em('concept')

# 行业一级/二级/三级
l1 = lk.sector_em('industry_l1')
l2 = lk.sector_em('industry_l2')
l3 = lk.sector_em('industry_l3')
```

### 2.2 板块成分股

```python
# 按板块代码查成分股（板块代码从 sector_em 获取）
code = 'BK0441'  # 新能源汽车
stocks = lk.sector_stocks_em(code)
for s in stocks[:5]:
    print(f"  {s['stock_name']}")

# 板块历史成分
history = lk.sector_stocks_his_kph('20260626', 'zs_type')
```

### 2.3 股票→行业归属

```python
result = lk.sector_stock_belong_em(['300750', '002594'])
for item in result:
    print(f"{item['stock_name']}({item['stock_code']}) → {item['sector_name']}")
# 宁德时代(300750) → 电池
# 比亚迪(002594) → 乘用车
```

### 2.4 板块排名/热度/轮动

```python
# 板块排名
ranking = lk.sector_ranking_kph('20260626', 'industry')

# 板块轮动
rotation = lk.get_sector_rotation()

# 板块热度
heat = lk.get_sector_heat()
```

---

## 三、涨停/跌停类

### 3.1 涨停板分析

```python
# 今日涨停池
zt = lk.stock_zt_pool_em()
print(f"今日涨停: {len(zt)}只")
for s in sorted(zt, key=lambda x: x['continuous'], reverse=True)[:5]:
    print(f"{s['stock_name']}({s['stock_code']}) "
          f"连板:{s['continuous']}板 "
          f"封板:{s['first_zt_time']} "
          f"开板:{s['open_times']}次 "
          f"行业:{s['sector']}")

# 指定日期
zt_hist = lk.stock_zt_pool_em('20260625')
```

### 3.2 跌停板

```python
dt = lk.stock_dt_pool_em()
```

### 3.3 昨日涨停追踪

```python
yesterday = lk.stock_yesterday_zt_em()
for s in yesterday[:5]:
    print(f"{s['stock_name']}: 昨日涨停, 今日表现...")
```

### 3.4 涨停历史/复盘

```python
# 涨停历史
history = lk.limit_up_his_kph()

# 跌停历史
down_history = lk.limit_down_his_kph()

# 破板率
pmsl = lk.get_pmsl()

# 涨停复盘
resumption = lk.get_his_limit_resumption()

# 涨停天天
zttt = lk.get_zttt()
```

### 3.5 异动

```python
# 异动列表
changes = lk.stock_changes_em()

# 异动明细
details = lk.stock_changes_detail_em()
```

---

## 四、大盘指数

```python
# 主要指数（6个）
indices = lk.market_index_em()
for idx in indices:
    print(f"{idx['name']}: {idx['price']} ({idx['change_pct']:+.2f}%) "
          f"成交:{idx['amount']/100000000:.0f}亿")

# 全量指数
all_idx = lk.market_index_all_em()
```

---

## 五、市场情绪与风口（独有价值）

### 5.1 市场情绪

```python
emotion = lk.market_emotion_cls()
print(f"市场热度: {emotion['market_degree']}")
print(f"上涨占比: {emotion['up_ratio']}")
print(f"赚钱效应: {emotion['profit_ratio']}")
print(f"成交额: {emotion['shsz_balance']}")
print(f"涨停梯队:")
for level, info in emotion['limit_up_board'].items():
    print(f"  {level}: {info['count']}只, 晋级率{info['continuous_rate']}")

# 开盘红情绪
kph = lk.market_emotion_kph()
```

### 5.2 风口板块

```python
plates = lk.get_sector_hot_plates()
for p in plates[:5]:
    print(f"\n🔥 {p['secu_name']} ({p['change']*100:+.2f}%)")
    print(f"  原因: {p['up_reason']}")
    print(f"  成分股({len(p['stock_list'])}只):")
    for s in p['stock_list'][:3]:
        tags = ','.join(s.get('up_tags', []))
        print(f"    {s['secu_name']} {s['change']*100:+.2f}% [{tags}]")
```

### 5.3 快讯

```python
# 重要快讯
news = lk.news_telegraph_cls(category='important')
for n in news[:5]:
    print(f"[{n['time']}] {n['title']}")
    print(f"  {n['content'][:100]}")

# 全部快讯
all_news = lk.news_telegraph_cls(category='all')
```

### 5.4 市场主线/风向

```python
# 市场主线
mainline = lk.market_mainline_cls()

# 市场风口
wind = lk.market_wind_cls()

# 风口成分股
wind_stocks = lk.market_wind_stocks_cls()

# 风向标历史
vane = lk.wind_vane_his_kph()
```

---

## 六、个股类

### 6.1 全量A股行情

```python
all_stocks = lk.stocks_all_em(filter_st=True)
# 5000+ 只股票的实时行情
```

### 6.2 个股K线/分时

```python
# K线（财联社源）
kline = lk.stock_kline_cls('SZ300750')

# 分时
timeline = lk.stock_timeline_cls('SZ300750')
```

### 6.3 热度排名（同花顺）

```python
hot = lk.stock_hot_rank_ths(limit=50)
for s in hot:
    print(f"#{s['rank']} {s['stock_name']}({s['stock_code']})")
```

---

## 七、工具类

```python
# 新闻
news_list = lk.news(category='stock')

# 交易日历
trade_days = lk.get_trade_days()

# 判断交易日
is_trade = lk.is_trade_day('20260626')
```

---

## 八、数据时效性

### 8.1 板块数据

| 数据 | 更新频率 | 延迟说明 |
|------|:--------:|---------|
| 行业/概念板块行情（sector_em） | 盘中连续更新 | **近实时** |
| 板块成分股（sector_stocks_em） | 每日盘后 | 成分股调整时更新 |
| 股票→行业归属（sector_stock_belong_em） | 低频 | 行业分类变更时更新 |
| 板块排名/热度 | 盘中连续更新 | **近实时** |

### 8.2 涨停/跌停数据

| 数据 | 更新频率 | 延迟说明 |
|------|:--------:|---------|
| 涨停板池（stock_zt_pool_em） | **盘中连续更新** | **近实时**（涨停即入库） |
| 跌停板池（stock_dt_pool_em） | **盘中连续更新** | **近实时** |
| 昨日涨停表现 | **每交易日开盘后** | T+1，约10:00前完成统计 |
| 涨停历史/复盘 | 每交易日盘后 | T+1 |
| 破板率 | 每交易日盘后 | T+1 |
| 异动列表 | 盘中连续更新 | **近实时** |

### 8.3 大盘指数

| 数据 | 更新频率 | 延迟说明 |
|------|:--------:|---------|
| 主要指数（market_index_em） | 盘中连续更新 | **近实时** |
| 全量指数 | 盘中连续更新 | **近实时** |

**非交易时间**: 指数数据定格在收盘点位。

### 8.4 市场情绪与快讯（财联社 独有）

| 数据 | 更新频率 | 延迟说明 |
|------|:--------:|---------|
| 市场情绪（market_emotion_cls） | **盘中实时** | 实时计算，分钟级刷新 |
| 开盘红情绪（market_emotion_kph） | **每交易日** | 盘中更新 |
| 风口板块（get_sector_hot_plates） | **盘中实时** | 实时推送，有热点即更新 |
| 快讯（news_telegraph_cls） | **实时推送** | 秒级，财联社即时新闻 |
| 市场主线/风向 | 盘中实时 | 实时更新 |

**财联社数据特点**: 这是唯一可以获取**盘中实时市场情绪**的数据源，其他源（akshare/雪球）均无此能力。

### 8.5 个股数据

| 数据 | 更新频率 | 说明 |
|------|:--------:|------|
| 全量A股行情（stocks_all_em） | 盘中连续更新 | 近实时，5000+只 |
| 个股K线（stock_kline_cls） | 每个交易日收盘后 | 财联社源，T+0盘后 |
| 个股分时（stock_timeline_cls） | 盘中连续更新 | 近实时 |
| 热度排名（stock_hot_rank_ths） | 每日更新 | 同花顺热榜 |

### 8.6 响应时间

| 数据源 | 响应时间 |
|--------|:--------:|
| 东方财富（`_em`） | 0.2-0.5s |
| 财联社（`_cls`） | 0.3-1.0s |
| 开盘红（`_kph`） | 0.3-0.8s |
| 同花顺（`_ths`） | 0.3-0.5s |

---

## 九、当前集成状态

```
web_search_base/sources/
  └── levistock.py     🔲 待创建
      ├── sector_belong()          🔲 — 股票→行业归属
      ├── zt_pool()                🔲 — 涨停分析
      ├── hot_plates()             🔲 — 风口板块+上涨原因
      ├── market_emotion()         🔲 — 市场情绪
      └── telegraph()              🔲 — 快讯
```
