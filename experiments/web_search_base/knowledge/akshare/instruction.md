# akshare 接口调用手册

> 版本: 1.18.64 | 安装: `pip install akshare` | GitHub: https://github.com/akfamily/akshare
> 类型: Python 开源库，直接调用函数返回 `pandas.DataFrame`
> 与 Sina/腾讯 REST API 不同，akshare 是函数调用库，无需构造 HTTP 请求

---

## 一、安装与基础

### 1.1 安装

```bash
pip install akshare
# 确认安装成功
python -c "import akshare; print(akshare.__version__)"
```

### 1.2 基础导入

```python
import akshare as ak
```

所有函数直接通过 `ak.函数名()` 调用，返回 `pandas.DataFrame`。

### 1.3 通用规则

1. **所有接口返回 DataFrame**，统一用 pandas 操作
2. **不需要 API Key**，全部免费
3. **无显式频率限制**，但建议单次调用间隔 ≥ 0.2 秒
4. **函数的后缀标识数据来源**: `_em`(东方财富), `_sina`(新浪), `_ths`(同花顺), `_xq`(雪球), `_jsl`(集思录)
5. **网络超时**: 部分函数支持 `timeout` 参数，建议设置 10-30 秒

---

## 二、股票代码格式规则

akshare 不同后缀的函数使用不同的代码格式，这是最常见的坑：

### 2.1 格式对照表

| 函数后缀 | 举例 | 代码格式 | 写法 |
|---------|------|---------|------|
| 无后缀 / `_sina` | `stock_financial_abstract` | 纯6位数字 | `'300750'`, `'600519'` |
| `_em` | `stock_financial_analysis_indicator_em` | 数字 + `.SZ`/`.SH` | `'300750.SZ'`, `'600519.SH'` |
| `_em` (三大报表) | `stock_profit_sheet_by_report_em` | `SZ`/`SH` + 数字 | `'SZ300750'`, `'SH600519'` |
| `_em` (个股信息) | `stock_individual_info_em` | 纯6位数字 | `'300750'`, `'600519'` |
| `_sina` (财务报告) | `stock_financial_report_sina` | `sh`/`sz` + 数字 | `'sh600519'`, `'sz300750'` |
| `_cninfo` | `stock_profile_cninfo` | 纯6位数字 | `'300750'`, `'600519'` |

### 2.2 代码转换工具

```python
def to_akshare_code(code: str, target_format: str) -> str:
    """股票代码格式转换"""
    code = code.strip()
    if code.startswith(('sh', 'sz', 'SH', 'SZ')):
        code = code[2:]  # 去除前缀
    
    if target_format == 'pure':           # 纯数字: stock_financial_abstract
        return code
    elif target_format == 'dot':          # 后缀点: _analysis_indicator_em
        suffix = '.SZ' if code.startswith(('0', '3')) else '.SH'
        return f'{code}{suffix}'
    elif target_format == 'prefix':       # 前缀: _sheet_by_report_em
        prefix = 'SZ' if code.startswith(('0', '3')) else 'SH'
        return f'{prefix}{code}'
    elif target_format == 'sina_prefix':  # 小写前缀: stock_financial_report_sina
        prefix = 'sz' if code.startswith(('0', '3')) else 'sh'
        return f'{prefix}{code}'
    return code
```

---

## 三、标准调用模式

### 3.1 DataFrame → 格式化文本

```python
import akshare as ak

def format_df_to_text(df: pd.DataFrame, title: str = "") -> str:
    """DataFrame 转可读文本"""
    lines = [title, "=" * 40]
    # 选取关键列
    for _, row in df.iterrows():
        items = [f"{col}: {row[col]}" for col in df.columns]
        lines.append(" | ".join(items))
    return "\n".join(lines)
```

### 3.2 财务数据 — 标准模式

```python
import akshare as ak

# 80指标 × 40期财务摘要
df = ak.stock_financial_abstract(symbol='300750')
# df.shape → (80, 42) | 80个指标行, 42个报告期列

# 提取特定指标
roe = df[df['指标'] == 'ROE(加权)']
latest_roe = roe.iloc[0, 2]  # 最新一期

# 提取多期趋势
revenue = df[df['指标'] == '营业总收入']
# revenue.iloc[0, 2:] → 所有期的营收数据
```

### 3.3 行情数据 — 标准模式

```python
# 历史K线
df = ak.stock_zh_a_hist(
    symbol='300750',
    period='daily',          # daily/weekly/monthly
    start_date='20260101',
    end_date='20260626',
    adjust='qfq'             # ''(不复权)/qfq(前复权)/hfq(后复权)
)
# df 列: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,换手率

# 全市场实时行情（慎用，数据量极大）
df = ak.stock_zh_a_spot_em()  # 5000+行
df_single = df[df['代码'] == '300750']
```

### 3.4 深度财务指标 — 标准模式

```python
# 140项深度财务指标
df = ak.stock_financial_analysis_indicator_em(
    symbol='300750.SZ',
    indicator='按报告期'
)
# df.shape → (40, 141) | 40期 × 141个指标列
# 包含: EPS, ROE, ROIC, 毛利率, 资产负债率, 杜邦分析等
```

### 3.5 宏观数据 — 标准模式

```python
# 中国GDP
df = ak.macro_china_gdp_yearly()

# 中国CPI
df = ak.macro_china_cpi_yearly()

# PMI
df = ak.macro_china_pmi()

# LPR利率
df = ak.macro_china_lpr()

# 中美利率对比
df = ak.bond_zh_us_rate()

# 美国非农
df = ak.macro_usa_non_farm()
```

### 3.6 板块数据 — 标准模式

**东方财富数据源**:

```python
# 行业板块实时行情（含涨跌幅/换手率）
df = ak.stock_board_industry_spot_em(symbol='小金属')

# 行业板块成分股列表
df = ak.stock_board_industry_cons_em(symbol='小金属')

# 行业板块日K线
df = ak.stock_board_industry_hist_em(symbol='小金属')

# 行业板块分钟K线
df = ak.stock_board_industry_hist_min_em(symbol='小金属')

# 行业板块名称全列表
df = ak.stock_board_industry_name_em()

# 概念板块实时行情
df = ak.stock_board_concept_spot_em(symbol='新能源')

# 概念板块成分股
df = ak.stock_board_concept_cons_em(symbol='新能源')

# 概念板块日K线
df = ak.stock_board_concept_hist_em(symbol='新能源')

# 概念板块分钟K线
df = ak.stock_board_concept_hist_min_em(symbol='新能源')

# 概念板块名称全列表
df = ak.stock_board_concept_name_em()

# 板块涨跌排行（所有板块一起排序）
df = ak.stock_board_change_em()
```

**同花顺数据源**:

```python
# 行业板块行情汇总（含资金流向等更多维度）
df = ak.stock_board_industry_summary_ths()

# 行业板块指数
df = ak.stock_board_industry_index_ths(symbol='小金属')

# 行业板块基本信息
df = ak.stock_board_industry_info_ths(symbol='小金属')

# 行业板块名称列表（同花顺分类）
df = ak.stock_board_industry_name_ths()

# 概念板块行情汇总
df = ak.stock_board_concept_summary_ths()

# 概念板块指数
df = ak.stock_board_concept_index_ths(symbol='新能源')

# 概念板块基本信息
df = ak.stock_board_concept_info_ths(symbol='新能源')

# 概念板块名称列表（同花顺分类）
df = ak.stock_board_concept_name_ths()
```

### 3.7 资金流向 — 标准模式

```python
# 个股资金流向（大单/中单/小单）
df = ak.stock_individual_fund_flow(stock='300750', market='sz')

# 北向资金汇总
df = ak.stock_hsgt_fund_flow_summary_em()

# 行业资金排名
df = ak.stock_fund_flow_industry(symbol='即时')
```

### 3.8 机构/股东 — 标准模式

```python
# 十大股东
df = ak.stock_gdfx_top_10_em(symbol='300750')

# 机构持仓
df = ak.stock_institute_hold(symbol='300750')

# 机构评级
df = ak.stock_institute_recommend(symbol='300750')

# 股东户数
df = ak.stock_zh_a_gdhs()
```

### 3.9 巨潮资讯 — 官方信息披露

```python
# 公司概况（法人/注册资金/主营业务/上市日期）
df = ak.stock_profile_cninfo('300750')

# IPO上市信息（发行价/发行数量/中签率/承销商）
df = ak.stock_ipo_summary_cninfo('300750')

# 历史分红（历年"10派X元"方案+除权日）
df = ak.stock_dividend_cninfo('300750')

# 股本变动明细（总股本/流通股/限售股）
df = ak.stock_share_change_cninfo('300750')

# 实际控制人持股变动
df = ak.stock_hold_control_cninfo('300750')

# 股权质押
df = ak.stock_cg_equity_mortgage_cninfo(date='20260331')

# 公司诉讼
df = ak.stock_cg_lawsuit_cninfo(symbol='300750')

# 行业归属变动历史
df = ak.stock_industry_change_cninfo('300750')

# 公告查询
df = ak.stock_zh_a_disclosure_report_cninfo('300750', start_date='20260601', end_date='20260626')

# 互动易问答
df = ak.stock_irm_cninfo('300750')

# 新股发行
df = ak.stock_new_ipo_cninfo()

# 基金重仓股
df = ak.fund_report_stock_cninfo(date='20260331')

# 国债发行
df = ak.bond_treasure_issue_cninfo()
```

---

## 四、完整调用模板

### 4.1 统一客户端

```python
import akshare as ak
import pandas as pd
from typing import Optional

class AkshareClient:
    """akshare 统一调用客户端"""
    
    @staticmethod
    def to_code(code: str, fmt: str) -> str:
        """代码格式转换"""
        code = code.strip()
        for p in ['sh', 'sz', 'SH', 'SZ', 'bj', 'BJ']:
            code = code.removeprefix(p)
        
        if fmt == 'pure':
            return code
        elif fmt == 'dot':
            suffix = '.SZ' if code.startswith(('0', '3', '30')) else '.SH'
            return f'{code}{suffix}'
        elif fmt == 'prefix':
            prefix = 'SZ' if code.startswith(('0', '3', '30')) else 'SH'
            return f'{prefix}{code}'
        return code
    
    def financial_abstract(self, code: str) -> pd.DataFrame:
        """80指标×40期财务摘要（核心功能）"""
        return ak.stock_financial_abstract(symbol=self.to_code(code, 'pure'))
    
    def deep_financial(self, code: str) -> pd.DataFrame:
        """140项深度财务指标"""
        return ak.stock_financial_analysis_indicator_em(
            symbol=self.to_code(code, 'dot'), indicator='按报告期'
        )
    
    def kline(self, code: str, period: str = 'daily',
              start: str = '20250101', end: str = '20260626',
              adjust: str = 'qfq') -> pd.DataFrame:
        """历史K线"""
        return ak.stock_zh_a_hist(
            symbol=self.to_code(code, 'pure'),
            period=period, start_date=start, end_date=end, adjust=adjust
        )
    
    def fund_flow(self, code: str, market: str = 'sz') -> pd.DataFrame:
        """个股资金流向"""
        return ak.stock_individual_fund_flow(
            stock=self.to_code(code, 'pure'), market=market
        )
    
    def profit_sheet(self, code: str) -> pd.DataFrame:
        """利润表"""
        return ak.stock_profit_sheet_by_report_em(
            symbol=self.to_code(code, 'prefix')
        )
    
    def balance_sheet(self, code: str) -> pd.DataFrame:
        """资产负债表"""
        return ak.stock_balance_sheet_by_report_em(
            symbol=self.to_code(code, 'prefix')
        )
    
    def cash_flow(self, code: str) -> pd.DataFrame:
        """现金流量表"""
        return ak.stock_cash_flow_sheet_by_report_em(
            symbol=self.to_code(code, 'prefix')
        )
    
    def stock_info(self, code: str) -> pd.DataFrame:
        """个股基本信息"""
        return ak.stock_individual_info_em(
            symbol=self.to_code(code, 'pure')
        )
    
    def top_shareholders(self, code: str) -> pd.DataFrame:
        """十大股东"""
        return ak.stock_gdfx_top_10_em(
            symbol=self.to_code(code, 'pure')
        )
    
    # ===== 巨潮资讯 =====
    def company_profile(self, code: str) -> pd.DataFrame:
        """公司概况（官方）"""
        return ak.stock_profile_cninfo(symbol=code)
    
    def ipo_info(self, code: str) -> pd.DataFrame:
        """IPO上市信息"""
        return ak.stock_ipo_summary_cninfo(symbol=code)
    
    def dividends(self, code: str) -> pd.DataFrame:
        """历史分红"""
        return ak.stock_dividend_cninfo(symbol=code)
    
    def share_changes(self, code: str) -> pd.DataFrame:
        """股本变动"""
        return ak.stock_share_change_cninfo(symbol=code)
    
    def disclosures(self, code: str, start: str, end: str) -> pd.DataFrame:
        """信息披露公告"""
        return ak.stock_zh_a_disclosure_report_cninfo(
            symbol=code, start_date=start, end_date=end
        )
    
    def irm_questions(self, code: str) -> pd.DataFrame:
        """互动易提问"""
        return ak.stock_irm_cninfo(symbol=code)
    
    def industry_changes(self, code: str) -> pd.DataFrame:
        """行业归属变动历史"""
        return ak.stock_industry_change_cninfo(symbol=code)


# ===== 使用示例 =====
client = AkshareClient()

# 财务摘要
df = client.financial_abstract('300750')
print(df[df['指标'] == '营业总收入'].iloc[0, :5])

# 日K线
df = client.kline('300750', period='daily', start='20260601', end='20260626')
print(df.tail(5))

# 个股资金流向
df = client.fund_flow('300750', 'sz')
print(df.head(3))
```

### 4.2 错误处理

```python
import akshare as ak
import time
from typing import Optional

def safe_call(func, *args, retries: int = 2, delay: float = 1.0, **kwargs):
    """带重试的安全调用"""
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
                continue
            print(f"[WARN] {func.__name__} 调用失败: {e}")
            return None

# 使用
df = safe_call(ak.stock_financial_abstract, symbol='300750')
if df is not None:
    print(df.shape)
```

---

## 五、DataFrame 常用处理

### 5.1 提取最新期数据

```python
# stock_financial_abstract: 行=指标, 列=报告期
# 最新期是第2列（索引1）
df = ak.stock_financial_abstract('300750')
latest_col = df.columns[1]  # 如 '20260331'

# 取所有指标的最新值
for _, row in df.iterrows():
    indicator = row['指标']
    value = row[latest_col]
    print(f'{indicator}: {value}')
```

### 5.2 提取多期趋势

```python
df = ak.stock_financial_abstract('300750')
revenue = df[df['指标'] == '营业总收入']

# 所有报告期的营收数据（跳过前2列: '选项', '指标'）
periods = df.columns[2:]  # 从20260331开始
values = revenue.iloc[0, 2:].values

for p, v in zip(periods, values):
    print(f'{p}: {v:.2f}')
```

### 5.3 过滤指定代码

```python
# 全市场行情过滤个股
df_all = ak.stock_zh_a_spot_em()
df_single = df_all[df_all['代码'] == '300750']
```

---

## 六、数据时效性

> 不同数据类型有完全不同的更新节奏，调用前先确认数据是否已到位。

### 6.1 行情数据

| 数据种类 | 数据源后缀 | 更新频率 | 延迟说明 |
|---------|:---------:|:--------:|---------|
| 实时行情（价格/涨跌/盘口） | `_sina` | 盘中连续更新 | **15分钟延迟**，非交易时间定格 |
| 实时行情（价格/涨跌） | `_em` | 盘中连续更新 | **近实时**（3-5秒级），非交易时间定格 |
| 日K线 | `_em` / `_sina` | 每个交易日收盘后更新 | **T+1** 下一个交易日开盘前完成 |
| 分钟K线 | `_em` | 盘中连续更新 | **近实时**，每分钟/5分钟粒度 |
| 全市场实时行情 | `stock_zh_a_spot_em` | 盘中连续更新 | 近实时，5000+只 |
| 分时走势 | `_sina` | 盘中连续更新 | 15分钟延迟 |

### 6.2 财务数据

| 数据种类 | 更新节奏 | 延迟说明 |
|---------|:--------:|---------|
| 财务报表（利润表/资产负债表/现金流） | **按季** | 一季报4月底, 中报8月底, 三季报10月底, 年报次年4月底 |
| 财务摘要（80指标） | **按季** | 同财务报表披露节奏 |
| 财务指标（ROE/EPS等） | **按季** | 同财务报表披露节奏 |
| 业绩预告 | T+0 | 公司发布后即时更新 |
| 业绩快报 | T+0 | 公司发布后即时更新 |
| 分红送配 | T+0 | 公告后即时更新 |
| 历史分红(巨潮) | **按季** | 每次分红实施后更新 |

### 6.3 资金流向

| 数据种类 | 更新频率 | 延迟说明 |
|---------|:--------:|---------|
| 个股资金流向 | **盘中连续更新** | **近实时**，L2数据延迟约3-5秒 |
| 行业资金流向 | **盘中连续更新** | 近实时 |
| 北向资金（沪深港通） | **盘中连续更新** | **近实时**，T+0可查当日 |
| 北向资金历史 | **每日** | T+1或当日盘中 |

### 6.4 板块数据

| 数据种类 | 数据源 | 更新频率 |
|---------|:-------:|:--------:|
| 行业板块行情 | 东方财富（`_em`） | 盘中近实时 |
| 概念板块行情 | 东方财富（`_em`） | 盘中近实时 |
| 板块涨跌排行 | 东方财富（`_em`） | 盘中近实时 |
| 行业板块汇总 | 同花顺（`_ths`） | 盘中近实时 |

### 6.5 宏观数据

| 数据种类 | 更新节奏 | 说明 |
|---------|:--------:|------|
| GDP | **季度**（滞后约1个月） | 1月/4月/7月/10月公布上季 |
| CPI/PPI | **月度**（滞后约10天） | 每月中旬公布上月 |
| PMI | **月度**（当月最后一天） | 采购经理人指数，当月发布 |
| 货币供应(M2) | **月度** | 约每月10-15日公布上月 |
| LPR | **每月20日** | 固定日期 |
| 进出口 | **月度** | 每月中旬公布上月 |
| 美国非农 | **月度**（第一个周五） | 当地时间周五公布上月 |
| 美债收益率 | **交易日频** | 每日更新 |

### 6.6 龙虎榜/异动

| 数据种类 | 更新频率 | 延迟说明 |
|---------|:--------:|---------|
| 龙虎榜 | **每交易日收盘后** | 约 **17:30-18:00** 更新（T+0盘后） |
| 大宗交易 | **每交易日** | 盘后可查当日数据 |
| 涨停板 | **盘中+盘后** | 盘中实时，盘后全量 |

### 6.7 股东/机构/公司治理

| 数据种类 | 更新节奏 | 说明 |
|---------|:--------:|------|
| 十大股东 | **按季** | 滞后约1-3个月 |
| 股东户数 | **按季** | 同季报披露节奏 |
| 机构持仓 | **按季** | 滞后约1-2个月 |
| 机构评级 | 不定期 | 随时更新 |
| 股权质押 | **每日** | 质押登记后更新 |
| 实际控制人变动 | **按季** | 季报更新 |
| 公司概况 | **低频** | 变动极少 |

### 6.8 巨潮资讯（\_cninfo）

| 数据种类 | 更新节奏 | 说明 |
|---------|:--------:|------|
| 公告查询 | **T+0** | 上市公司披露后即时可查 |
| 互动易问答 | **T+0** | 提问/回答后即时更新 |
| 公司概况 | **低频** | 变更时更新 |
| IPO信息 | **每次IPO** | 新股发行期间更新 |
| 行业分类标准 | **按年** | 分类标准调整时更新 |

### 6.9 响应时间参考

| 数据源 | 响应时间 | 并发限制 | 稳定性 |
|--------|:--------:|:--------:|:------:|
| 东方财富(`_em`) | 0.2-1.0s | 一般 | ⭐⭐⭐⭐⭐ |
| 新浪(`_sina`) | 0.1-0.5s | 一般 | ⭐⭐⭐⭐ |
| 同花顺(`_ths`) | 0.3-1.0s | 有频率限制 | ⭐⭐⭐ |
| 雪球(`_xq`) | 0.3-0.8s | 一般 | ⭐⭐⭐⭐ |
| 集思录(`_jsl`) | 0.2-0.5s | 一般 | ⭐⭐⭐⭐ |
| **巨潮资讯(`_cninfo`)** | **0.3-7.0s** | **一般** | **⭐⭐⭐⭐⭐** |

- 第一次调用某个函数时较慢（内部加载模块）
- 建议在循环中调用时加 `time.sleep(0.2)` 避免被封
- 部分东方财富接口在非交易时间响应更快

---

## 七、注意事项

1. **代码格式混用是最大坑**: 见第二章表格，看清楚每个函数需要的代码格式
2. **财务数据的报告期**: 使用 `YYYYMMDD` 格式，如 `20260331` = 2026一季报
3. **A股代码映射**: `stock_info_a_code_name()` → 5528只股票代码-名称对照表
4. **交易日历**: `tool_trade_date_hist_sina()` → 8797个交易日（可查未来日期）
5. **K线复权**: `adjust='qfq'` 前复权, `'hfq'` 后复权, `''` 不复权
6. **数据延迟**: 新浪系延迟15分钟；东方财富系接近实时
7. **限流**: 每秒建议不超过5次连续调用
