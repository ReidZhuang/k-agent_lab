# 数据源主备机制设计

## 问题

DataField 只有一个 default_datasource_id。当该数据源不可用时，路由和执行都没有备用方案。

## 方案：HAS_BACKUP_DATASOURCE 关系

```cypher
(f:DataField)-[:HAS_BACKUP_DATASOURCE {
    priority: 1,         // 备用优先级（1=首选备用, 2=兜底）
    api_column: "列名",   // 在该备源中该字段的列名（可能不同于主源）
    unit: "元"            // 在该备源中的单位
}]->(ds:DataSource)
```

不需要重复 code_format（DataSource 节点已有）。

## 优先级计算

priority = weight_relability × reliability_score + weight_authority × authority_score + weight_freshness × freshness_score

由 config/backup_weights.json 配置，专家调优。

## 路由输出

RouteResult 新增：
```json
{
  "datasource": {"id": "DS_TUSHARE_DAILY"},
  "backups": [
    {"priority": 1, "datasource_id": "DS_SINA_KLINE", "api_column": "收盘价"},
    {"priority": 2, "datasource_id": "DS_XUEQIU_KLINE", "api_column": "current"}
  ]
}
```

## 执行器逻辑

1. 优先尝试主数据源
2. 如果主数据源失败，按 priority 从低到高依次尝试备用源
3. 每个备用源使用各自的 api_column 和 unit
