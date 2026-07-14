# DS_TENCENT_QUOTE API 调用规则

## 接口
HTTP GET: https://web.sqt.gtimg.cn/q={code}

## 参数
- code: sh600519 或 sz300750（sh=上海, sz=深圳）
- 批量: 逗号分隔多个代码
- 请求需带 User-Agent 头
- **必须跟随 302 重定向**（加 allow_redirects=True）

## 示例
```python
import requests
r = requests.get('https://web.sqt.gtimg.cn/q=sh600519',
                 headers={'User-Agent': 'Mozilla/5.0'},
                 timeout=10, allow_redirects=True)
text = r.text
```

## 注意
- 免 Token
- 返回 ~ 分隔的纯文本
