# DS_LEVISTOCK_STOCK_CHANGES — 股票异动（Stock Changes）

## 数据源名称
- **中文名称**：股票异动
- **英文名称**：Stock Changes
- **数据源ID**：DS_LEVISTOCK_STOCK_CHANGES

## 接口
- **类型**：levistock SDK（C类）
- **函数签名**：`lk.stock_changes_em(change_type='8201', filter_st=True)`

## 数据内容描述
个股异动监控（急涨、急跌、放量等）

## 数据内容覆盖业务描述
短线异动监控

## 数据接口背景描述（若有）
Levistock 是一个轻量级金融数据接口库，专注于 A 股实时和日频数据。通过 `pip install levistock` 安装。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import levistock as lk
data = lk.stock_changes_em(change_type='8201', filter_st=True)
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|

### 返回值
返回 list[dict]，每项包含 stock_code, stock_name, change_pct 等字段

## 数据更新时效描述
Levistock 实时数据盘中高频更新（秒级），日频数据 T+1 更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| stock_name | str | 股票名称 | 深南电B |
| stock_code | str | 股票代码 | 200037 |
| change_pct | str | 涨跌幅% | 0.085714 |

## 接口调用示例
```python
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# lk.stock_changes_em(change_type='8201', filter_st=True) 的返回值
# 实际数据需运行时获取
```

## 取数时容易出现的坑
1. **change_type 参数**：'8201'=实时异动，其他值含义不同
2. **filter_st**：默认过滤 ST 股
