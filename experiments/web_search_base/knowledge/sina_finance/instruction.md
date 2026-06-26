# 新浪财经接口调用手册

> 数据来源: 新浪财经免费公开接口 | 数据延迟: ~15 分钟（实时行情）/ 报告期更新（财务报表）
> 请求头要求: 所有接口必须带 `Referer: https://finance.sina.com.cn` 和 `User-Agent: Mozilla/5.0`
> 编码: `hq.sinajs.cn` 返回 `GBK` 编码，需 `r.encoding = 'gbk'` 解码

---

## 一、通用规则

1. **禁止批量请求过快**: 建议单次请求间隔 ≥ 0.2 秒，避免被限流
2. **代码前缀格式**:
   - A 股: `sh600519` / `sz300750` / `sz002594` / `bj835368`
   - 港股: `hk00700` / `hk03690`
   - ETF: `sh510050` / `sz159915`
   - 期货: `rb2410` / `au2412`
3. **数据延迟**: 免费版实时行情延迟约 15 分钟；财务数据按报告期更新
4. **编码处理**: 行情接口需 decode `GBK`；K 线接口是 `UTF-8`

---

## 二、接口清单

| # | 接口名称 | 端点 | 数据格式 | 响应时间 |
|:-:|---------|------|:--------:|:--------:|
| 1 | 实时行情 | `hq.sinajs.cn` | CSV (GBK) | ~0.1s |
| 2 | K 线数据 | `money.finance.sina.com.cn` | JSONP (UTF-8) | ~0.2s |
| 3 | 利润表 | `vip.stock.finance.sina.com.cn` | HTML (GBK) | ~0.3s |
| 4 | 资产负债表 | `vip.stock.finance.sina.com.cn` | HTML (GBK) | ~0.3s |
| 5 | 现金流量表 | `vip.stock.finance.sina.com.cn` | HTML (GBK) | ~0.3s |

---

## 三、实时行情接口

### 端点

```
GET http://hq.sinajs.cn/list={codes}
```

### 参数

- `codes`: 逗号分隔，最多约 50 个（HTTP 无明确限制，但过大会截断）
- 必须带请求头: `Referer: https://finance.sina.com.cn`, `User-Agent: Mozilla/5.0`

### 代码前缀规则

```python
if code.startswith('6'):           prefix = 'sh'
elif code.startswith('0') \
  or code.startswith('3'):         prefix = 'sz'
elif code.startswith('8'):         prefix = 'bj'
elif code.isdigit() and len(code) == 5:  prefix = 'hk'
elif code.startswith('hk'):        # 已带前缀，直接使用
```

### 请求示例

```python
url = 'http://hq.sinajs.cn/list=sh600519,sz300750,sz002594'
headers = {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}
r = requests.get(url, headers=headers, timeout=10)
r.encoding = 'gbk'
```

### 原始响应

```
var hq_str_sz300750="宁德时代,401.000,401.900,382.350,409.810,381.000,382.340,382.350,42808236,16715394482.650,1800,382.340,100,382.320,100,382.310,100,382.300,100,382.280,6300,382.350,3800,382.360,100,382.370,1200,382.380,2500,382.390,2026-06-26,14:41:09,00";
```

### A 股/ETF 字段映射（47 字段，`~` 分隔）

| 字段索引 | 名称 | 类型 | 含义 |
|:-------:|------|:----:|------|
| 0 | name | str | 股票名称 |
| 1 | open | float | 今日开盘价 |
| 2 | prev_close | float | 昨日收盘价 |
| 3 | price | float | 当前价格 |
| 4 | high | float | 今日最高价 |
| 5 | low | float | 今日最低价 |
| 6 | bid_price | float | 买一价 |
| 7 | ask_price | float | 卖一价 |
| 8 | volume | int | 成交量（股数） |
| 9 | amount | float | 成交额（元） |
| 10-19 | 买五~买一 | - | 依次为价格, 数量（五对） |
| 20-29 | 卖一~卖五 | - | 依次为价格, 数量（五对） |
| 30 | date | str | 日期 YYYY-MM-DD |
| 31 | time | str | 时间 HH:MM:SS |

### 港股字段映射（18 字段，`~` 分隔）

| 字段索引 | 名称 | 类型 | 含义 |
|:-------:|------|:----:|------|
| 0 | name_en | str | 英文名称 |
| 1 | name | str | 中文名称 |
| 2 | prev_close | float | 昨收 |
| 3 | open | float | 开盘价 |
| 4 | high | float | 最高价 |
| 5 | low | float | 最低价 |
| 6 | price | float | 当前价 |
| 7 | change | float | 涨跌额 |
| 8 | change_pct | float | 涨跌幅% |
| 9 | bid | float | 买价 |
| 10 | ask | float | 卖价 |
| 11 | amount | float | 成交额 |
| 12 | volume | int | 成交量 |
| 13 | pe | float | 市盈率 |
| 14 | yield | float | 周息率 |
| 15 | market_cap | float | 总市值(亿) |
| 16 | circulate | float | 流通市值(亿) |
| 17 | datetime | str | 日期时间 |

### 已实现的功能（web_search_base/sources/sina.py）

- `fetch_quotes(codes: list[str]) → dict[code, dict]` — 批量获取行情
- `format_quote(code: str, name: str) → str` — 格式化为可读文本（含涨跌幅）

---

## 四、K 线数据接口

### 端点

```
GET http://money.finance.sina.com.cn/quotes_service/api/jsonp_v2.php/var=/CN_MarketData.getKLineData?symbol={symbol}&scale={scale}&ma=no&datalen={count}
```

### 参数

| 参数 | 说明 | 示例 | 支持值 |
|------|------|------|--------|
| symbol | 前缀+代码 | `sz300750` | `sh`/`sz`/`bj` + 代码 |
| scale | 时间粒度 | `30` | `5`, `15`, `30`, `60`, `240` |
| ma | 移动均线 | `no` | 固定值 `no` |
| datalen | 返回条数 | `100` | 正整数，max~1000 |

### 时间粒度

```
scale=5   → 5分钟K线  ✅
scale=15  → 15分钟K线 ✅
scale=30  → 30分钟K线 ✅
scale=60  → 60分钟K线 ✅
scale=240 → 日K线      ✅
```

### 请求示例

```python
url = 'http://money.finance.sina.com.cn/quotes_service/api/jsonp_v2.php/var=/CN_MarketData.getKLineData'
params = {
    'symbol': 'sz300750',
    'scale': '240',      # 日线
    'ma': 'no',
    'datalen': '20',     # 最近20条
}
headers = {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}
r = requests.get(url, params=params, headers=headers, timeout=10)
```

### 原始响应

```json
var=([
    {"day":"2026-06-18","open":"400.390","high":"409.890","low":"389.920","close":"391.550","volume":"38548105"},
    {"day":"2026-06-22","open":"393.000","high":"413.330","low":"386.000","close":"408.980","volume":"59464844"}
]);
```

### 字段映射

| 字段 | 类型 | 含义 |
|------|:----:|------|
| day | str | 时间（日线只显示日期，分时精确到秒） |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| volume | int | 成交量（股数） |

### 解析方法（JSONP → JSON）

```python
import json
# 去除外层 var=( 和 ); 包裹
json_str = r.text[r.text.find('[') : r.text.rfind(']') + 1]
data = json.loads(json_str)  # → list[dict]
```

**尚未实现**，待扩展。

---

## 五、利润表接口

### 端点

```
GET https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/{code}/ctrl/part/displaytype/4.phtml
```

### 参数

- `{code}` = 6 位纯数字代码（无 `sh`/`sz` 前缀），如 `300750`
- `displaytype/4` = 按报告期显示（季度频率）

### 返回

HTML 表格，约 **30 个科目 × 5 个报告期**（最近 5 个季报）

### 解析方式

```python
import re, requests

url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/{code}/ctrl/part/displaytype/4.phtml'
headers = {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}
r = requests.get(url, headers=headers, timeout=10)
r.encoding = 'gbk'

# 找到最后一个含"报表日期"的表格
tables = re.findall(r'<table[^>]*>(.*?)</table>', r.text, re.DOTALL)
for table in tables:
    if '报表日期' in table:
        rows = re.findall(r'<tr>(.*?)</tr>', table, re.DOTALL)
        for row in rows:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row)
            texts = [re.sub(r'<[^>]*>', '', c).strip() for c in cells]
            # texts[0] = 科目名, texts[1..5] = 各报告期数值（万元）
```

### 科目行结构

```
行0: "报表日期" + 5 个日期（如 2026-03-31, 2025-12-31, ...）
行1: 一、营业总收入
行2:   营业收入
行3: 二、营业总成本
行4:   营业成本
行5:   营业税金及附加
行6:   销售费用
行7:   管理费用
行8:   财务费用
行9:   研发费用
行10:  资产减值损失
行11: 公允价值变动收益
行12: 投资收益
行13:   其中:对联营企业...
行14: 三、营业利润
行15: 加:营业外收入
行16: 减:营业外支出
行17: 四、利润总额
行18: 减:所得税费用
行19: 五、净利润
行20:   归属于母公司所有者的净利润
行21:   少数股东损益
行22: 六、每股收益
行23:   基本每股收益(元/股)
行24:   稀释每股收益(元/股)
行25: 七、其他综合收益
```

**单位**: 万元 | **暂未实现**

---

## 六、资产负债表接口

### 端点

```
GET https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/{code}/ctrl/part/displaytype/4.phtml
```

### 参数

- `{code}` = 6 位纯数字代码，如 `300750`

### 返回

HTML 表格，约 **96 个科目 × 5 个报告期**

### 解析方式

同上（`_parse_financial_table(url)` 通用解析器）

### 科目行结构

```
行0: "报表日期" + 5 个日期
行1: 流动资产
行2:   货币资金
行3:   交易性金融资产
行4:   应收票据及应收账款
行5:   预付款项
行6:   存货
行7:   其他流动资产
行8:   流动资产合计
行9: 非流动资产
行10:  固定资产
行11:  在建工程
行12:  无形资产
行13:  商誉
行14:  长期股权投资
行15:  非流动资产合计
行16: 资产总计
行17: 流动负债
行18:  短期借款
行19:  应付票据及应付账款
行20:  合同负债
行21:  应付职工薪酬
行22:  应交税费
行23:  流动负债合计
行24: 非流动负债
行25:  长期借款
行26:  应付债券
行27:  非流动负债合计
行28: 负债合计
行29: 所有者权益
行30:  实收资本(股本)
行31:  资本公积
行32:  未分配利润
行33:  归属于母公司股东权益合计
行34:  少数股东权益
行35:  所有者权益合计
行36: 负债和所有者权益总计
```

**单位**: 万元 | **暂未实现**

---

## 七、现金流量表接口

### 端点

```
GET https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_CashFlow/stockid/{code}/ctrl/part/displaytype/4.phtml
```

### 参数

- `{code}` = 6 位纯数字代码，如 `300750`

### 返回

HTML 表格，约 **78 个科目 × 5 个报告期**

### 科目行结构

```
行0: "报表日期" + 5 个日期
行1: 一、经营活动产生的现金流量
行2:   销售商品、提供劳务收到的现金
行3:   收到的税费返还
行4:   收到其他与经营活动有关的现金
行5:   经营活动现金流入小计
行6:   购买商品、接受劳务支付的现金
行7:   支付给职工以及为职工支付的现金
行8:   支付的各项税费
行9:   支付其他与经营活动有关的现金
行10:  经营活动现金流出小计
行11:  经营活动产生的现金流量净额
行12: 二、投资活动产生的现金流量
行13:  收回投资收到的现金
...
行N:   投资活动产生的现金流量净额
行N+1: 三、筹资活动产生的现金流量
...
行M:   筹资活动产生的现金流量净额
行M+1: 四、汇率变动对现金的影响
行M+2: 五、现金及现金等价物净增加额
行M+3: 六、期初现金及现金等价物余额
行M+4: 七、期末现金及现金等价物余额
```

**单位**: 万元 | **暂未实现**

---

## 八、代码调用样板

### 8.1 完整调用模板

```python
import requests
import re
import json

class SinaFinanceClient:
    """新浪财经数据客户端"""
    
    BASE_HEADERS = {
        'Referer': 'https://finance.sina.com.cn',
        'User-Agent': 'Mozilla/5.0',
    }
    
    @staticmethod
    def _to_sina_code(code: str) -> str:
        """6位代码 → 新浪格式"""
        if code.startswith('6'):
            return f'sh{code}'
        elif code.startswith(('0', '3')):
            return f'sz{code}'
        elif code.startswith('8'):
            return f'bj{code}'
        elif code.startswith('hk'):
            return code  # 已带前缀
        return f'sz{code}'
    
    def fetch_quotes(self, codes: list[str]) -> dict[str, dict]:
        """批量实时行情"""
        sina_codes = ','.join(self._to_sina_code(c) for c in codes)
        url = f'http://hq.sinajs.cn/list={sina_codes}'
        r = requests.get(url, headers=self.BASE_HEADERS, timeout=10)
        r.encoding = 'gbk'
        
        result = {}
        for line in r.text.strip().split(';'):
            if '=' not in line or '"' not in line:
                continue
            # 从变量名提取股票代码
            var_name = line.split('=')[0].split('_')[-1]
            code = var_name[2:] if len(var_name) > 2 else var_name
            
            fields = line.split('"')[1].split(',')
            if len(fields) >= 32:
                # A股格式解析
                result[code] = {
                    'name': fields[0],
                    'open': float(fields[1]),
                    'prev_close': float(fields[2]),
                    'price': float(fields[3]),
                    'high': float(fields[4]),
                    'low': float(fields[5]),
                    'volume': int(fields[8]),
                    'amount': float(fields[9]),
                    'date': fields[30],
                    'time': fields[31],
                }
            elif len(fields) >= 17:
                # 港股格式解析
                result[code] = {
                    'name': fields[1],
                    'price': float(fields[6]),
                    'change': float(fields[7]),
                    'change_pct': float(fields[8]),
                    'market_cap': float(fields[15]),
                    'pe': float(fields[13]),
                }
        return result
    
    def fetch_kline(self, code: str, scale: int = 240, count: int = 20) -> list[dict]:
        """K线数据"""
        symbol = self._to_sina_code(code)
        url = 'http://money.finance.sina.com.cn/quotes_service/api/jsonp_v2.php/var=/CN_MarketData.getKLineData'
        params = {'symbol': symbol, 'scale': scale, 'ma': 'no', 'datalen': count}
        r = requests.get(url, params=params, headers=self.BASE_HEADERS, timeout=10)
        json_str = r.text[r.text.find('['):r.text.rfind(']') + 1]
        return json.loads(json_str)
    
    def _parse_financial_table(self, url: str) -> list[list[str]]:
        """通用财务表格解析器"""
        r = requests.get(url, headers=self.BASE_HEADERS, timeout=10)
        r.encoding = 'gbk'
        tables = re.findall(r'<table[^>]*>(.*?)</table>', r.text, re.DOTALL)
        for table in tables:
            if '报表日期' not in table:
                continue
            rows = re.findall(r'<tr>(.*?)</tr>', table, re.DOTALL)
            result = []
            for row in rows:
                cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row)
                texts = [re.sub(r'<[^>]*>', '', c).strip() for c in cells]
                if texts and texts[0]:
                    result.append(texts)
            return result
        return []
    
    def fetch_profit_statement(self, code: str) -> list[list[str]]:
        """利润表"""
        url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/{code}/ctrl/part/displaytype/4.phtml'
        return self._parse_financial_table(url)
    
    def fetch_balance_sheet(self, code: str) -> list[list[str]]:
        """资产负债表"""
        url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/{code}/ctrl/part/displaytype/4.phtml'
        return self._parse_financial_table(url)
    
    def fetch_cash_flow(self, code: str) -> list[list[str]]:
        """现金流量表"""
        url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_CashFlow/stockid/{code}/ctrl/part/displaytype/4.phtml'
        return self._parse_financial_table(url)


# ===== 使用示例 =====
client = SinaFinanceClient()

# 实时行情
quotes = client.fetch_quotes(['300750', '600519'])
print(quotes['300750']['price'])  # → 382.35

# 日K线
kline = client.fetch_kline('300750', scale=240, count=10)

# 利润表
income = client.fetch_profit_statement('300750')
# income[0] = ["报表日期", "2026-03-31", "2025-12-31", ...]
# income[1] = ["一、营业总收入", "12913104.10", "42370183.40", ...]
```

---

## 七、数据时效性

### 7.1 实时行情

| 数据 | 更新频率 | 延迟说明 |
|------|:--------:|---------|
| A股实时行情（价格/涨跌/盘口） | 盘中连续更新 | **15分钟延迟** |
| 港股实时行情 | 盘中连续更新 | **15分钟延迟** |
| ETF实时行情 | 盘中连续更新 | **15分钟延迟** |

**非交易时间**: 收盘后行情数据定格在收盘价，盘口字段清空。

### 7.2 K线数据

| 时间粒度 | 更新时机 | 说明 |
|---------|:--------:|------|
| 5分钟K线 | 盘中每5分钟生成 | 延迟15分钟 |
| 15分钟K线 | 盘中每15分钟生成 | 延迟15分钟 |
| 30分钟K线 | 盘中每30分钟生成 | 延迟15分钟 |
| 60分钟K线 | 盘中每60分钟生成 | 延迟15分钟 |
| 日K线 | 每日收盘后 | T+0盘后约17:00可查 |

### 7.3 财务报表

| 报表类型 | 更新节奏 | 法定截止日期 |
|---------|:--------:|:------------:|
| 一季报 | 每年4月30日前 | 4月30日 |
| 中报（半年报） | 每年8月31日前 | 8月31日 |
| 三季报 | 每年10月31日前 | 10月31日 |
| 年报 | 次年4月30日前 | 4月30日 |

**数据覆盖**: 最近 **5 个报告期**。
**同步延迟**: 公司公告后 **1-2 个交易日**内同步。

### 7.4 响应时间

| 接口 | 响应时间 |
|------|:--------:|
| 实时行情（hq.sinajs.cn） | ~0.1s |
| K线数据 | ~0.2s |
| 三大报表（HTML） | ~0.3s |

---

### 8.2 当前实现状态

```
web_search_base/sources/sina.py
  ├── fetch_quotes()     ✅ 已实现 — A股 + ETF 实时行情
  ├── format_quote()     ✅ 已实现 — 格式化输出（含涨跌幅）
  ├── fetch_kline()              🔲 待扩展
  ├── fetch_profit_statement()   🔲 待扩展
  ├── fetch_balance_sheet()      🔲 待扩展
  ├── fetch_cash_flow()          🔲 待扩展
  └── fetch_hk_quotes()          🔲 待扩展
```
