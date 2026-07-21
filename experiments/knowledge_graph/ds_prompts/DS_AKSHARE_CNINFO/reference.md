# DS_AKSHARE_CNINFO — 巨潮公告（CNINFO Announcements）

## 数据源名称
- **中文名称**：巨潮公告
- **英文名称**：CNINFO Announcements
- **数据源ID**：DS_AKSHARE_CNINFO

## 接口
- **类型**：akshare SDK（B类）
- **函数签名**：`ak.stock_zh_a_disclosure_report_cninfo(symbol)`

## 数据内容描述
巨潮资讯网上市公司公告

## 数据内容覆盖业务描述
公告筛选、舆情监控

## 数据接口背景描述（若有）
AkShare 是一个开源金融数据接口库，支持多种财经数据源。本接口通过 AkShare SDK 获取数据，免费使用。建议安装最新版 `pip install akshare --upgrade`。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import akshare as ak
df = ak.stock_zh_a_disclosure_report_cninfo(symbol)
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|

### 返回值
['代码', '简称', '公告标题', '公告时间', '公告链接']

### 重要约定
- symbol 参数不要带 .SZ / .SH 后缀，只传纯数字代码

## 数据更新时效描述
AkShare 数据源多样，更新频率取决于底层源。实时行情类盘中高频更新，财报/机构持仓类按季度更新。部分接口数据延迟约 15-30 分钟。

## 输出数据描述
| 字段名 | 说明 |
|:---|:---|
| 代码 | 代码 |
| 简称 | 简称 |
| 公告标题 | 公告标题 |
| 公告时间 | 公告时间 |
| 公告链接 | 公告链接 |

## 接口调用示例
```python
import akshare as ak, pandas as pd
df = ak.stock_zh_a_disclosure_report_cninfo(symbol)
print(df.head(10))
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# ak.stock_zh_a_disclosure_report_cninfo(symbol) 的返回值
# 实际数据需运行时获取
```

## 取数时容易出现的坑
