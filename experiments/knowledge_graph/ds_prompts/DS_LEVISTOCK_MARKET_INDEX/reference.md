# DS_LEVISTOCK_MARKET_INDEX — 主要指数行情（Market Index）

## 数据源名称
- **中文名称**：主要指数行情
- **英文名称**：Market Index
- **数据源ID**：DS_LEVISTOCK_MARKET_INDEX

## 接口
- **类型**：levistock SDK（C类）
- **函数签名**：`lk.market_index_all_em()`

## 数据内容描述
A股主要指数实时行情（上证、深证、创业板等）

## 数据内容覆盖业务描述
大盘实时行情、指数追踪

## 数据接口背景描述（若有）
Levistock 是一个轻量级金融数据接口库，专注于 A 股实时和日频数据。通过 `pip install levistock` 安装。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import levistock as lk
data = lk.market_index_all_em()
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|

## 数据更新时效描述
Levistock 实时数据盘中高频更新（秒级），日频数据 T+1 更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| name | — | 指数名称 | — |
| price | — | 当前点位 | — |
| change_pct | — | 涨跌幅% | — |
| vol | — | 成交量 | — |
| amount | — | 成交额 | — |

## 接口调用示例
```python
data_list = lk.market_index_all_em()
if data_list:
    target_name = "上证指数"  # 从查询条件获取
    for item in data_list:
        if item.get("name") == target_name:
            _result = [item.get("price", 0)]
            break
```

## 调用返回值样例（head(5)）
```
# 实际返回取决于调用时参数和当前数据
# 详见 api.md 中的返回格式说明
```

## 取数时容易出现的坑
1. **无参数**：返回所有指数，需遍历按 name 匹配
2. **多个指数**：返回列表，不指定名称时取第一个
### 额外说明
无参数，返回所有主要指数的实时行情
返回 list[dict]，每个 dict 包含一个指数数据
**要从列表中找出特定指数，遍历 data_list 按 name 字段匹配**

