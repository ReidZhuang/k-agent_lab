# LLM 用户问题解析

## 任务
解析用户的投资研究问题，提取结构化路由所需的信息。

## 输入
用户问题原文

## 输出格式
```json
{
  "keywords": ["关键词1", "关键词2"],
  "intent_type": "fact",
  "entity": {"type": "stock_code", "value": ""},
  "time_range": {"start": "", "end": ""},
  "conditions": {}
}
```

## 字段说明

### keywords
从用户问题中提取的关键指标词，用于知识图谱 alias 匹配。
- 优先提取业务术语，如"净利润"、"毛利率"、"PE_TTM"
- 不要添加原文中没有的词
- 如有明显限定词（如"指数涨跌幅"），优先保留完整限定词

### intent_type
- `fact`：事实查询（"是多少"、"查一下"）
- `analysis`：分析查询（"表现如何"、"评价一下"）
- `explore`：探索查询（"全面说说"、"帮我看一看"）

### entity
用户提到的实体对象，如股票代码、板块名称等。

### time_range
查询涉及的时间范围，格式 YYYYMMDD。

## 示例

用户问题：贵州茅台2025年第一季度的毛利率是多少？
```json
{
  "keywords": ["毛利率"],
  "intent_type": "fact",
  "entity": {"type": "stock_code", "value": "600519.SH"},
  "time_range": {"start": "20250101", "end": "20250331"},
  "conditions": {}
}
```

用户问题：宁德时代最近的财务状况怎么样，帮我看一下
```json
{
  "keywords": ["ROE", "毛利率", "净利率", "营收增速", "净利增速", "资产负债率"],
  "intent_type": "analysis",
  "entity": {"type": "stock_code", "value": "300750.SZ"},
  "time_range": {"start": "", "end": ""},
  "conditions": {}
}
```
