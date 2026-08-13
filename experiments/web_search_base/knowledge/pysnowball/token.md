# pysnowball Token

> 来源: refresh_token.py Playwright 自动登录 | 上次更新: 2026-08-12 14:56
> 有效期: 7-30 天，过期需重新获取

```
xq_a_token=8726c7e17a6d858f8961ce2aa3ca13dfe5169baa
u=401786517767719
```

## 设置方式

```python
import pysnowball as ball
ball.set_token("xq_a_token=8726c7e17a6d858f8961ce2aa3ca13dfe5169baa; u=401786517767719")
```

## 过期处理

运行 `conda run -n stock_agent python3 refresh_token.py` 自动更新。
