## 接口
lk.news_telegraph_cls(category='important')

## 参数
- category: 'important' 重要快讯 / 'all' 全部

## 返回结构
返回 list[dict]，每项:
- item['time']     → 发布时间
- item['title']    → 标题
- item['content']  → 正文