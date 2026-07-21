# DS_LEVISTOCK_SECTOR — 板块行情（全量）（Sector Overview）

## 数据源名称
- **中文名称**：板块行情（全量）
- **英文名称**：Sector Overview
- **数据源ID**：DS_LEVISTOCK_SECTOR

## 接口
- **类型**：levistock SDK（C类）
- **函数签名**：`lk.sector_em(sector_type='industry')`

## 数据内容描述
全量板块行情数据（行业/概念/地域）

## 数据内容覆盖业务描述
板块全面扫描、轮动分析

## 数据接口背景描述（若有）
Levistock 是一个轻量级金融数据接口库，专注于 A 股实时和日频数据。通过 `pip install levistock` 安装。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import levistock as lk
data = lk.sector_em(sector_type='industry')
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| sector_type: 板块类型（默认 'industry'），可选值：'industry', 'concept', 'region' |

### 返回值
返回 list[dict]，每个 dict 包含板块行情数据

## 数据更新时效描述
Levistock 实时数据盘中高频更新（秒级），日频数据 T+1 更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| sector_code | — | 板块代码 | — |
| sector_name | — | 板块名称 | — |
| price | — | 板块指数 | — |
| change_pct | — | 涨跌幅% | — |
| amount | — | 成交额 | — |
| turnover_rate | — | 换手率% | — |
| amplitude | — | 振幅% | — |
| total_market | — | 总市值 | — |
| main_inflow | — | 主力净流入 | — |
| lead_stock_name | — | 领涨股名称 | — |
| up_count | — | 上涨家数 | — |
| down_count | — | 下跌家数 | — |

## 接口调用示例
```python
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# lk.sector_em(sector_type='industry') 的返回值
# 实际数据需运行时获取
```

## 取数时容易出现的坑
1. **sector_type 参数**：'industry' 行业 / 'concept' 概念 / 'region' 地域
2. **遍历匹配**：返回 list[dict]，需遍历按 sector_name 匹配
