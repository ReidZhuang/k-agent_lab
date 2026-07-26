# pysnowball Token

> 来源: Playwright 自动登录 | 上次更新: 2026-07-25 17:38
> 有效期: 7-30 天，过期需重新获取

```
xq_a_token=711478fcaffa49560b2873559a1332edd5de17e0
u=791784972289904
```

## 设置方式

```python
import pysnowball as ball
ball.set_token("xq_a_token=711478fcaffa49560b2873559a1332edd5de17e0; u=791784972289904")
```

## 过期处理

当接口返回 `error_code: 400016` 时表示 Token 已过期：
1. 运行 `python3 login_xueqiu_playwright.py` 自动更新
2. 或手动：浏览器打开 https://xueqiu.com → F12 → Application → Cookies → 复制 xq_a_token
