# 数据源主备切换流程

## 场景

当某个数据源不稳定（如东方财富 EM 频繁断连），需要将 DataField 的主数据源切换到另一个数据源（如同花顺 THS），并将原数据源降级为备选。

---

## 切换前置检查清单

### 1. 确认新数据源能否覆盖

调用新数据源的 API，获取返回的列名：

```python
import akshare as ak
df = ak.stock_board_industry_summary_ths()  # 新数据源
print(list(df.columns))
# → ['序号', '板块', '涨跌幅', '总成交量', '总成交额', '净流入', ...]
```

### 2. 逐字段对照

| 原字段 | 原 api_column | 新数据源有无 | 新列名 |
|--------|-------------|:-----------:|--------|
| 板块名称 | 板块名称 | ✅ 有 | 板块 |
| 板块涨跌幅 | 涨跌幅 | ✅ 有 | 涨跌幅 |
| 板块代码 | 板块代码 | ❌ 无 | — |

### 3. 决定切换策略

| 情况 | 处理 |
|------|------|
| 新数据源有对应列 | 切换主数据源 + 更新 api_column |
| 新数据源无对应列 | 保留原主数据源，添加备份关系 |

---

## 切换执行步骤

### Step 1：更新 ds_prompts 文档

确保新数据源的 API 说明准确：

```bash
cat > ds_prompts/DS_AKSHARE_SECTOR_THS/api.md << 'EOF'
## 接口
ak.stock_board_industry_summary_ths()
## 说明
- 无参数，返回所有同花顺行业板块实时行情
- 返回 DataFrame
EOF
```

### Step 2：在 Neo4j 中执行切换

```cypher
// 2a. 删除旧 HAS_DATASOURCE 关系
MATCH (f:DataField {id: 'FIELD_SECTOR_NAME'})-[r:HAS_DATASOURCE]->(ds:DataSource {id: 'DS_AKSHARE_SECTOR_SPOT'})
DELETE r

// 2b. 创建新 HAS_DATASOURCE 关系
MATCH (f:DataField {id: 'FIELD_SECTOR_NAME'})
MATCH (ds:DataSource {id: 'DS_AKSHARE_SECTOR_THS'})
CREATE (f)-[:HAS_DATASOURCE]->(ds)

// 2c. 更新 api_column
MATCH (f:DataField {id: 'FIELD_SECTOR_NAME'})
SET f.api_column = '板块'

// 2d. 添加备份关系
MATCH (f:DataField {id: 'FIELD_SECTOR_NAME'})
MATCH (ds:DataSource {id: 'DS_AKSHARE_SECTOR_SPOT'})
CREATE (f)-[:HAS_BACKUP_DATASOURCE {
    backup_reason: 'THS主数据源不可用时切换',
    priority: 1
}]->(ds)

// 2e. 更新属性
MATCH (f:DataField {id: 'FIELD_SECTOR_NAME'})
SET f.has_backup = True,
    f.default_datasource_id = 'DS_AKSHARE_SECTOR_THS'
```

### Step 3：验证

```bash
# 路由测试通过
python3 query_agent_api/test_agent_router.py

# 审计通过
cd scripts && python3 audit_full.py

# 重生成 Embedding（字段属性变更后）
python3 scripts/generate_embeddings.py
```

### Step 4：Codegen 测试

```bash
python3 query_agent_api/test_agent_coder.py
```

---

## 需要更新的属性清单

切换一个 DataField 的主数据源时，以下属性需要评估是否更新：

| 属性 | 位置 | 是否需要更新 | 说明 |
|------|------|:-----------:|------|
| `api_column` | DataField 节点 | ✅ 必改 | 新数据源的列名可能不同 |
| `has_backup` | DataField 节点 | ✅ 必改 | 设为 True |
| `default_datasource_id` | DataField 节点 | ✅ 必改 | 指向新主数据源 |
| `granularity` | DataField 节点 | ⚠️ 视情况 | 新数据源粒度可能不同 |
| `refresh_time` | DataField 节点 | ⚠️ 视情况 | 新数据源更新频率可能不同 |
| `unit` | DataField 节点 | ⚠️ 视情况 | 新数据源单位可能不同（亿元 vs 元） |
| HAS_DATASOURCE 关系 | 关系 | ✅ 必改 | 删除旧 + 创建新 |
| HAS_BACKUP_DATASOURCE 关系 | 关系 | ✅ 必改 | 添加新备份关系 |
| 备份关系属性 | 关系属性 | ✅ 推荐 | backup_reason, priority, coverage |

---

## 本次切换记录（示例）

**时间**: 2026-07-16
**源数据源**: DS_AKSHARE_SECTOR_SPOT（东方财富 EM）
**目标数据源**: DS_AKSHARE_SECTOR_THS（同花顺）
**原因**: EM 东方财富源频繁 ConnectionError

**切换字段（8个）**:
| 字段 | 原 api_column → 新 api_column |
|------|-----------------------------|
| FIELD_SECTOR_NAME | 板块名称 → 板块 |
| FIELD_SECTOR_PCT_CHG | 涨跌幅 → 涨跌幅 |
| FIELD_SECTOR_AMOUNT | 成交额 → 总成交额 |
| FIELD_SECTOR_MAIN_INFLOW | 主力净流入 → 净流入 |
| FIELD_SECTOR_LEAD_STOCK | 领涨股 → 领涨股 |
| FIELD_SECTOR_LEAD_CHG | 领涨股涨幅 → 领涨股-涨跌幅 |
| FIELD_SECTOR_UP_COUNT | 上涨家数 → 上涨家数 |
| FIELD_SECTOR_DOWN_COUNT | 下跌家数 → 下跌家数 |

**未切换字段（8个，THS 无对应列）**:
板块代码、换手率、板块指数、振幅、领涨股代码、领跌股、领跌股涨幅、总市值

**清理**: 删除被替代的冗余字段 FIELD_SECTOR_THS_NET_INFLOW
