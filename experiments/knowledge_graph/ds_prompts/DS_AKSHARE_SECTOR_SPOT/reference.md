# DS_AKSHARE_SECTOR_SPOT — 东方财富板块实时行情（Sector Spot）

## 数据源名称
- **中文名称**：东方财富板块实时行情
- **英文名称**：Sector Spot
- **数据源ID**：DS_AKSHARE_SECTOR_SPOT

## 接口
- **类型**：akshare SDK（B类）
- **函数签名**：`ak.stock_board_industry_spot_em(symbol='板块名称')`

## 数据内容描述
东方财富行业板块实时行情（涨跌幅等）

## 数据内容覆盖业务描述
板块轮动监控

## 数据接口背景描述（若有）
AkShare 是一个开源金融数据接口库，支持多种财经数据源。本接口通过 AkShare SDK 获取数据，免费使用。建议安装最新版 `pip install akshare --upgrade`。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import akshare as ak
df = ak.stock_board_industry_spot_em(symbol='板块名称')
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| symbol: 板块名称（如 '小金属'、'半导体'），必填参数 |

### 返回值
当 symbol 指定具体板块时，返回 item-value 两列格式：
| item | value |
|------|-------|
| 最新 | 1314.10 |
| 涨跌幅 | -0.18 |
| 换手率 | 0.82 |

从返回的 DataFrame 中提取目标字段：按 item 列匹配，取 value 列的值。

## 数据更新时效描述
AkShare 数据源多样，更新频率取决于底层源。实时行情类盘中高频更新，财报/机构持仓类按季度更新。部分接口数据延迟约 15-30 分钟。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| 板块名称 | str | — | — |
| 板块代码 | str | — | — |
| 涨跌幅 | float% | — | — |
| 成交额 | float(亿元) | — | — |
| 换手率 | float% | — | — |
| 领涨股 | str | — | — |
| 主力净流入 | float | — | — |

## 接口调用示例
```python
df = ak.stock_board_industry_spot_em(symbol="电池")
result_row = df[df["item"] == "涨跌幅"]
value = float(result_row["value"].iloc[0])
```

## 调用返回值样例（head(5)）
```
# 实际返回取决于调用时参数和当前数据
# 详见 api.md 中的返回格式说明
```

## 取数时容易出现的坑
