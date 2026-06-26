# pysnowball Token

> 来源: 浏览器登录 xueqiu.com → F12 → Application → Cookies → xueqiu.com
> 有效期: 7-30 天，过期需重新获取

```
xq_a_token=0840dc1dbe677e97880d8f7911de1ddd7a01501d
u=3755631005
```

## 设置方式

```python
import pysnowball as ball
ball.set_token("xq_a_token=0840dc1dbe677e97880d8f7911de1ddd7a01501d; u=3755631005")
```

## 过期处理

当接口返回 `error_code: 400016` 时表示 Token 已过期。

### 方法一：运行脚本（推荐）

```bash
cd research/experiments/web_search_base/knowledge/pysnowball
python3 login_xueqiu.py
```

脚本会自动尝试登录，成功则直接更新本文件。

### 方法二：手动更新

1. 浏览器打开 https://xueqiu.com 并登录
2. F12 → Application → Cookies → `https://xueqiu.com`
3. 找到 `xq_a_token`，复制新的 Value
4. 更新本文件
