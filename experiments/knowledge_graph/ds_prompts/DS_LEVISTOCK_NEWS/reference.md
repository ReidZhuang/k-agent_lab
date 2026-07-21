# DS_LEVISTOCK_NEWS — 市场快讯（Market News）

## 数据源名称
- **中文名称**：市场快讯
- **英文名称**：Market News
- **数据源ID**：DS_LEVISTOCK_NEWS

## 接口
- **类型**：levistock SDK（C类）
- **函数签名**：`lk.news_telegraph_cls(category='important')`

## 数据内容描述
7x24小时市场快讯/电报

## 数据内容覆盖业务描述
实时消息面、事件驱动

## 数据接口背景描述（若有）
Levistock 是一个轻量级金融数据接口库，专注于 A 股实时和日频数据。通过 `pip install levistock` 安装。

## 数据接口函数调用方法描述
### 基本使用方法
```python
import levistock as lk
data = lk.news_telegraph_cls(category='important')
```

### 输入参数
| 参数名 | 必填 | 类型 | 说明 |
|:------|:----:|:----:|:-----|
| category: 'important' 重要快讯 / 'all' 全部 |

### 返回值
返回 list[dict]，每项:
- item['time']     → 发布时间
- item['title']    → 标题
- item['content']  → 正文

## 数据更新时效描述
Levistock 实时数据盘中高频更新（秒级），日频数据 T+1 更新。

## 输出数据描述
| 字段名 | 类型 | 说明 | 数据示例 |
|:------|:----:|:-----|:--------|
| time | — | 时间 | — |
| title | — | 标题 | — |
| content | — | 正文 | — |

## 接口调用示例
```python
import levistock as lk
news = lk.news_telegraph_cls(category='important')
if news:
    print(news[0]['title'])
```

## 调用返回值样例（head(5)）
```
# 返回值格式
# lk.news_telegraph_cls(category='important') 的返回值
# 实际数据需运行时获取
```

## 取数时容易出现的坑
1. **category 参数**：默认 'important' 只返回重要快讯，'all' 返回全部
2. **内容可能长**：content 字段正文较长
