# DS_AKSHARE_INST_HOLD — 机构持仓明细（Institutional Holdings）

## 数据源名称
- **中文名称**：机构持仓明细
- **英文名称**：Institutional Holdings
- **数据源ID**：DS_AKSHARE_INST_HOLD

## 接口
- **类型**：akshare SDK（B类）
- **函数签名**：`ak.stock_institute_hold_detail(stock, quarter)`

## 数据内容描述
上市公司季度机构持仓明细

## 数据内容覆盖业务描述
机构持仓追踪

## 数据接口背景描述（若有）
AkShare 是一个开源金融数据接口库，支持多种财经数据源。本接口通过 AkShare SDK 获取数据，免费使用。建议安装最新版 `pip install akshare --upgrade`。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import akshare as ak
df = ak.stock_institute_hold_detail(stock, quarter)
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| 参数 | 类型 | 说明 | 示例 | |
| :----|:----:|:-----|:----:| |
| stock | str | **纯数字**股票代码，不带.SZ/.SH后缀 | 000001 | |
| quarter | str | 季度标识，格式为 年份+季度，如20261=2026年Q1 | 20261 | |

### 重要约定
- stock 参数不要带 .SZ / .SH 后缀，只传纯数字代码（如 000001）
- quarter 从查询条件中的时间范围提取（如 20260101~20260331 对应 20261）
- 如果有多行（多个机构），取列表最后一项的数据（汇总行或不指定单个机构时取第一个机构，即机构总数变化汇总）
- 该数据每季度更新，返回每个机构的最新持股明细

## 数据更新时效描述
AkShare 数据源多样，更新频率取决于底层源。实时行情类盘中高频更新，财报/机构持仓类按季度更新。部分接口数据延迟约 15-30 分钟。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| 持股比例 | float | 机构持仓占A股比例（%） | ? |
| 最新持股比例 | float | 最新一期持股比例（%） | ? |
| 持股数 | float | 持仓股数（万股） | ? |
| 最新持股数 | float | 最新一期持仓股数（万股） | ? |
| 占流通股比例 | float | 占流通A股比例（%） | ? |
| 最新占流通股比例 | float | 最新一期占流通A股比例（%） | ? |
| 持股比例增幅 | float | 持股比例较上季度变动（百分点） | ? |
| 占流通股比例增幅 | float | 占流通股比例较上季度变动（百分点） | ? |

## 接口调用示例
```python
import akshare as ak, pandas as pd
df = ak.stock_institute_hold_detail(stock='300750', quarter='20261')
row = df.iloc[-1]  # 汇总行
value = row['机构总数']
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# ak.stock_institute_hold_detail(stock, quarter) 的返回值
# 实际数据需运行时获取
```

## 取数时容易出现的坑
