# 腾讯财经接口调用手册

> 端点: `https://web.sqt.gtimg.cn/q={code}`
> 类型: REST API（HTTP GET），返回 `~` 分隔的纯文本
> 特点: 免费、无需 Token、近实时、88字段含估值

---

## 一、通用规则

1. **代码前缀**: 上海 `sh` + 代码，深圳 `sz` + 代码
   ```python
   'sh' if code.startswith('6') else 'sz'
   ```
2. **批量请求**: 逗号分隔，如 `sz300750,sh600519,sz002594`
3. **编码**: UTF-8，无需特殊处理
4. **数据延迟**: 接近实时（无15分钟延迟）
5. **无 Token**: 直接 HTTP GET，无需任何认证

---

## 二、接口规范

### 端点

```
GET https://web.sqt.gtimg.cn/q=sz300750,sh600519
```

### 请求

```python
import requests

url = 'https://web.sqt.gtimg.cn/q=sz300750,sz002594'
headers = {'User-Agent': 'Mozilla/5.0'}
r = requests.get(url, headers=headers, timeout=10)
```

### 原始响应

```
v_sz300750="51~宁德时代~300750~381.00~401.90~401.00~465253~203694...";
v_sz002594="51~比亚迪~002594~78.20~82.20~81.51~663208~106500...";
```

每只股票一行，`~` 分隔 88 个字段，以 `";\n"` 结束。

### 解析方式

```python
for line in r.text.strip().split(';'):
    if '~' not in line:
        continue
    fields = line.split('~')
    result = {
        'name':           fields[1],     # 股票名称
        'code':           fields[2],     # 股票代码
        'price':          fields[3],     # 当前价
        'prev_close':     fields[4],     # 昨收
        'open':           fields[5],     # 开盘
        'volume':         fields[6],     # 成交量
        'amount_wan':     fields[37],    # 成交额(万)
        'high':           fields[41],    # 最高
        'low':            fields[42],    # 最低
        'turnover_rate':  fields[38],    # 换手率%
        'pe_dynamic':     fields[39],    # 市盈率(动)
        'amplitude':      fields[43],    # 振幅%
        'market_cap_total':  fields[44], # 总市值(亿)
        'market_cap_flow':   fields[45], # 流通市值(亿)
        'pb':             fields[46],    # 市净率
    }
```

---

## 三、完整代码调用

### 3.1 已实现（web_search_base/sources/tencent.py）

```python
from sources.tencent import fetch_quotes, format_quote

# 批量获取
quotes = fetch_quotes(['300750', '002594'])

# 获取单只
q = quotes.get('300750', {})
price = float(q['price'])
pe = q.get('pe_dynamic', 'N/A')
mc = q.get('market_cap_total', 'N/A')

# 格式化输出
text = format_quote('300750', '宁德时代')
print(text)
```

### 3.2 统一客户端模板

```python
import requests

class TencentFinanceClient:
    """腾讯财经统一客户端"""
    
    URL = 'https://web.sqt.gtimg.cn/q='
    HEADERS = {'User-Agent': 'Mozilla/5.0'}
    
    @staticmethod
    def _tencent_code(code: str) -> str:
        return f'sh{code}' if code.startswith('6') else f'sz{code}'
    
    def fetch_quotes(self, codes: list[str]) -> dict[str, dict]:
        """批量获取行情+估值"""
        tcodes = ','.join(self._tencent_code(c) for c in codes)
        r = requests.get(f'{self.URL}{tcodes}', headers=self.HEADERS, timeout=10)
        
        result = {}
        for line in r.text.strip().split(';'):
            if '~' not in line:
                continue
            fields = line.split('~')
            if len(fields) < 47:
                continue
            code = fields[2]
            result[code] = {
                'name': fields[1],
                'price': fields[3],
                'prev_close': fields[4],
                'open': fields[5],
                'high': fields[41],
                'low': fields[42],
                'turnover_rate': fields[38],
                'pe_dynamic': fields[39],
                'pb': fields[46],
                'market_cap_total': fields[44],
                'market_cap_flow': fields[45],
                'amplitude': fields[43],
                'amount_wan': fields[37],
                'volume_ratio': fields[49],
                'limit_up': fields[47],
                'limit_down': fields[48],
            }
        return result
    
    def format_quote(self, code: str, name: str) -> str:
        """格式化为可读文本"""
        quotes = self.fetch_quotes([code])
        q = quotes.get(code, {})
        
        price = float(q.get('price', 0))
        prev = float(q.get('prev_close', 0))
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0
        
        lines = [
            f"{name}({code}) 实时行情与估值",
            f"  当前价: {q.get('price', 'N/A')}",
            f"  涨跌幅: {change:+.2f} ({change_pct:+.2f}%)",
            f"  最高/最低: {q.get('high', 'N/A')} / {q.get('low', 'N/A')}",
            f"  总市值: {q.get('market_cap_total', 'N/A')}亿",
            f"  流通市值: {q.get('market_cap_flow', 'N/A')}亿",
            f"  市盈率(动): {q.get('pe_dynamic', 'N/A')}",
            f"  市净率: {q.get('pb', 'N/A')}",
            f"  换手率: {q.get('turnover_rate', 'N/A')}%",
            f"  量比: {q.get('volume_ratio', 'N/A')}",
            f"  成交额: {q.get('amount_wan', 'N/A')}万",
            f"\n(来源: 腾讯财经)",
        ]
        return '\n'.join(lines)


# ===== 使用示例 =====
client = TencentFinanceClient()
quotes = client.fetch_quotes(['300750', '002594'])
print(quotes['300750']['pe_dynamic'])  # → 22.32
print(client.format_quote('300750', '宁德时代'))
```

---

## 四、字段索引速查卡

```
fields[ 1] = name             股票名称
fields[ 2] = code             股票代码
fields[ 3] = price            当前价        ★
fields[ 4] = prev_close       昨收
fields[ 5] = open             开盘价
fields[ 6] = volume           成交量
fields[ 7] = amount_wan_orig  成交额(万)(原始)
fields[30] = datetime         YYYYMMDDHHMMSS
fields[31] = chg              涨跌额
fields[32] = chg_pct          涨跌幅%       ★
fields[33] = high             最高价
fields[34] = low              最低价
fields[37] = amount           成交额(万)    ★
fields[38] = turnover_rate    换手率%       ★
fields[39] = pe_dynamic       市盈率(动态)  ★
fields[41] = high_dup         最高价(重复)
fields[42] = low_dup          最低价(重复)
fields[43] = amplitude        振幅%         ★
fields[44] = market_cap_total 总市值(亿)    ★
fields[45] = market_cap_flow  流通市值(亿)  ★
fields[46] = pb               市净率        ★
fields[47] = limit_up         涨停价
fields[48] = limit_down       跌停价
fields[49] = volume_ratio     量比          ★
```

---

## 四、数据时效性

### 4.1 实时行情

| 字段 | 更新频率 | 延迟说明 |
|------|:--------:|---------|
| 价格 / 涨跌幅 / 涨跌额 | 盘中连续更新 | **近实时**（3-5秒级） |
| 总市值 / 流通市值 | 盘中连续更新 | 随股价实时变动 |
| 市盈率(动态) | 盘中连续更新 | 随股价变动（PE = 股价 / EPS） |
| 市净率 | 盘中连续更新 | 随股价变动 |
| 换手率 | 盘中连续更新 | 随成交量变动 |
| 量比 | 盘中连续更新 | 实时计算 |
| 最高/最低价 | 盘中连续更新 | 当日累计 |
| 成交额 | 盘中连续更新 | 当日累计 |

**非交易时间**: 所有字段定格在收盘最后一口数据，不更新。
**盘后数据**: 无盘后数据。与东方财富不同，腾讯无盘后固定价格。

### 4.2 数据特点

| 对比项 | 腾讯财经 | 新浪财经 |
|--------|:--------:|:--------:|
| 数据延迟 | **近实时**（3-5秒） | **15分钟延迟** |
| 非交易时段 | 定格 | 定格 |
| 估值字段 | ✅ PE/PB/市值 | ❌ 无 |

### 4.3 响应时间

| 操作 | 响应时间 |
|------|:--------:|
| 单只股票查询 | ~0.1s |
| 批量查询（3只） | ~0.15s |
| 批量查询（10只） | ~0.3s |

---

## 五、当前集成状态

```
web_search_base/sources/tencent.py
  ├── fetch_quotes()     ✅ 已实现 — 批量行情+估值
  └── format_quote()     ✅ 已实现 — 格式化输出
```

已全部实现，无需扩展。
