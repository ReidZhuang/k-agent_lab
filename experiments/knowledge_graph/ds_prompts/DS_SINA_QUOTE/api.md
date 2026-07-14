# DS_SINA_QUOTE API 调用规则

## 接口
HTTP GET: http://hq.sinajs.cn/list={prefix}{code}

## 参数
- code: sh600519 或 sz300750
- **必须带 Referer 和 User-Agent 头**
- 编码: GBK，需要 r.encoding = 'gbk'

## 示例
```python
import requests
r = requests.get('http://hq.sinajs.cn/list=sh600519',
                 headers={'Referer': 'https://finance.sina.com.cn',
                          'User-Agent': 'Mozilla/5.0'},
                 timeout=10)
r.encoding = 'gbk'
text = r.text
```

## 注意
- 免 Token
- 数据延迟约 15 分钟
