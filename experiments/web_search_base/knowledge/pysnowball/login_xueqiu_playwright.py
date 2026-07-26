#!/usr/bin/env python3
"""雪球 Token 自动获取 — Playwright 无头浏览器登录

雪球使用阿里云 WAF 防护，普通 requests 登录会被拦截。
Playwright 模拟真实浏览器行为，可绕过 WAF 完成登录。

用法:
  python3 login_xueqiu_playwright.py              # 登录并更新两个 token 文件
  python3 login_xueqiu_playwright.py --verify     # 只验证当前 token，不登录
  python3 login_xueqiu_playwright.py --force      # 强制重新登录（跳过 token 有效性检查）

输出:
  - token.md  (knowledge/pysnowball)
  - snowball_token.json  (midday/config)
"""

import os
import re
import sys
import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

# ── 路径 ──────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
TOKEN_MD = _THIS_DIR / "token.md"
TOKEN_JSON = Path(
    __file__).resolve().parent.parent.parent.parent / "report_machine" / "data_fetch" / "midday" / "config" / "snowball_token.json"

# ── 凭证 ──────────────────────────────────────────────
USERNAME = "3755631005"
PASSWORD = "zhuang321"

# ── 日志 ──────────────────────────────────────────────
_log = lambda msg: print(f"  {msg}")


# ============================================================
# Token 文件读写
# ============================================================

def read_current_token() -> tuple[str, str]:
    """从 token.md 读取当前存储的 xq_a_token 和 u"""
    if not TOKEN_MD.exists():
        return "", ""
    content = TOKEN_MD.read_text(encoding="utf-8")
    m = re.search(r"xq_a_token=([^\s\n]+)", content)
    xq_a_token = m.group(1) if m else ""
    m = re.search(r"(?<!xq_a_token)u=([^\s\n]+)", content)
    u = m.group(1) if m else ""
    return xq_a_token, u


def update_token_md(xq_a_token: str, u: str):
    """更新 token.md"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = f"""# pysnowball Token

> 来源: Playwright 自动登录 | 上次更新: {ts}
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
1. 运行 `python3 login_xueqiu_playwright.py` 自动更新
2. 或手动：浏览器打开 https://xueqiu.com → F12 → Application → Cookies → 复制 xq_a_token
"""
    TOKEN_MD.write_text(content, encoding="utf-8")
    _log(f"✅ token.md 已更新")


def update_token_json(xq_a_token: str, u: str):
    """更新 snowball_token.json（midday/config/ 下的配置文件）"""
    data = {
        "xq_a_token": xq_a_token,
        "u": u,
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "note": "雪球 API Token，Playwright 自动获取。过期特征: 接口返回 error_code: 400016",
    }
    TOKEN_JSON.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    _log(f"✅ snowball_token.json 已更新")


def verify_token(xq_a_token: str, u: str) -> bool:
    """验证 Token 是否有效"""
    try:
        import pysnowball as ball
        ball.set_token(f"xq_a_token={xq_a_token}; u={u}")
        data = ball.quotec("SZ300750")
        if isinstance(data, dict) and data.get("error_code") == 0:
            price = data.get("data", [{}])[0].get("current", "?")
            _log(f"✅ Token 有效! 宁德时代当前价: {price}")
            return True
        return False
    except Exception as e:
        _log(f"❌ Token 验证异常: {e}")
        return False


# ============================================================
# Playwright 登录
# ============================================================

def _find_login_trigger(page):
    """查找页面上的登录触发元素"""
    selectors = [
        "a[href*='login']",
        "a.nav__login",
        "a.login-btn",
        "a:has-text('登录')",
        "//a[contains(text(),'登录')]",
        "button:has-text('登录')",
        "div[class*='login'] a",
        "span:has-text('登录')",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                return el
        except Exception:
            continue
    return None


def _find_username_field(page):
    """查找用户名输入框"""
    selectors = [
        "input[name='username']",
        "input[class*='username']",
        "input[class*='phone']",
        "input[placeholder*='手机']",
        "input[placeholder*='账号']",
        "input[type='text']",
        "//input[@type='text']",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                return el
        except Exception:
            continue
    return None


def _find_password_field(page):
    """查找密码输入框"""
    selectors = [
        "input[name='password']",
        "input[class*='password']",
        "input[placeholder*='密码']",
        "input[type='password']",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                return el
        except Exception:
            continue
    return None


def _find_submit_button(page):
    """查找登录提交按钮"""
    selectors = [
        "button[type='submit']",
        "button:has-text('登录')",
        "div[class*='submit'] button",
        "//button[contains(text(),'登录')]",
        "//div[contains(@class,'submit')]//button",
        "input[type='submit']",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                return el
        except Exception:
            continue
    return None


def login_via_playwright() -> tuple[str, str]:
    """用 Playwright 无头浏览器登录雪球，返回 (xq_a_token, u)"""
    _log("启动 Playwright 无头浏览器...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # 注入反检测脚本
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        """)

        page = ctx.new_page()

        # ── 第一步：打开首页 ──
        _log("🌐 打开 xueqiu.com...")
        try:
            page.goto("https://xueqiu.com", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
        except PwTimeout:
            _log("⚠️  首页加载超时，继续尝试...")

        # ── 第二步：点击登录按钮 ──
        _log("🔍 查找登录按钮...")
        login_trigger = _find_login_trigger(page)
        if login_trigger:
            _log("点击登录按钮...")
            try:
                login_trigger.click(timeout=5000)
                page.wait_for_timeout(2000)
            except Exception as e:
                _log(f"⚠️  点击登录按钮失败: {e}")
        else:
            _log("⚠️  未找到登录按钮，尝试直接填写表单...")

        # ── 第三步：填入用户名和密码 ──
        _log("🔑 填入凭证...")
        username_el = _find_username_field(page)
        password_el = _find_password_field(page)

        if username_el and password_el:
            try:
                username_el.fill(USERNAME)
                page.wait_for_timeout(500)
                password_el.fill(PASSWORD)
                page.wait_for_timeout(500)
                _log("✅ 已填入用户名和密码")
            except Exception as e:
                _log(f"⚠️  填入表单失败: {e}")
        else:
            # 如果找不到表单字段，尝试直接注入 JavaScript 方式
            _log("尝试 JS 注入方式填写表单...")
            try:
                page.evaluate(f"""
                    (() => {{
                        const inputs = document.querySelectorAll('input');
                        let phone = null, pwd = null;
                        for (const inp of inputs) {{
                            const t = (inp.type || '').toLowerCase();
                            const ph = (inp.placeholder || '').toLowerCase();
                            const nm = (inp.name || '').toLowerCase();
                            if (!phone && (t === 'text' || ph.includes('手机') || ph.includes('账号') || nm === 'username')) {{
                                phone = inp;
                            }}
                            if (!pwd && (t === 'password' || ph.includes('密码') || nm === 'password')) {{
                                pwd = inp;
                            }}
                        }}
                        if (phone) {{
                            phone.value = '{USERNAME}';
                            phone.dispatchEvent(new Event('input', {{bubbles: true}}));
                            phone.dispatchEvent(new Event('change', {{bubbles: true}}));
                        }}
                        if (pwd) {{
                            pwd.value = '{PASSWORD}';
                            pwd.dispatchEvent(new Event('input', {{bubbles: true}}));
                            pwd.dispatchEvent(new Event('change', {{bubbles: true}}));
                        }}
                        return {{phone: !!phone, pwd: !!pwd}};
                    }})()
                """)
                page.wait_for_timeout(1000)
                _log("✅ JS 填充完成")
            except Exception as e:
                _log(f"❌ JS 填充失败: {e}")
                browser.close()
                return "", ""

        # ── 第四步：点击提交按钮 ──
        submit_btn = _find_submit_button(page)
        if submit_btn:
            _log("点击登录提交按钮...")
            try:
                submit_btn.click(timeout=5000)
            except Exception as e:
                _log(f"⚠️  点击提交按钮失败，尝试回车提交: {e}")
                try:
                    page.keyboard.press("Enter")
                except Exception:
                    pass
        else:
            _log("未找到提交按钮，尝试回车提交...")
            try:
                page.keyboard.press("Enter")
            except Exception:
                pass

        # ── 第五步：等待登录完成 ──
        _log("⏳ 等待登录完成...")
        page.wait_for_timeout(5000)

        # 检测是否出现验证码
        page_text = page.content().lower()
        if "验证码" in page_text or "captcha" in page_text or "slide" in page_text:
            _log("⚠️  出现验证码，尝试等待自动通过...")
            page.wait_for_timeout(8000)

        # 再等一会儿确保 cookie 生成
        page.wait_for_timeout(3000)

        # ── 第六步：提取 Cookie ──
        cookies = ctx.cookies()
        xq_a_token = ""
        u = ""
        for c in cookies:
            if c["name"] == "xq_a_token":
                xq_a_token = c["value"]
            elif c["name"] == "u":
                u = c["value"]

        browser.close()

        if xq_a_token:
            _log(f"✅ 获取到 xq_a_token: {xq_a_token[:20]}...")
            _log(f"✅ 获取到 u: {u}")
            return xq_a_token, u
        else:
            _log("❌ 未获取到 xq_a_token cookie，登录可能失败")
            return "", ""


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 50)
    print("  雪球 Token 获取 — Playwright 无头浏览器")
    print("=" * 50)
    print()

    force_login = "--force" in sys.argv
    verify_only = "--verify" in sys.argv

    # 读取当前 Token
    xq_a_token, u = read_current_token()
    if xq_a_token:
        _log(f"当前 xq_a_token: {xq_a_token[:20]}...")
        _log(f"当前 u: {u}")
        print()
    else:
        _log("⚠️  未找到现有 Token")

    # 仅验证模式
    if verify_only:
        if xq_a_token:
            _log("验证 Token...")
            valid = verify_token(xq_a_token, u)
            sys.exit(0 if valid else 1)
        else:
            _log("❌ 无 Token 可验证")
            sys.exit(1)

    # 验证当前 Token（除非 --force）
    if xq_a_token and not force_login:
        print("验证当前 Token...")
        if verify_token(xq_a_token, u):
            print()
            _log("Token 有效，无需更新。如需强制重新登录请加 --force")
            return

    # 登录获取新 Token
    print()
    _log("尝试 Playwright 登录获取新 Token...")
    print()
    new_token, new_u = login_via_playwright()

    if not new_token:
        print()
        _log("=" * 50)
        _log("❌ Playwright 登录失败")
        _log("")
        _log("可能原因:")
        _log("  1. 页面结构已变化（选择器不匹配）")
        _log("  2. 需要手动处理验证码")
        _log("  3. 网络问题")
        _log("")
        _log("请手动更新 Token:")
        _log("  1. 浏览器打开 https://xueqiu.com 并登录")
        _log("  2. F12 → Application → Cookies → xq_a_token")
        _log("  3. 运行 python3 login_xueqiu_playwright.py --force")
        _log("     或将值填入 token.md")
        _log("=" * 50)
        sys.exit(1)

    # 验证新 Token
    print()
    _log("验证新 Token...")
    if not verify_token(new_token, new_u):
        _log("⚠️  新 Token 验证失败，可能已过期或登录异常")
        sys.exit(1)

    # 更新文件
    print()
    _log("更新 Token 文件...")
    update_token_md(new_token, new_u)
    update_token_json(new_token, new_u)

    print()
    _log("✅ 全部完成")


if __name__ == "__main__":
    main()
