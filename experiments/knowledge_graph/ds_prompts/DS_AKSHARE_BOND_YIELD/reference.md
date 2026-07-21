# DS_AKSHARE_BOND_YIELD — 债券收益率（Bond Yield）

## 数据源名称
- **中文名称**：债券收益率
- **英文名称**：Bond Yield
- **数据源ID**：DS_AKSHARE_BOND_YIELD

## 接口
- **类型**：akshare SDK（B类）
- **函数签名**：`ak.bond_zh_us_rate()`

## 数据内容描述
中美债券收益率历史数据

## 数据内容覆盖业务描述
债券利率分析、中美利差

## 数据接口背景描述（若有）
AkShare 是一个开源金融数据接口库，支持多种财经数据源。本接口通过 AkShare SDK 获取数据，免费使用。建议安装最新版 `pip install akshare --upgrade`。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import akshare as ak
df = ak.bond_zh_us_rate()
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|

## 数据更新时效描述
AkShare 数据源多样，更新频率取决于底层源。实时行情类盘中高频更新，财报/机构持仓类按季度更新。部分接口数据延迟约 15-30 分钟。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| 中国国债收益率2年 | float | 中国国债收益率2年 | ? |
| 中国国债收益率5年 | float | 中国国债收益率5年 | ? |
| 中国国债收益率10年 | float | 中国国债收益率10年 | ? |
| 中国国债收益率30年 | float | 中国国债收益率30年 | ? |
| 日期 | date | 日期 | ? |

## 接口调用示例
```python
import akshare as ak, pandas as pd
df = ak.bond_zh_us_rate()
row = df.iloc[-1]
value = row['中国国债收益率10年']
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# ak.bond_zh_us_rate() 的返回值
# 实际数据需运行时获取
```

## 取数时容易出现的坑
### 额外说明
无参数，返回中美债券收益率历史数据 DataFrame

