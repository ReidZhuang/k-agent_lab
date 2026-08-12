#!/usr/bin/env python3
"""雪球 Token 自动刷新 — Playwright 无头浏览器登录

用途:
  雪球 API Token 有效期 7-30 天，过期后 `pysnowball` 接口返回
  `error_code: 400016`。本脚本用 Playwright 模拟浏览器登录，
  绕过阿里云 WAF 防护，自动获取新 Token 并更新配置文件。

用法:
  conda run -n stock_agent python3 refresh_token.py          # 检查并刷新
  conda run -n stock_agent python3 refresh_token.py --force  # 强制刷新
  conda run -n stock_agent python3 refresh_token.py --verify # 仅验证

输出文件:
  - data_fetch/midday/config/snowball_token.json   ← 取数代码实际读取的位置
  - (可选) knowledge/pysnowball/token.md           ← 知识库文档中的备份
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
_PROJECT_ROOT = _THIS_DIR.parent
_MIDDAY_CONFIG = _PROJECT_ROOT / "data_fetch" / "midday" / "config"
TOKEN_JSON = _MIDDAY_CONFIG / "snowball_token.json"

# 知识库 token.md（可选，不影响取数）
TOKEN_MD = Path(
    __file__).resolve().parent.parent.parent / "web_search_base" / "knowledge" / "pysnowball" / "token.md"

# ── 凭证 ──────────────────────────────────────────────
USERNAME = "3755631005"
PASSWORD = "zhuang321"

# ── 日志 ──────────────────────────────────────────────
_log = lambda msg: print(f"  {msg}")


# ============================================================
# Token 文件读写
# ============================================================

def read_current_token() -> tuple[str, str]:
    """从 snowball_token.json 读取当前 token"""
    if not TOKEN_JSON.exists():
        return "", ""
    try:
        data = json.loads(TOKEN_JSON.read_text(encoding="utf-8"))
        return data.get("xq_a_token", ""), data.get("u", "")
    except Exception:
        return "", ""


def update_token_json(xq_a_token: str, u: str):
    """更新 snowball_token.json（取数代码实际读取的文件）"""
    data = {
        "xq_a_token": xq_a_token,
        "u": u,
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "note": "雪球 API Token，Playwright 自动获取。过期特征: error_code: 400016",
    }
    TOKEN_JSON.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    _log(f"✅ snowball_token.json 已更新")


def update_token_md(xq_a_token: str, u: str):
    """更新 token.md（知识库文档中的备份）"""
    if not TOKEN_MD.parent.exists():
        _log(f"  ⏭️  跳过 token.md（目录不存在）")
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = f"""# pysnowball Token

> 来源: refresh_token.py Playwright 自动登录 | 上次更新: {ts}
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

运行 `conda run -n stock_agent python3 refresh_token.py` 自动更新。
"""
    TOKEN_MD.write_text(content, encoding="utf-8")
    _log(f"✅ token.md 已更新")


def verify_token(xq_a_token: str, u: str) -> bool:
    """验证 Token 是否有效

    注意: 必须用资金流接口 capital_flow(校验严格, 失效返回 400016)。
    行情接口 quotec 对 token 校验宽松, 失效 token 也能通过(曾导致误报有效)。
    """
    try:
        import pysnowball as ball
        ball.set_token(f"xq_a_token={xq_a_token}; u={u}")
        from pysnowball.capital import capital_flow
        data = capital_flow("SZ000001")
        if isinstance(data, dict) and data.get("error_code") == 0:
            _log(f"✅ Token 有效! (资金流接口 error_code=0)")
            return True
        _log(f"❌ Token 失效! 资金流接口返回: {data.get('error_code') if isinstance(data, dict) else data}")
        return False
    except Exception as e:
        _log(f"❌ Token 验证异常: {e}")
        return False


# ============================================================
# Playwright 登录
# ============================================================

_SELECTORS = {
    "login_trigger": [
        "a[href*='login']",
        "a.nav__login",
        "a.login-btn",
        "a:has-text('登录')",
        "//a[contains(text(),'登录')]",
        "button:has-text('登录')",
        "div[class*='login'] a",
        "span:has-text('登录')",
    ],
    "username": [
        "input[name='username']",
        "input[class*='username']",
        "input[class*='phone']",
        "input[placeholder*='手机']",
        "input[placeholder*='账号']",
        "input[type='text']",
        "//input[@type='text']",
    ],
    "password": [
        "input[name='password']",
        "input[class*='password']",
        "input[placeholder*='密码']",
        "input[type='password']",
    ],
    "submit": [
        "button[type='submit']",
        "button:has-text('登录')",
        "div[class*='submit'] button",
        "//button[contains(text(),'登录')]",
        "//div[contains(@class,'submit')]//button",
        "input[type='submit']",
    ],
}


def _find_visible(page, selectors: list[str], timeout=2000):
    """按优先级查找页面上的可见元素"""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=timeout):
                return el
        except Exception:
            continue
    return None


def _js_fill_login_form(page) -> bool:
    """JS 注入方式填入用户名密码（兜底方案）"""
    try:
        result = page.evaluate(f"""
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
                    const nativeSetter = Object.getOwnPropertyDescriptor(
                        HTMLInputElement.prototype, 'value'
                    ).set;
                    nativeSetter.call(phone, '{USERNAME}');
                    phone.dispatchEvent(new Event('input', {{bubbles: true}}));
                    phone.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
                if (pwd) {{
                    const nativeSetter = Object.getOwnPropertyDescriptor(
                        HTMLInputElement.prototype, 'value'
                    ).set;
                    nativeSetter.call(pwd, '{PASSWORD}');
                    pwd.dispatchEvent(new Event('input', {{bubbles: true}}));
                    pwd.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
                return {{phone: !!phone, pwd: !!pwd}};
            }})()
        """)
        return result.get("phone") and result.get("pwd")
    except Exception:
        return False


def login_via_playwright() -> tuple[str, str]:
    """无头浏览器登录雪球，返回 (xq_a_token, u)"""
    _log("启动 Playwright 无头浏览器...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        # 反检测：隐藏 headless 特征
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        """)
        page = ctx.new_page()

        # ── 1. 打开首页 ──
        _log("🌐 打开 xueqiu.com...")
        try:
            page.goto("https://xueqiu.com", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
        except PwTimeout:
            _log("  ⚠️  首页加载超时，继续尝试...")

        # ── 2. 点击登录按钮 ──
        _log("🔍 点击登录...")
        login_btn = _find_visible(page, _SELECTORS["login_trigger"])
        if login_btn:
            try:
                login_btn.click(timeout=5000)
                page.wait_for_timeout(2000)
            except Exception:
                _log("  ⚠️  点击登录按钮失败（尝试 JS 方式）")

        # ── 3. 填写表单 ──
        _log("🔑 填写凭证...")
        username_el = _find_visible(page, _SELECTORS["username"])
        password_el = _find_visible(page, _SELECTORS["password"])

        filled = False
        if username_el and password_el:
            try:
                username_el.fill(USERNAME)
                password_el.fill(PASSWORD)
                page.wait_for_timeout(500)
                filled = True
                _log("  ✅ 常规方式填入成功")
            except Exception:
                pass

        if not filled:
            _log("  ↪ 尝试 JS 注入方式...")
            if _js_fill_login_form(page):
                _log("  ✅ JS 注入填入成功")
                page.wait_for_timeout(1000)
            else:
                _log("  ❌ 无法填入登录表单")
                browser.close()
                return "", ""

        # ── 4. 提交 ──
        submit_btn = _find_visible(page, _SELECTORS["submit"])
        if submit_btn:
            try:
                submit_btn.click(timeout=5000)
                _log("  ✅ 点击提交按钮")
            except Exception:
                _log("  ↪ 点击失败，尝试回车提交...")
                page.keyboard.press("Enter")
        else:
            _log("  ↪ 未找到提交按钮，按回车提交...")
            page.keyboard.press("Enter")

        # ── 5. 等待登录完成 ──
        _log("⏳ 等待登录完成...")
        page.wait_for_timeout(5000)

        # 检测验证码
        if "验证码" in page.content().lower() or "captcha" in page.content().lower():
            _log("  ⚠️  出现验证码，等待自动通过（最多15s）...")
            page.wait_for_timeout(15000)

        page.wait_for_timeout(3000)

        # ── 6. 提取 Cookie ──
        cookies = ctx.cookies()
        xq_a_token = next((c["value"] for c in cookies if c["name"] == "xq_a_token"), "")
        u = next((c["value"] for c in cookies if c["name"] == "u"), "")

        browser.close()

        if xq_a_token:
            _log(f"  ✅ 获取到 xq_a_token: {xq_a_token[:20]}...")
            _log(f"  ✅ 获取到 u: {u}")
            return xq_a_token, u
        else:
            _log("  ❌ 未获取到 xq_a_token")
            return "", ""


# ============================================================
# 主流程
# ============================================================

def refresh(force: bool = False) -> bool:
    """刷新 Token 的主流程

    Args:
        force: True 时跳过 Token 有效性检查，强制重新登录

    Returns:
        True 表示 Token 有效或已成功刷新，False 表示失败
    """
    xq_a_token, u = read_current_token()

    # 验证现有 Token
    if xq_a_token and not force:
        if verify_token(xq_a_token, u):
            return True
        _log("  Token 已过期，尝试重新登录...")
    else:
        _log("  尝试获取新 Token...")

    print()

    # Playwright 登录
    new_token, new_u = login_via_playwright()
    if not new_token:
        return False

    # 验证新 Token
    print()
    if not verify_token(new_token, new_u):
        _log("  ❌ 新 Token 验证失败")
        return False

    # 更新文件
    print()
    update_token_json(new_token, new_u)
    update_token_md(new_token, new_u)
    return True


def main():
    print("=" * 50)
    print("  雪球 Token 自动刷新")
    print("=" * 50)
    print()

    if "--verify" in sys.argv:
        xq_a_token, u = read_current_token()
        if not xq_a_token:
            _log("❌ snowball_token.json 未找到或内容为空")
            sys.exit(1)
        print("验证 Token...")
        sys.exit(0 if verify_token(xq_a_token, u) else 1)

    force = "--force" in sys.argv
    success = refresh(force=force)

    print()
    if success:
        _log("✅ Token 刷新完成")
    else:
        _log("=" * 50)
        _log("❌ Token 刷新失败")
        _log("")
        _log("可能原因:")
        _log("  1. 页面结构已变化（选择器不匹配）")
        _log("  2. 需要手动处理验证码")
        _log("  3. 网络问题")
        _log("")
        _log("手动更新:")
        _log("  1. 浏览器登录 xueqiu.com")
        _log("  2. F12 → Application → Cookies → 复制 xq_a_token")
        _log("  3. 编辑 data_fetch/midday/config/snowball_token.json")
        _log("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
