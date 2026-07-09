# TuShare Pro 接口调用手册

> 版本: Pro | 安装: `pip install tushare` | GitHub: https://github.com/waditu/tushare
> 类型: Python SDK，通过 `pro.函数名()` 调用，返回 `pandas.DataFrame`
> 特点: 与 akshare 免费直接调用不同，TuShare Pro 需要 Token 鉴权 + 积分门槛

---

## 一、安装与鉴权

### 1.1 安装

```bash
pip install tushare
# 确认安装成功
python -c "import tushare; print(tushare.__version__)"
```

### 1.2 鉴权

```python
import tushare as ts

# 方式一：直接设置
ts.set_token('your_token_here')
pro = ts.pro_api()

# 方式二：从环境变量读取（推荐）
import os
from dotenv import load_dotenv
load_dotenv('~/.secrets/stockagent.env')
ts.set_token(os.getenv("TUSHARE_TOKEN"))
pro = ts.pro_api()

# 验证鉴权成功
df = pro.stock_basic(list_status='L')
print(df.shape)  # 正常返回即鉴权成功
```

### 1.3 Token 获取

Token 从 TuShare Pro 官网获取: https://tushare.pro → 注册 → 个人主页 → 接口Token

---

## 二、基础规则

### 2.1 通用规则

1. **所有接口通过 `pro.函数名()` 调用**，返回 `pandas.DataFrame`
2. **需要 Token 鉴权**，免费额度 120 分，本手册基于 2124 分账户
3. **有频率限制**，2000 分约 60 次/分钟
4. **有积分门槛**，不同接口需要不同积分（2000/3000/5000/6000/8000）
5. **单次返回行数受限**，大部分接口 limit=5000，大数据量需按日期循环
6. **日期格式统一** `YYYYMMDD`（如 `20260709`）

### 2.2 股票代码格式

TuShare 统一使用带后缀的代码格式：

| 市场 | 格式 | 举例 |
|:----:|:----:|:----:|
| A股上海 | `600519.SH` | 贵州茅台 |
| A股深圳 | `000001.SZ` | 平安银行 |
| 创业板 | `300750.SZ` | 宁德时代 |
| 科创板 | `688981.SH` | 中芯国际 |
| 北交所 | `830799.BJ` | 华岭股份 |
| 港股 | `00700.HK` | 腾讯控股 |
| 美股 | `AAPL` | 苹果 |
| 指数 | `000001.SH` | 上证综指 |
| 申万行业 | `801010.SI` | 农林牧渔 |

### 2.3 代码转换工具

```python
def to_tscode(code: str) -> str:
    """转换股票代码为 TuShare 格式"""
    code = code.strip()
    # 去除已有后缀
    for suffix in ['.SH', '.SZ', '.BJ', '.HK']:
        code = code.replace(suffix, '')
    # 去除交易所前缀
    for prefix in ['sh', 'sz', 'SH', 'SZ', 'bj', 'BJ']:
        if code.startswith(prefix):
            code = code[len(prefix):]
    
    # 判断市场
    if code.startswith(('6', '68')):
        return f'{code}.SH'
    elif code.startswith(('0', '3', '30')):
        return f'{code}.SZ'
    elif code.startswith(('4', '8')):
        return f'{code}.BJ'
    return code

# 港股格式处理
def to_hkcode(code: str) -> str:
    code = code.strip()
    for suffix in ['.HK']:
        code = code.replace(suffix, '')
    # 港股代码补零到5位
    code = code.zfill(5)
    return f'{code}.HK'
```

---

## 三、标准调用模式

### 3.1 DataFrame → 格式化文本

```python
import tushare as ts
ts.set_token('your_token')
pro = ts.pro_api()

def format_df(df, title=""):
    """DataFrame 转可读文本"""
    lines = [title, "=" * 40]
    for _, row in df.iterrows():
        items = [f"{col}: {row[col]}" for col in df.columns]
        lines.append(" | ".join(str(x) for x in items))
    return "\n".join(lines)
```

### 3.2 行情数据 — 标准模式

```python
import tushare as ts
ts.set_token('your_token')
pro = ts.pro_api()

# 日线行情
df = pro.daily(
    ts_code='000001.SZ',
    start_date='20260101',
    end_date='20260630'
)
# df 列: ts_code, trade_date, open, high, low, close, pre_close, change,
#          pct_chg, vol, amount

# 周线行情
df = pro.weekly(ts_code='600519.SH')

# 月线行情
df = pro.monthly(ts_code='600519.SH')

# 复权行情（推荐用 pro_bar）
df = pro.pro_bar(
    ts_code='600519.SH',
    adj='qfq',          # qfq=前复权, hfq=后复权, ''=不复权
    start_date='20260101',
    end_date='20260630'
)

# 每日指标（PE/PB/换手率）
df = pro.daily_basic(ts_code='000001.SZ', start_date='20260601')

# 涨跌停价格
df = pro.stk_limit(ts_code='000001.SZ', trade_date='20260708')
```

### 3.3 财务数据 — 标准模式

```python
# 利润表
df = pro.income(ts_code='300750.SZ', start_date='20250101', end_date='20260630')
# 核心列: revenue, total_profit, n_income, basic_eps

# 资产负债表
df = pro.balancesheet(ts_code='300750.SZ')
# 核心列: total_assets, total_liab, total_hldr_eqy

# 现金流量表
df = pro.cashflow(ts_code='300750.SZ')
# 核心列: cashflow_op, cashflow_inv, cashflow_fin

# 财务指标（最常用）
df = pro.fina_indicator(ts_code='300750.SZ')
# 核心列: roe, roe_diluted, gross_profit_margin, net_profit_margin, eps

# 业绩预告
df = pro.forecast(ts_code='300750.SZ')

# 业绩快报
df = pro.express(ts_code='300750.SZ')

# 分红送股
df = pro.dividend(ts_code='600519.SH')

# 主营业务构成
df = pro.fina_mainbz(ts_code='300750.SZ', type='P')  # type='P'按产品, 'D'按地区
```

### 3.4 资金流向 — 标准模式

```python
# 个股资金流向
df = pro.moneyflow(ts_code='000001.SZ', start_date='20260601')
# 列: buy_sm_vol, sell_sm_vol, buy_md_vol, sell_md_vol, buy_lg_vol, sell_lg_vol

# 沪深港通资金流向
df = pro.moneyflow_hsgt(start_date='20260601', end_date='20260708')

# 行业资金流向
df = pro.moneyflow_ind_ths(trade_date='20260708')

# 大盘资金流向
df = pro.moneyflow_mkt_dc(trade_date='20260708')
```

### 3.5 股东数据 — 标准模式

```python
# 前十大股东
df = pro.top10_holders(ts_code='600519.SH', start_date='20260101')

# 前十大流通股东
df = pro.top10_floatholders(ts_code='600519.SH')

# 股东人数
df = pro.stk_holdernumber(ts_code='600519.SH')

# 股东增减持
df = pro.stk_holdertrade(ts_code='600519.SH')
```

### 3.6 宏观数据 — 标准模式

```python
# GDP
df = pro.cn_gdp()

# CPI
df = pro.cn_cpi()

# PPI
df = pro.cn_ppi()

# PMI（需先调用一次建立连接）
df = pro.cn_pmi()

# Shibor
df = pro.shibor()

# LPR
df = pro.shibor_lpr()

# M2货币供应
df = pro.cn_m()

# 社融增量
df = pro.sf_month()

# 美债收益率
df = pro.us_tycr()
```

### 3.7 申万行业分类（核心模块）

```python
# 一级行业（31个）
df_L1 = pro.index_classify(level='L1', src='SW2021')
# 列: index_code, industry_name, level

# 二级行业（134个）
df_L2 = pro.index_classify(level='L2', src='SW2021')

# 三级行业
df_L3 = pro.index_classify(level='L3', src='SW2021')

# 行业成分股
df_members = pro.index_member_all(index_code='801010.SI')
# 列: index_code, index_name, con_code, con_name, in_date, out_date, is_new

# 行业日行情
df_sw = pro.sw_daily(ts_code='801010.SI', start_date='20260101')
```

### 3.8 指数 — 标准模式

```python
# 指数日线
df = pro.index_daily(ts_code='000300.SH', start_date='20260101')

# 指数成分和权重
df = pro.index_weight(index_code='000300.SH', start_date='20260601')

# 指数基本信息
df = pro.index_basic(ts_code='000300.SH')

# 全球指数
df = pro.index_global()
```

### 3.9 股票列表/基本信息

```python
# 全市场股票列表
df = pro.stock_basic(list_status='L')
# L上市, D退市, P暂停上市
# 列: ts_code, symbol, name, area, industry, fullname, list_date, market

# 上市公司基本信息
df = pro.stock_company(ts_code='000001.SZ')
# 列: chairman, managers, reg_capital, employees, main_business

# 交易日历
df = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20261231')
# 列: cal_date, is_open, pretrade_date

# IPO新股
df = pro.new_share(start_date='20260101')

# 股票曾用名
df = pro.namechange(ts_code='600519.SH')
```

### 3.10 融资融券/质押/大宗

```python
# 融资融券汇总
df = pro.margin(trade_date='20260708')

# 融资融券明细
df = pro.margin_detail(ts_code='600519.SH')

# 融资融券标的
df = pro.margin_secs()

# 股权质押统计
df = pro.pledge_stat(ts_code='600519.SH')

# 大宗交易
df = pro.block_trade(ts_code='600519.SH', start_date='20260101')

# 限售股解禁
df = pro.share_float(ts_code='600519.SH')

# 股票回购
df = pro.repurchase(ts_code='600519.SH')
```

### 3.11 期货/ETF/债券/港股/美股

```python
# === 期货 ===
pro.fut_daily(ts_code='CU24.SHF')
pro.fut_basic(exchange='SHFE')
pro.fut_mapping(ts_code='CU24.SHF')
pro.fut_holding(trade_date='20260708', symbol='CU')

# === ETF/基金 ===
pro.fund_daily(ts_code='510050.SH')
pro.fund_basic(market='E')  # E=ETF
pro.fund_portfolio(ts_code='510050.SH')
pro.fund_div(ts_code='510050.SH')

# === 可转债 ===
pro.cb_daily(ts_code='123456.SZ')
pro.cb_basic(ts_code='123456.SZ')
pro.cb_issue()

# === 港股 ===
pro.hk_daily(ts_code='00700.HK')
pro.hk_basic(ts_code='00700.HK')

# === 美股 ===
pro.us_daily(ts_code='AAPL')
pro.us_basic(ts_code='AAPL')

# === 外汇 ===
pro.fx_daily(ts_code='USDCNY')
```

### 3.12 龙虎榜

```python
# 龙虎榜每日明细
df = pro.top_list(trade_date='20260708')
# 列: trade_date, ts_code, name, close, pct_chg, turnover_rate,
#     buy_amount, sell_amount, net_amount

# 龙虎榜机构交易
df = pro.top_inst(trade_date='20260708')
```

---

## 四、完整调用模板

### 4.1 统一客户端

```python
import tushare as ts
import pandas as pd
from typing import Optional

class TuShareClient:
    """TuShare Pro 统一调用客户端"""
    
    def __init__(self, token_path: Optional[str] = None):
        if token_path:
            from dotenv import load_dotenv
            import os
            load_dotenv(token_path)
            token = os.getenv("TUSHARE_TOKEN")
        else:
            token = 'your_token_here'
        ts.set_token(token)
        self.pro = ts.pro_api()
    
    # ===== 行情 =====
    def kline(self, symbol: str, start: str = '', end: str = '') -> pd.DataFrame:
        return self.pro.daily(ts_code=symbol, start_date=start, end_date=end)
    
    def adj_kline(self, symbol: str, adj: str = 'qfq', **kw) -> pd.DataFrame:
        return self.pro.pro_bar(ts_code=symbol, adj=adj, **kw)
    
    def daily_basic(self, symbol: str, **kw) -> pd.DataFrame:
        return self.pro.daily_basic(ts_code=symbol, **kw)
    
    # ===== 财务 =====
    def income(self, symbol: str, **kw) -> pd.DataFrame:
        return self.pro.income(ts_code=symbol, **kw)
    
    def fina_indicator(self, symbol: str, **kw) -> pd.DataFrame:
        return self.pro.fina_indicator(ts_code=symbol, **kw)
    
    # ===== 资金流向 =====
    def moneyflow(self, symbol: str, **kw) -> pd.DataFrame:
        return self.pro.moneyflow(ts_code=symbol, **kw)
    
    def hsgt_flow(self, **kw) -> pd.DataFrame:
        return self.pro.moneyflow_hsgt(**kw)
    
    # ===== 股东 =====
    def top10_holders(self, symbol: str, **kw) -> pd.DataFrame:
        return self.pro.top10_holders(ts_code=symbol, **kw)
    
    def holder_number(self, symbol: str) -> pd.DataFrame:
        return self.pro.stk_holdernumber(ts_code=symbol)
    
    # ===== 行业分类 =====
    def sw_classify(self, level: str = 'L1') -> pd.DataFrame:
        return self.pro.index_classify(level=level)
    
    def sw_members(self, index_code: str) -> pd.DataFrame:
        return self.pro.index_member_all(index_code=index_code)
    
    # ===== 基础数据 =====
    def stock_list(self, status: str = 'L') -> pd.DataFrame:
        return self.pro.stock_basic(list_status=status)
    
    def trade_cal(self, exchange: str = 'SSE', **kw) -> pd.DataFrame:
        return self.pro.trade_cal(exchange=exchange, **kw)
    
    def company_info(self, symbol: str) -> pd.DataFrame:
        return self.pro.stock_company(ts_code=symbol)


# ===== 使用示例 =====
client = TuShareClient('~/.secrets/stockagent.env')

# 日线行情
df = client.kline('000001.SZ', start='20260701', end='20260708')
print(df.tail(3))

# 财务指标
df = client.fina_indicator('300750.SZ')
print(df[['end_date', 'roe', 'eps']].head())

# 行业分类
df = client.sw_classify('L1')
print(f"一级行业数: {len(df)}")
```

### 4.2 带重试的安全调用

```python
import time
from typing import Optional

def safe_call(pro_func, retries: int = 3, delay: float = 1.0, **kwargs):
    """带重试的安全 API 调用"""
    for attempt in range(retries):
        try:
            df = pro_func(**kwargs)
            if df is not None and len(df) > 0:
                return df
            elif df is not None:
                # 空数据等待重试
                print(f"[RETRY] 空数据, {retries - attempt - 1}次剩余")
        except Exception as e:
            if '频率超限' in str(e):
                wait = delay * (attempt + 1) * 60
                print(f"[RATE_LIMIT] 等待 {wait:.0f}s...")
                time.sleep(wait)
            elif attempt < retries - 1:
                print(f"[RETRY] {e}, 重试 {attempt+1}/{retries}")
                time.sleep(delay)
            else:
                print(f"[FAIL] {e}")
                return None
    return None

# 使用
df = safe_call(
    pro.daily,
    ts_code='000001.SZ',
    start_date='20260701',
    end_date='20260708'
)
```

---

## 五、DataFrame 常用处理

### 5.1 提取最新数据

```python
# 日线最新
df = pro.daily(ts_code='000001.SZ', start_date='20260701')
latest = df.iloc[0]  # 默认按日期降序
print(f"最新日期: {latest['trade_date']}")
print(f"收盘价: {latest['close']}")
print(f"涨跌幅: {latest['pct_chg']}%")

# 财务指标最新期
df = pro.fina_indicator(ts_code='300750.SZ')
latest = df.iloc[0]
print(f"ROE: {latest['roe']}%")
print(f"EPS: {latest['eps']}")
```

### 5.2 提取多期趋势

```python
# 多期营收趋势
df = pro.income(ts_code='300750.SZ')
revenue = df[['end_date', 'revenue']].sort_values('end_date')
print(revenue.head(8))  # 最近8期营收

# 多期ROE趋势
df = pro.fina_indicator(ts_code='300750.SZ')
roe = df[['end_date', 'roe']].sort_values('end_date')
print(roe.head(8))
```

### 5.3 行业分类映射

```python
# 获取全市场的行业归属
df_stocks = pro.stock_basic(list_status='L')
industry_map = df_stocks[['ts_code', 'name', 'industry']]

# 获取某股票行业
stock = df_stocks[df_stocks['ts_code'] == '600519.SH']
print(f"{stock['name'].values[0]}: {stock['industry'].values[0]}")

# 按行业分组
industry_count = df_stocks.groupby('industry').size().sort_values(ascending=False)
print(industry_count.head(10))
```

### 5.4 交易日判断

```python
# 判断今天是不是交易日
cal = pro.trade_cal(exchange='SSE', start_date='20260709', end_date='20260709')
is_open = cal['is_open'].values[0]
print(f"今天{'是' if is_open else '不是'}交易日")
```

---

## 六、数据时效性

> 不同数据类型有完全不同的更新节奏，调用前先确认数据是否已到位。

### 6.1 行情数据

| 数据种类 | 更新频率 | 延迟说明 |
|---------|:--------:|---------|
| 日线行情 (daily) | 每个交易日收盘后 | 约 **15:00-17:00** 完成更新 |
| 周线行情 (weekly) | 每周最后一个交易日 | 周五收盘后 |
| 月线行情 (monthly) | 每月最后一个交易日 | 月末收盘后 |
| 复权行情 | 事件驱动 | 分红/送股/配股后立即更新 |
| 复权因子 | 事件驱动 | 同复权行情 |
| 每日指标 (daily_basic) | 每个交易日 | T+1 完成 |
| 涨跌停价格 | 每个交易日 | 盘前计算，盘中可查 |
| 实时行情 | 盘中连续 | 近实时 |
| 停复牌信息 | 每个交易日 | 盘后更新 |
| 备用行情 | 每个交易日 | 盘后更新 |

### 6.2 财务数据

| 数据种类 | 更新节奏 | 说明 |
|---------|:--------:|------|
| 利润表/资产负债表/现金流 | **按季度** | 一季报4月30日前, 中报8月31日前, 三季报10月31日前, 年报次年4月30日前 |
| 财务指标 | **按季度** | 同财务报表披露节奏 |
| 业绩预告 | **不定期** | 公司发布后即时更新（通常在财报截止日前集中发布） |
| 业绩快报 | **不定期** | 比正式财报提前发布 |
| 分红送股 | **不定期** | 董事会/股东大会决议后更新 |
| 财报披露日期 | **按季度** | 交易所提前发布披露日历 |

### 6.3 资金流向

| 数据种类 | 更新频率 | 延迟说明 |
|---------|:--------:|---------|
| 个股资金流向 | **每个交易日盘后** | 约 **17:00-18:00** 更新 |
| 沪深港通资金流向 | **每个交易日** | 盘中/盘后均可查 |
| 行业资金流向 | **每个交易日** | 盘后更新 |
| 沪深港通十大成交 | **每个交易日** | 盘后更新 |

### 6.4 股东数据

| 数据种类 | 更新节奏 | 说明 |
|---------|:--------:|------|
| 前十大股东 | **按季度** | 滞后约1-3个月（季报披露后更新） |
| 股东人数 | **按季度** | 同季报披露节奏 |
| 股东增减持 | **不定期** | 上市公司公告后更新 |

### 6.5 融资融券/质押/大宗

| 数据种类 | 更新频率 | 说明 |
|---------|:--------:|------|
| 融资融券汇总 | **每个交易日** | 约 **18:00-20:00** 更新 |
| 融资融券明细 | **每个交易日** | 同上 |
| 股权质押 | **每日** | 质押登记后更新 |
| 大宗交易 | **每个交易日** | 盘后可查 |

### 6.6 宏观经济

| 数据种类 | 更新节奏 | 说明 |
|---------|:--------:|------|
| GDP | **季度**（滞后约1个月） | 1月/4月/7月/10月公布上季 |
| CPI/PPI | **月度**（滞后约10天） | 每月中旬公布上月 |
| PMI | **月度**（当月最后一天） | 当月发布 |
| Shibor | **每个交易日** | 11:00 报价 |
| LPR | **每月20日** | 固定日期 |
| M2/社融 | **月度** | 约每月10-15日公布上月 |

### 6.7 龙虎榜/打板

| 数据种类 | 更新频率 | 说明 |
|---------|:--------:|------|
| 龙虎榜 | **每个交易日** | 约 **17:30-18:00** 更新 |

### 6.8 其他市场

| 市场 | 更新频率 | 说明 |
|:----|:--------:|------|
| 港股行情 | **每个交易日** | 港股收盘时间晚于A股 |
| 美股行情 | **每个交易日** | 美股为当地时间交易 |
| 期货行情 | **每个交易日** | 日盘+夜盘 |
| 外汇行情 | **每个交易日** | 24小时交易 |
| ETF行情 | **每个交易日** | 跟随交易所 |

---

## 七、注意事项

### 7.1 积分限制

TuShare Pro 使用积分门槛制（不消耗积分），积分越高可调用接口越多：

| 积分区间 | 可调用接口 | 频次限制 |
|:--------:|:----------:|:--------:|
| 120分（免费） | 基础接口约 20 个 | 约 2 次/分钟 |
| 2000分+ | ~160 个接口（本手册） | 约 60 次/分钟 |
| 5000分+ | 含打板/特色数据 ~200 个 | 约 200 次/分钟 |
| 8000分+ | 几乎全覆盖 ~240 个 | 约 500 次/分钟 |

### 7.2 频率限制处理

- 超出频率会返回 `抱歉，您访问接口(xxx)频率超限`
- 建议每次调用间隔 ≥ 0.5 秒
- 频率超限后等待 1 分钟再重试

### 7.3 数据空值处理

```python
# 财务数据可能存在空值
df = pro.fina_indicator(ts_code='300750.SZ')
# 用 fillna 处理
df = df.fillna(0)
# 或只取非空列
df = df.dropna(axis=1, how='all')
```

### 7.4 大数据量循环

```python
# 日线数据一次最多 5000 行，按年循环
import pandas as pd

def fetch_all_daily(symbol, start='20200101', end='20260708'):
    """循环获取全量日线数据"""
    dates = pd.date_range(start, end, freq='YE')
    all_data = []
    for i in range(len(dates)):
        s = dates[i].strftime('%Y%m%d')
        e = dates[i+1].strftime('%Y%m%d') if i+1 < len(dates) else end
        df = pro.daily(ts_code=symbol, start_date=s, end_date=e)
        if df is not None and len(df) > 0:
            all_data.append(df)
        time.sleep(0.5)
    return pd.concat(all_data) if all_data else pd.DataFrame()
```

### 7.5 关键提醒

1. **Token 保护好**: Token 是账户凭证，不要提交到代码仓库
2. **首次调用较慢**: 第一次调用 `pro.xxx()` 会建立网络连接，约 1-3s
3. **非交易时间调用**: 在非交易时间调行情接口可能返回空数据
4. **数据日期**: TuShare 使用 `YYYYMMDD` 格式，注意与 `datetime` 互转
5. **字段名**: 全英文命名（如 `total_assets`），注意拼写
6. **积分不可耗尽**: 积分是门槛制不是消耗制，积分越高能访问的接口越多
