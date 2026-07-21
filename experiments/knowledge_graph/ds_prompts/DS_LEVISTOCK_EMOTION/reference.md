# DS_LEVISTOCK_EMOTION — 市场情绪（Market Emotion）

## 数据源名称
- **中文名称**：市场情绪
- **英文名称**：Market Emotion
- **数据源ID**：DS_LEVISTOCK_EMOTION

## 接口
- **类型**：levistock SDK（C类）
- **函数签名**：`lk.market_emotion_cls()`

## 数据内容描述
A股市场情绪综合指标（热度、赚钱效应等）

## 数据内容覆盖业务描述
市场情绪判断

## 数据接口背景描述（若有）
Levistock 是一个轻量级金融数据接口库，专注于 A 股实时和日频数据。通过 `pip install levistock` 安装。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import levistock as lk
data = lk.market_emotion_cls()
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|

### 返回值
返回 dict，直接索引访问：
- emotion['market_degree']  → 市场热度 int 0-100
- emotion['up_ratio']       → 上涨占比 %
- emotion['profit_ratio']   → 赚钱效应 %
- emotion['shsz_balance']   → 两市成交额
- emotion['limit_up_board'] → 涨停梯队 dict

## 数据更新时效描述
Levistock 实时数据盘中高频更新（秒级），日频数据 T+1 更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| market_degree | — | 市场热度0-100 | — |
| up_ratio | — | 上涨占比% | — |
| profit_ratio | — | 赚钱效应% | — |
| shsz_balance | — | 两市成交额 | — |
| limit_up_board | — | 涨停梯队dict | — |

## 接口调用示例
```python
import levistock as lk
emotion = lk.market_emotion_cls()
print(emotion['market_degree'])
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# lk.market_emotion_cls() 的返回值
# 实际数据需运行时获取
```

## 取数时容易出现的坑
1. **返回 dict**：不是 DataFrame，直接索引访问
2. **整数范围**：market_degree 是 int 0-100
3. **limit_up_board 是嵌套 dict**
