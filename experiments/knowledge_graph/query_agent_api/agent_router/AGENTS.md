# AGENTS.md — 字段筛选工作流程

## 你的输入

你会收到两部分信息：

### 1. 取数请求（你要服务的目标）

```json
{
    "req_id": "R_001",
    "obj": ["宁德时代"],
    "var": "涨跌幅",
    "condition": ["今天"]
}
```

各字段的含义：
- **obj**：取数对象（股票名/板块名/指数名）
- **var**：取数指标
- **condition**：限制条件（时间、复权方式等）

### 2. 路由候选列表（系统已经查好的）

```json
[
    {
        "id": "FIELD_QUOTE_PCT_CHG",
        "name": "个股涨跌幅",
        "match": "qualified",
        "time_gran": "实时",
        "scope": "个股级别",
        "ds_name": "Tushare日线",
        "protocol": "tushare"
    },
    {
        "id": "FIELD_INDEX_PCT_CHG",
        "name": "指数涨跌幅",
        "match": "simple",
        "time_gran": "日频",
        "scope": "指数级别",
        "ds_name": "Tushare指数",
        "protocol": "tushare"
    }
]
```

每个候选字段属性的含义：

| 属性 | 含义 | 选段依据 |
|------|------|---------|
| **id** | 字段唯一代号。命名前缀暗示类型：`QUOTE`=行情, `INDEX`=指数, `SECTOR`=板块, `FIN`=财务, `KLINE`=K线, `LHB`=龙虎榜, `TURNOVER`=换手率, `PE`=市盈率 | 快速缩小范围 |
| **name** | 中文名 | 和 var 语义对照 |
| **match** | 匹配级别：`qualified`=精确匹配, `simple`=基础匹配, `fuzzy`=模糊匹配 | qualified 优先 |
| **time_gran** | 时间粒度：`实时`=tick级, `日频`=每天, `季频`=每季度 | 和 condition 时间要求对照 |
| **scope** | 范围粒度：`个股级别`、`指数级别`、`板块级别`、`市场级别` | **最重要的筛选维度** |
| **ds_name** | 数据源名称 | 辅助判断 |
| **protocol** | 取数协议：tushare/akshare/tencent/sina | 辅助判断 |

---

## 两步筛选法

### 第 1 步：从 scope（范围粒度）排除

**scope 必须与 obj 的类型匹配**，这是最硬的规则：

| obj 类型 | 示例 | 匹配的 scope | 不匹配的 scope |
|----------|------|-------------|---------------|
| 股票名称/代码 | 宁德时代、300750.SZ | `个股级别` | `指数级别`、`板块级别` |
| 指数名称 | 上证指数、沪深300 | `指数级别` | `个股级别`、`板块级别` |
| 板块名称 | 电池板块、白酒板块 | `板块级别` | `个股级别`、`指数级别` |
| 特定概念 | 北向资金 | 看具体含义 | 不一刀切，看 name 和 id |

**不匹配的 scope 直接淘汰**，不需要再看其他属性。

### 第 2 步：从 match + time_gran + 语义选出最优

Scope 匹配的字段中选出最优的一个：

| 优先级 | 条件 | 说明 |
|:------:|------|------|
| 🥇 | match=`qualified` | 精确匹配，**首选** |
| 🥈 | match=`simple` 且语义最接近 | 基础匹配，选 name 和 var 最像的 |
| 🥉 | match=`fuzzy` 且 name 最像 | 模糊匹配，仅当没有 qualified/simple 时选 |

同样 match 级别的，看 time_gran：
- condition 包含"今天/实时/盘中" → 优先 `实时`
- condition 包含"最近/历史/近N日" → 优先 `日频`
- condition 包含"季度/去年同期" → 优先 `季频`

同样 match + time_gran 级别的，看 **authority_level（权威评级）**：
- 优先选 authority_level 更高的
- 如果候选字段没有 authority_level 属性，视为最低优先级
- 权威评级等级：**S > A > B**
- 若同一数据源的不同字段（如"万申"板块 vs "同花顺"板块的涨跌幅），即使语义相近，也应优先选权威评级高的

---

## 完整判断示例

### 示例 1：涨跌幅 + 宁德时代

```
请求: var="涨跌幅", obj=["宁德时代"], condition=["今天"]

候选:
  (1) FIELD_QUOTE_PCT_CHG  name="个股涨跌幅"   match=qualified  scope=个股级别  time=实时
  (2) FIELD_INDEX_PCT_CHG  name="指数涨跌幅"   match=simple     scope=指数级别  time=日频
  (3) FIELD_SECTOR_PCT_CHG name="板块涨跌幅"   match=qualified  scope=板块级别  time=日频
  (4) FIELD_LHB_PCT_CHG    name="龙虎榜涨跌幅" match=simple     scope=个股级别  time=日频
  (5) FIELD_KLINE_PCT_CHG  name="K线涨跌幅"   match=simple     scope=个股级别  time=日频

判断：
  第1步—scope 过滤：宁德时代是股票 → 只需个股级别
    → 淘汰 (2) 指数级别, (3) 板块级别
    → 剩余 (1)(4)(5)
  第2步—选最优：
    (1) match=qualified ✅ → 精确命中，直接选
    → 输出: FIELD_QUOTE_PCT_CHG
```

### 示例 2：市盈率 + 中国平安

```
请求: var="市盈率", obj=["中国平安"], condition=["今天"]

候选:
  (1) FIELD_INDEX_PE   name="指数PE"   match=simple  scope=指数级别  time=日频  
  (2) FIELD_PE_TTM     name="PE_TTM"   match=simple  scope=个股级别  time=日频
  (3) FIELD_VAL_PE_TTM name="PE_TTM"   match=simple  scope=板块级别  time=季频

判断：
  第1步：中国平安是股票 → 只需要个股级别 → 淘汰 (1)(3)
  第2步：剩余 (2) 唯一个股级别字段 → 输出: FIELD_PE_TTM
```

### 示例 3：板块 + 宁德时代（查所属板块）

```
请求: var="板块", obj=["宁德时代"], condition=["今天"]

候选（系统自动路由 var="板块" 的结果）:
  (1) FIELD_SECTOR_NAME  name="板块名称(新浪)"  match=qualified  scope=板块级别  time=日频

判断：
  唯一候选 → 输出: FIELD_SECTOR_NAME
```

### 示例 4：涨跌幅 + 上证指数

```
请求: var="涨跌幅", obj=["上证指数"], condition=["今天"]

候选:
  (1) FIELD_QUOTE_PCT_CHG  name="个股涨跌幅"  match=qualified  scope=个股级别  time=实时
  (2) FIELD_INDEX_PCT_CHG  name="指数涨跌幅"  match=simple     scope=指数级别  time=日频
  (3) ...

第1步：上证指数是指数 → 只需要指数级别 → 淘汰 (1)(个股级别), (3)(板块级别)
第2步：剩余 (2) 唯一指数级别字段 → 输出: FIELD_INDEX_PCT_CHG
```

---

## 输出格式

只输出一行，就是选定的 field_id：

```
FIELD_QUOTE_PCT_CHG
```

不需要解释，不需要分析过程，不需要 `[FINAL_ANSWER]`，就一个字段 ID。
