#!/usr/bin/env python3
"""雪球 Token 维护脚本

功能（按优先级）:
  1. 尝试静默登录获取新 Token
  2. 如 WAF 拦截登录，检查已有 Token 是否有效
  3. 如 Token 失效且登录被拦，给出手动更新指引

用法:
  python3 login_xueqiu.py           # 仅检查/更新 token.md
  python3 login_xueqiu.py --verify  # 只验证当前 token，不尝试登录
"""

import re
import os
import sys
import json
import requests

TOKEN_FILE = os.path.join(os.path.dirname(__file__), 'token.md')

# ===== 用户凭证（只在登录尝试时使用）=====
USERNAME = '3755631005'
PASSWORD = 'zhuang321'


def read_token_from_file() -> tuple[str, str]:
    """从 token.md 读取当前存储的 xq_a_token 和 u"""
    xq_a_token = ''
    u = ''
    try:
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        m = re.search(r'xq_a_token=([^\s\n]+)', content)
        if m:
            xq_a_token = m.group(1)
        m = re.search(r'(?<!xq_a_token)u=([^\s\n]+)', content)
        if m:
            u = m.group(1)
    except FileNotFoundError:
        pass
    return xq_a_token, u


def verify_token(xq_a_token: str, u: str) -> bool:
    """验证 Token 是否有效（用 quotec 接口测试）"""
    import pysnowball as ball
    ball.set_token(f'xq_a_token={xq_a_token}; u={u}')
    try:
        data = ball.quotec('SZ300750')
        if data.get('error_code') == 0 and data.get('data'):
            price = data['data'][0]['current']
            print(f'  ✅ Token 有效! 宁德时代当前价: {price}')
            return True
        return False
    except Exception as e:
        print(f'  ❌ Token 验证异常: {e}')
        return False


def login_xueqiu() -> tuple[str, str]:
    """尝试登录雪球（可能被 WAF 拦截）"""
    s = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://xueqiu.com/',
    }
    s.headers.update(headers)

    # 首页获取 cookie
    r = s.get('https://xueqiu.com', timeout=15)
    if r.status_code != 200:
        print(f'  ⚠️  首页访问失败: {r.status_code}')
        return '', ''

    # XHR 风格登录
    s.headers.update({
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
    })
    payload = {'username': USERNAME, 'password': PASSWORD, 'remember_me': 'true'}
    r = s.post('https://xueqiu.com/user/login', data=payload, timeout=15)

    cookies = s.cookies.get_dict()
    xq_a_token = cookies.get('xq_a_token', '')
    u = cookies.get('u', '')

    if xq_a_token:
        return xq_a_token, u

    # 判断 WAF 拦截
    if 'aliyun_waf' in r.text or '_waf_' in r.text:
        print(f'  🔒 登录被阿里云 WAF 拦截（非浏览器请求无法通过）')
    else:
        try:
            err = r.json()
            print(f'  ❌ 登录失败: {err.get("error_description", "未知错误")}')
        except:
            print(f'  ❌ 登录失败: HTTP {r.status_code}')
    return '', ''


def update_token_file(xq_a_token: str, u: str):
    """写入 token.md"""
    content = f'''# pysnowball Token

> 来源: 自动登录脚本更新 | 上次更新: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}
> 有效期: 7-30 天，过期需重新获取

```
xq_a_token={xq_a_token}
u={u}
```

## 设置方式

```python
import pysnowball as ball
ball.set_token("xq_a_token={xq_a_token}; u={u}")
```

## 过期处理

当接口返回 `error_code: 400016` 时表示 Token 已过期：
1. 浏览器打开 https://xueqiu.com 并登录
2. F12 → Application → Cookies → `https://xueqiu.com`
3. 找到 `xq_a_token`，复制新的 Value
4. 更新本文件
'''
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  ✅ token.md 已更新')
    print(f'     xq_a_token={xq_a_token}')
    print(f'     u={u}')


def main():
    print('=' * 45)
    print('  雪球 Token 维护')
    print('=' * 45)
    print()

    # 读取现有 Token
    xq_a_token, u = read_token_from_file()
    if xq_a_token:
        print(f'当前 Token: {xq_a_token[:20]}...')
        print(f'当前 u:     {u}')
        print()
        print('验证 Token...')
        if verify_token(xq_a_token, u):
            print()
            print('Token 正常，无需更新。')
            return
        print()
    else:
        print('⚠️  token.md 中未找到 xq_a_token')
        print()

    # Token 无效或不存在，尝试登录
    print('尝试登录获取新 Token...')
    xq_a_token, u = login_xueqiu()
    if xq_a_token:
        print()
        print('更新 Token...')
        update_token_file(xq_a_token, u)
        print()
        print('验证新 Token...')
        verify_token(xq_a_token, u)
    else:
        print()
        print('=' * 45)
        print('⚠️  自动登录失败')
        print()
        print('雪球使用了阿里云 WAF 防护，')
        print('当前环境无法完成浏览器级别的登录验证。')
        print()
        print('请手动获取 Token:')
        print('  1. 浏览器登录 xueqiu.com')
        print('  2. F12 → Application → Cookies')
        print('  3. 复制 xq_a_token 和 u')
        print('  4. 更新 knowledge/pysnowball/token.md')
        print('=' * 45)


if __name__ == '__main__':
    main()
