# DS_LEVISTOCK_ZT_POOL — 涨停板池（ZT Pool）

## 数据源名称
- **中文名称**：涨停板池
- **英文名称**：ZT Pool
- **数据源ID**：DS_LEVISTOCK_ZT_POOL

## 接口
- **类型**：levistock SDK（C类）
- **函数签名**：`lk.stock_zt_pool_em(date)`

## 数据内容描述
涨停股池，含连板数、封板时间等

## 数据内容覆盖业务描述
涨停分析、连板统计

## 数据接口背景描述（若有）
Levistock 是一个轻量级金融数据接口库，专注于 A 股实时和日频数据。通过 `pip install levistock` 安装。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import levistock as lk
data = lk.stock_zt_pool_em(date)
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|

### 返回值
返回 list[dict]，每个 dict 包含涨停股票信息

## 数据更新时效描述
Levistock 实时数据盘中高频更新（秒级），日频数据 T+1 更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| continuous | int | 连续涨停天数 | ? |
| zt_days | int | 涨停总天数 | ? |
| first_zt_time | string | 首次涨停封板时间（如92500=9:25） | ? |
| last_zt_time | string | 最后涨停封板时间 | ? |
| open_times | int | 涨停开板次数 | ? |
| price | float | 最新价 | ? |
| change_pct | float | 涨跌幅% | ? |
| amount | float | 成交额 | ? |
| sector | string | 涨停股票所属行业板块 | ? |
| stock_name | string | 股票名称 | ? |
| stock_code | string | 股票代码 | ? |

## 接口调用示例
```python
data = lk.stock_zt_pool_em(date="20260715")
if data:
    item = data[0]
    _result = [item.get("continuous", 0)]  # 字段名从字段映射表获取
```

## 调用返回值样例（head(5)）
```
# 实际返回取决于调用时参数和当前数据
# 详见 api.md 中的返回格式说明
```

## 取数时容易出现的坑
1. **日期格式**：YYYYMMDD 格式
2. **非交易日**：非交易日返回空列表
3. **字典字段**：返回的数据是 list[dict]，用 `.get()` 取值避免 KeyError
