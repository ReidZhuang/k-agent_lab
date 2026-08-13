"""choice.eastmoney.com/mcp 无头登录取 API Key

凭据从环境变量读取(不进 git):
    CHOICE_MCP_USERNAME  东方财富账号(手机号/邮箱)
    CHOICE_MCP_PASSWORD  登录密码
    CHOICE_MCP_API_KEY   已保存的 API Key(可选,仅用于对比提示)

用法:
    python choice_get_api_key.py          # 登录并打印 API Key
    python choice_get_api_key.py --save   # 登录,打印并把 Key 写入 ~/.config/choice_mcp_api_key(不落 git)

返回: 成功打印 Key 后 exit 0; 失败 exit 1。
"""
import os
import re
import sys

from playwright.sync_api import sync_playwright

MCP_URL = "https://choice.eastmoney.com/mcp/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
KEY_PATTERN = re.compile(r"em_[A-Za-z0-9]{20,}")


def _env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"[ERROR] 缺少环境变量 {name}(请先 export, 见 ~/.bashrc)", file=sys.stderr)
        sys.exit(2)
    return val


def login_and_get_key(page) -> str:
    """执行登录并从'查询 API Key'弹窗提取 Key, 返回 Key 字符串"""
    page.goto(MCP_URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    # 1. 点登录按钮 → Login7 iframe
    login_btn = page.query_selector("button.loginBtn___pFTz0")
    if not login_btn:
        raise RuntimeError("未找到登录按钮(可能已登录或页面结构变化)")
    login_btn.click()
    page.wait_for_timeout(4000)

    login_frame = None
    for f in page.frames:
        if "exaccount2" in f.url:
            login_frame = f
            break
    if not login_frame:
        raise RuntimeError("未找到登录 iframe")

    # 2. 切"账号登录"tab, 勾选协议(必须点 img.selectbox), 填凭据
    login_frame.query_selector("span.account").click()
    page.wait_for_timeout(500)
    login_frame.query_selector("img.selectbox").click(position={"x": 5, "y": 5})
    login_frame.fill("#txt_account", _env("CHOICE_MCP_USERNAME"))
    login_frame.fill("#txt_pwd", _env("CHOICE_MCP_PASSWORD"))
    login_frame.query_selector("button.loginBtn").click()
    page.wait_for_timeout(4000)

    # 3. 点"点击开始验证"(em_ 滑块验证, 点击后自动通过)
    clicked = False
    for f in page.frames:
        try:
            el = f.query_selector(".em_init")
            if el and el.is_visible():
                el.click()
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        raise RuntimeError("未找到'点击开始验证'按钮")

    # 4. 等登录完成(登录按钮消失)
    import time
    for _ in range(30):
        page.wait_for_timeout(1000)
        if not page.query_selector("button.loginBtn___pFTz0"):
            break
    else:
        raise RuntimeError("登录超时, 登录按钮未消失")

    page.wait_for_timeout(2000)

    # 5. 点"查询 API Key" → 弹窗含 Key
    key_el = None
    for e in page.query_selector_all("button, div, span, a"):
        try:
            t = (e.inner_text() or "").strip()
        except Exception:
            continue
        if t == "查询 API Key" and e.evaluate("el => el.tagName") in ("BUTTON", "A", "SPAN"):
            key_el = e
            break
    if not key_el:
        raise RuntimeError("未找到'查询 API Key'按钮")
    key_el.click()
    page.wait_for_timeout(5000)

    dialog = page.query_selector(".ant-modal")
    if not dialog:
        raise RuntimeError("未出现 API Key 弹窗")
    m = KEY_PATTERN.search(dialog.inner_text())
    if not m:
        raise RuntimeError("弹窗内未找到 em_ 开头的 API Key")
    return m.group(0)


def main() -> int:
    save = "--save" in sys.argv
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            channel="chromium",  # 新无头模式, 指纹接近真实浏览器
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=UA,
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        page = ctx.new_page()
        try:
            key = login_and_get_key(page)
        except Exception as ex:
            print(f"[ERROR] {ex}", file=sys.stderr)
            page.screenshot(path="/tmp/choice_login_fail.jpg", type="jpeg", quality=80)
            browser.close()
            return 1
        browser.close()

    print(key)

    # 与已保存 Key 对比提示
    saved = os.environ.get("CHOICE_MCP_API_KEY", "").strip()
    if saved and saved != key:
        print(f"[WARN] 新 Key 与 CHOICE_MCP_API_KEY 不一致, 请更新 ~/.bashrc", file=sys.stderr)

    if save:
        import pathlib
        path = pathlib.Path.home() / ".config" / "choice_mcp_api_key"
        path.write_text(key + "\n")
        print(f"[INFO] Key 已写入 {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
