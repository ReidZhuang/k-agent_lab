# DS_LEVISTOCK_NEWS API 调用规则

## 接口
lk.news_telegraph_cls(category='important')

## 参数
- category: 'important' 重要快讯 / 'all' 全部

## 返回结构
返回 list[dict]，每项:
- item['time']     → 发布时间
- item['title']    → 标题
- item['content']  → 正文

## 示例
```python
import levistock as lk
news_list = lk.news_telegraph_cls(category='important')
for n in news_list[:5]:
    print(n['time'], n['title'])
```

## 注意
- 默认返回最近 20-50 条
- 无需 Token
