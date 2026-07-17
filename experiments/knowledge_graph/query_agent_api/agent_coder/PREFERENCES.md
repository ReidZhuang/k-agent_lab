# PREFERENCES.md — 编码规范

- 按 API 文档的要求构造请求/调用 SDK
- 从返回数据中按字段名或索引提取目标字段
- 确保 _result 顺序与查询条件中的指标列表顺序一致
- 处理空数据情况
- 使用 iloc[0] 取 DataFrame 的最新一行
