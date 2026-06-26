# pysnowball 接口调用手册

> 版本: 0.1.8 | 安装: `pip install pysnowball`
> 需配合 Token 使用（见同目录 `token.md`）

---

## 一、安装与基础

### 1.1 安装

```bash
pip install pysnowball
```

### 1.2 设置 Token

```python
import pysnowball as ball

# 将 token.md 中的值填入
ball.set_token("xq_a_token=xxx; u=yyy")
```

### 1.3 代码格式

雪球统一使用 `SH`/`SZ` 前缀 + 6位数字代码：

```
上海: SH600519
深圳: SZ300750
北京: BJ835368
港股: HK00700
```

---

## 二、接口调用规范

### 2.1 通用规则

1. **所有接口返回 dict**，含 `error_code` / `error_description` / `data` 三层结构
2. **需要 Token 的接口如果 Token 过期**，返回 `error_code: 400016` — "遇到错误，请刷新页面或者重新登录"
3. **无需 Token 的接口**：`quotec`（行情）、`pankou`（盘口）— 仅需模拟浏览器 Cookie
4. 建议单次请求间隔 ≥ 0.3 秒

### 2.2 返回值结构

```python
{
    "data": { ... },          # 实际数据
    "error_code": 0,          # 0=成功, 非0=失败
    "error_description": ""   # 错误描述
}
```

### 2.3 无需 Token 的调用方式

```python
import requests as rq

s = rq.Session()
headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://xueqiu.com'}
s.get('https://xueqiu.com', headers=headers, timeout=10)

# 行情
r = s.get('https://stock.xueqiu.com/v5/stock/realtime/quotec.json?symbol=SZ300750,SH600519', headers=headers, timeout=10)
data = r.json()
price = data['data'][0]['current']

# 盘口
r = s.get('https://stock.xueqiu.com/v5/stock/realtime/pankou.json?symbol=SZ300750', headers=headers, timeout=10)
bid = r.json()['data']['bp1']  # 买一价
```

---

## 三、完整调用模板

### 3.1 统一客户端

```python
import pysnowball as ball
from typing import Optional

# ===== Token 设置 =====
# 从 knowledge/pysnowball/token.md 读取
ball.set_token("xq_a_token=xxx; u=yyy")


class XueqiuClient:
    """雪球数据统一客户端"""

    @staticmethod
    def to_xq_code(code: str) -> str:
        """转换为雪球代码格式"""
        code = code.strip()
        for p in ['sh', 'sz', 'SH', 'SZ', 'bj', 'BJ']:
            code = code.removeprefix(p)
        if code.startswith(('6', '9')):
            return f'SH{code}'
        elif code.startswith(('0', '3')):
            return f'SZ{code}'
        elif code.startswith('8'):
            return f'BJ{code}'
        return f'SZ{code}'

    # ----- 行情 -----
    def quote(self, code: str) -> dict:
        """获取实时行情 + 估值（无需Token也能获取部分数据）"""
        xq_code = self.to_xq_code(code)
        return ball.quotec(xq_code)

    def quote_detail(self, code: str) -> Optional[dict]:
        """详细行情（含PE/PB/EPS/股息率/52周高低的完整数据）"""
        xq_code = self.to_xq_code(code)
        data = ball.quote_detail(xq_code)
        if data.get('error_code') == 0:
            return data['data']
        return None

    def kline(self, code: str, period: str = 'day', count: int = 120) -> Optional[list]:
        """K线数据（含PE/PB/市值历史曲线）"""
        xq_code = self.to_xq_code(code)
        data = ball.kline(xq_code, period=period, count=count)
        if data.get('error_code') == 0:
            return data['data']
        return None

    # ----- 财务 -----
    def income(self, code: str, annals: bool = True, count: int = 4) -> Optional[list]:
        """利润表"""
        xq_code = self.to_xq_code(code)
        data = ball.income(xq_code, is_annals=int(annals), count=count)
        if data.get('error_code') == 0:
            return data['data']['list']
        return None

    def balance(self, code: str, annals: bool = True, count: int = 4) -> Optional[list]:
        """资产负债表"""
        xq_code = self.to_xq_code(code)
        data = ball.balance(xq_code, is_annals=int(annals), count=count)
        if data.get('error_code') == 0:
            return data['data']['list']
        return None

    def cash_flow(self, code: str, annals: bool = True, count: int = 4) -> Optional[list]:
        """现金流量表"""
        xq_code = self.to_xq_code(code)
        data = ball.cash_flow(xq_code, is_annals=int(annals), count=count)
        if data.get('error_code') == 0:
            return data['data']['list']
        return None

    def indicator(self, code: str, annals: bool = True, count: int = 4) -> Optional[list]:
        """财务指标（ROE/EPS/毛利率等）"""
        xq_code = self.to_xq_code(code)
        data = ball.indicator(xq_code, is_annals=int(annals), count=count)
        if data.get('error_code') == 0:
            return data['data']['list']
        return None

    def main_indicator(self, code: str) -> Optional[dict]:
        """主要指标一览（一屏看完PE/PB/ROE/毛利率等）"""
        xq_code = self.to_xq_code(code)
        data = ball.main_indicator(xq_code)
        if data.get('error_code') == 0 and data.get('data', {}).get('items'):
            return data['data']['items'][0]
        return None

    # ----- 资金 -----
    def capital_flow(self, code: str) -> Optional[list]:
        """当日资金流向（逐分钟）"""
        xq_code = self.to_xq_code(code)
        data = ball.capital_flow(xq_code)
        if data.get('error_code') == 0:
            return data['data'].get('items', [])
        return None

    def capital_history(self, code: str, count: int = 20) -> Optional[dict]:
        """历史资金流向"""
        xq_code = self.to_xq_code(code)
        data = ball.capital_history(xq_code, count=count)
        if data.get('error_code') == 0:
            return data['data']
        return None

    def capital_assort(self, code: str) -> Optional[dict]:
        """资金细分（大单/中单/小单）"""
        from pysnowball.capital import capital_assort
        xq_code = self.to_xq_code(code)
        data = capital_assort(xq_code)
        if data.get('error_code') == 0:
            return data['data']
        return None

    # ----- 股东 -----
    def top_holders(self, code: str) -> Optional[dict]:
        """十大股东"""
        xq_code = self.to_xq_code(code)
        data = ball.top_holders(xq_code)
        if data.get('error_code') == 0:
            return data['data']
        return None

    def org_holding_change(self, code: str) -> Optional[list]:
        """机构持仓变动历史"""
        xq_code = self.to_xq_code(code)
        data = ball.org_holding_change(xq_code)
        if data.get('error_code') == 0:
            return data['data'].get('items', [])
        return None

    # ----- 行业 -----
    def industry(self, code: str) -> Optional[dict]:
        """行业归属 + 概念板块（★ 股票→概念聚类）"""
        xq_code = self.to_xq_code(code)
        data = ball.industry(xq_code)
        if data.get('error_code') == 0:
            return data['data']
        return None
    
    @staticmethod
    def common_concepts(codes: list[str]) -> dict:
        """批量聚类：给一堆股票，找出它们共同归属的概念板块"""
        client = XueqiuClient()
        all_concepts = {}
        for code in codes:
            data = client.industry(code)
            if data and 'concept' in data:
                all_concepts[code] = set(c['ind_name'] for c in data['concept'])
        
        # 取所有股票都有的共同概念
        common = None
        for code, concepts in all_concepts.items():
            if common is None:
                common = concepts
            else:
                common &= concepts
        
        return {
            'stock_concepts': all_concepts,
            'common_concepts': sorted(common) if common else [],
        }

    def industry_compare(self, code: str) -> Optional[dict]:
        """行业估值对比"""
        xq_code = self.to_xq_code(code)
        data = ball.industry_compare(xq_code)
        if data.get('error_code') == 0:
            return data['data']
        return None

    # ----- 交易数据 -----
    def margin(self, code: str) -> Optional[list]:
        """融资融券余额"""
        xq_code = self.to_xq_code(code)
        data = ball.margin(xq_code)
        if data.get('error_code') == 0:
            return data['data'].get('items', [])
        return None

    def blocktrans(self, code: str) -> Optional[list]:
        """大宗交易"""
        xq_code = self.to_xq_code(code)
        data = ball.blocktrans(xq_code)
        if data.get('error_code') == 0:
            return data['data'].get('items', [])
        return None

    def bonus(self, code: str) -> Optional[list]:
        """分红记录"""
        xq_code = self.to_xq_code(code)
        data = ball.bonus(xq_code)
        if data.get('error_code') == 0:
            return data['data'].get('items', [])
        return None

    # ----- 搜索 -----
    def search(self, keyword: str) -> Optional[list]:
        """股票搜索（中文→代码）"""
        data = ball.suggest_stock(keyword)
        if data.get('success'):
            return data['data']
        return None


# ===== 使用示例 =====
client = XueqiuClient()

# 详细行情（含PE/PB/市值）
detail = client.quote_detail('300750')
if detail:
    quote = detail['quote']
    print(f"PE: {quote.get('pe_ttm')}, PB: {quote.get('pb')}, "
          f"市值: {quote.get('market_capital')}")

# 利润表
income = client.income('300750', annals=True, count=4)
if income:
    for r in income:
        print(f"{r['report_name']}: 营收{r['total_revenue']}, 净利{r['net_profit']}")

# 行业估值对比
comp = client.industry_compare('300750')
if comp:
    print(f"行业: {comp.get('ind_name')}, 行业平均PE: {comp.get('avg', {}).get('pe_ttm')}")

# 资金细分
assort = client.capital_assort('300750')
if assort:
    net_large = assort['buy_large'] - assort['sell_large']
    print(f"大单净额: {net_large}")

# ★ 概念板块聚类：找出多只股票的共同概念
result = XueqiuClient.common_concepts(['300750', '002594', '300124'])
print(f"共同概念板块: {result['common_concepts']}")
for code, concepts in result['stock_concepts'].items():
    print(f"  {code}: {sorted(concepts)[:5]}...")
```

### 3.2 错误处理

```python
import pysnowball as ball
from typing import Optional

def safe_xueqiu_call(func, *args, **kwargs) -> Optional[dict]:
    """雪球 API 安全调用"""
    try:
        data = func(*args, **kwargs)
        if isinstance(data, dict):
            if data.get('error_code') != 0:
                err = data.get('error_description', '未知错误')
                print(f"[WARN] 雪球API返回错误: {err}")
                return None
        return data
    except Exception as e:
        print(f"[WARN] 雪球API调用失败: {e}")
        return None

# 使用
data = safe_xueqiu_call(ball.quote_detail, 'SZ300750')
if data:
    print(data['data']['quote']['pe_ttm'])
```

---

## 四、数据时效性

### 4.1 行情数据（quotec / quote_detail）

| 数据 | 更新频率 | 延迟说明 |
|------|:--------:|---------|
| 价格 / 涨跌幅 / 涨跌额 | 盘中连续更新 | **近实时**（3-5秒级） |
| 总市值 / 流通市值 | 盘中连续更新 | 随股价实时变动 |
| 市盈率(PE_TTM) | 盘中连续更新 | 随股价变动 |
| 市净率(PB) | 盘中连续更新 | 随股价变动 |
| 52周高/低 | 每日更新 | 每日收盘后更新 |
| 股息率(dividend_yield) | 公告后更新 | 分红方案实施后更新 |
| 换手率 / 量比 | 盘中连续更新 | 实时计算 |
| 年初至今涨幅 | 盘中连续更新 | 实时计算 |

**非交易时间**: 行情数据定格在收盘最后一口。

### 4.2 K线数据（kline）

| 周期 | 更新时机 |
|------|:--------:|
| 日K线 | 每个交易日收盘后（约16:00完成） |
| 周K线 | 每周五收盘后 |
| 月K线 | 每月最后一个交易日收盘后 |

**K线附带数据**: 每根K线同时返回 PE / PB / PS / PCF / 市值 / 融资余额 / 北向持股，这些估值字段按日频更新。

### 4.3 财务数据（income / balance / cash_flow / indicator）

| 报告类型 | 更新节奏 | 法定截止日期 |
|---------|:--------:|:------------:|
| 一季报 | 每年4月30日前 | 4月30日 |
| 中报（半年报） | 每年8月31日前 | 8月31日 |
| 三季报 | 每年10月31日前 | 10月31日 |
| 年报 | 次年4月30日前 | 4月30日 |

**同步延迟**: 雪球一般在公司公告后 1-2 个交易日内完成数据同步。
**数据覆盖**: 通过 `count` 参数控制返回期数（默认10期）。

### 4.4 资金流向

| 数据 | 更新频率 | 说明 |
|------|:--------:|------|
| 当日资金流向（capital_flow） | **盘中逐分钟** | 近实时，每分钟更新 |
| 历史资金流向（capital_history） | **每交易日** | 每日收盘后更新 |
| 资金细分（capital_assort） | **每交易日** | 每日收盘后统计 |
| 融资融券（margin） | **每交易日** | 每日收盘后更新 |

### 4.5 股东/持仓数据

| 数据 | 更新节奏 | 说明 |
|------|:--------:|------|
| 十大股东 | **按季** | 滞后约1-3个月 |
| 机构持仓变动 | **按季** | 滞后约1-2个月 |
| 分红记录 | 公告后 | 分红方案公告后更新 |

### 4.6 行业数据

| 数据 | 更新节奏 | 说明 |
|------|:--------:|------|
| 行业归属 + 概念板块 | **按季** | 随成分股调整更新 |
| 行业估值对比 | **按季** | 基于最新财务报告 |

### 4.7 响应时间

| 接口 | Token需求 | 响应时间 |
|------|:--------:|:--------:|
| quotec | ❌ 免Token | ~0.1s |
| pankou | ❌ 免Token | ~0.1s |
| quote_detail | ✅ | ~0.2s |
| kline | ✅ | ~0.3s |
| income/balance/cash_flow | ✅ | ~0.3s |
| capital_flow/history | ✅ | ~0.3s |
| top_holders | ✅ | ~0.3s |
| industry/industry_compare | ✅ | ~0.3s |

---

## 五、Token 过期处理

Token 有效期 **7-30 天**，过期时所有需要 Token 的接口返回:

```json
{"error_code": 400016, "error_description": "遇到错误，请刷新页面或者重新登录帐号后再试"}
```

此时需要:
1. 打开浏览器登录 `xueqiu.com`
2. F12 → Application → Cookies → `xq_a_token` 复制新值
3. 更新 `knowledge/pysnowball/token.md`

---

## 五、当前集成状态

```
web_search_base/sources/                  (尚未创建雪球模块)
  └── xueqiu.py     🔲 待创建 — 雪球数据源
      ├── fetch_quote(code)           🔲 行情含估值
      ├── fetch_kline(code)           🔲 K线含PE/PB
      ├── fetch_income(code)          🔲 利润表
      ├── fetch_balance(code)         🔲 资产负债表
      ├── fetch_cash_flow(code)       🔲 现金流量表
      ├── fetch_indicator(code)       🔲 财务指标
      ├── fetch_capital_assort(code)  🔲 资金流向细分
      ├── fetch_top_holders(code)     🔲 十大股东
      ├── fetch_industry_compare(code)🔲 行业估值对比
      └── fetch_margin(code)          🔲 融资融券
```
