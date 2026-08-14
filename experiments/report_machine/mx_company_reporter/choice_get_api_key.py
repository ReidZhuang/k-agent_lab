"""choice.eastmoney.com/mcp 无头登录取 API Key

凭据来源(按优先级):
    1. JSON 配置文件 ~/.config/choice_mcp_credentials.json:
       {"primary": {"username","password"}, "backups": [{u,p}, ...]} (备用1~4 按序)
       --index 0 = primary; 1..4 = backups[0..3]
    2. 环境变量(JSON 缺失时回退):
       CHOICE_MCP_USERNAME  东方财富账号(手机号/邮箱)
       CHOICE_MCP_PASSWORD  登录密码
       CHOICE_MCP_API_KEY   已保存的 API Key(可选,仅用于对比提示)

登录方式:
    --storage PATH   优先用已保存的浏览器登录态(storage_state JSON)免登录拿 Key。
                     页面未登录(登录态失效)时自动回退完整登录流程(账号密码+滑块)。

用法:
    python choice_get_api_key.py                       # 主凭据登录并打印 API Key
    python choice_get_api_key.py --index 1            # 备用1 登录
    python choice_get_api_key.py --index 1 --json     # 备用1 登录, stdout 输出 JSON
    python choice_get_api_key.py --storage ~/.config/choice_storage.json --json
                                                       # storage 复用(免滑块), 失效时回退登录
    python choice_get_api_key.py --save               # 登录,打印并把 Key 写入 ~/.config/choice_mcp_api_key
    python choice_get_api_key.py --update-openclaw    # 登录,并把 Key 更新到 openclaw.json 的 mx-ds-mcp em_api_key(自动备份)

--json 输出格式:
    成功: {"ok": true,  "key": "em_...", "index": 0, "elapsed_s": 42.1}
    失败: {"ok": false, "reason": "登录超时...", "index": 0, "elapsed_s": 33.5}
    人类可读日志始终走 stderr。

返回: 成功 exit 0; 失败 exit 1; 缺凭据 exit 2。
"""
import json
import pathlib
import shutil
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

MCP_URL = "https://choice.eastmoney.com/mcp/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
KEY_PATTERN = re.compile(r"em_[A-Za-z0-9]{20,}")
CREDENTIALS_FILE = pathlib.Path.home() / ".config" / "choice_mcp_credentials.json"


def _env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"[ERROR] 缺少环境变量 {name}(请先 export, 见 ~/.bashrc)", file=sys.stderr)
        sys.exit(2)
    return val


def load_credentials(index: int | None = None) -> dict:
    """返回 {"username", "password"}。

    JSON 配置文件存在时: index 为 None/0 → primary; 1..4 → backups[index-1]。
    JSON 缺失: 回退环境变量(保持旧行为)。
    索引越界/格式错误: 打印错误并 sys.exit(2)。
    """
    if CREDENTIALS_FILE.exists():
        try:
            data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[ERROR] 凭据配置文件 {CREDENTIALS_FILE} 不是合法 JSON: {e}", file=sys.stderr)
            sys.exit(2)
        if index in (None, 0):
            cred = data.get("primary")
            if not isinstance(cred, dict) or not cred.get("username") or not cred.get("password"):
                print("[ERROR] 凭据配置文件缺少 primary(username/password)", file=sys.stderr)
                sys.exit(2)
            return cred
        backups = data.get("backups") or []
        if index - 1 >= len(backups):
            print(f"[ERROR] --index {index} 超出备用凭据数量({len(backups)} 套)", file=sys.stderr)
            sys.exit(2)
        cred = backups[index - 1]
        if not isinstance(cred, dict) or not cred.get("username") or not cred.get("password"):
            print(f"[ERROR] 备用凭据[{index - 1}]缺少 username/password", file=sys.stderr)
            sys.exit(2)
        return cred
    # 回退环境变量(旧行为)
    return {"username": _env("CHOICE_MCP_USERNAME"), "password": _env("CHOICE_MCP_PASSWORD")}


def login_and_get_key(page, username: str, password: str) -> str:
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
    login_frame.fill("#txt_account", username)
    login_frame.fill("#txt_pwd", password)
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


def get_key_via_storage(page, storage_path: str) -> str:
    """storage_state 复用: 已登录态直接打开页面拿 Key, 无需账号密码/滑块。

    页面仍显示登录按钮(登录态失效)时抛 RuntimeError, 由调用方回退完整登录流程。
    """
    if not pathlib.Path(storage_path).exists():
        raise RuntimeError(f"storage 文件不存在: {storage_path}")
    page.goto(MCP_URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    if page.query_selector("button.loginBtn___pFTz0"):
        raise RuntimeError(f"storage 登录态已失效({storage_path})")
    # 点"查询 API Key" → 弹窗含 Key
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


OPENCLAW_JSON = pathlib.Path.home() / ".openclaw" / "openclaw.json"


def update_openclaw(key: str) -> bool:
    """把 Key 更新到 openclaw.json 的 mcp.servers.mx-ds-mcp.headers.em_api_key

    修改前备份为 openclaw.json.bak.<旧key前8位>。返回 True = 处理成功
    (key 已更新或本来就相同); False = 失败(openclaw.json 缺失/路径错误)。
    key 是否发生变化需另读 openclaw.json 对比(服务端判断是否重启 gateway)。
    """
    if not OPENCLAW_JSON.exists():
        print(f"[ERROR] 未找到 {OPENCLAW_JSON}", file=sys.stderr)
        return False
    with open(OPENCLAW_JSON) as f:
        cfg = json.load(f)
    try:
        headers = cfg["mcp"]["servers"]["mx-ds-mcp"]["headers"]
    except KeyError:
        print("[ERROR] openclaw.json 缺少 mcp.servers.mx-ds-mcp.headers 路径", file=sys.stderr)
        return False
    old = headers.get("em_api_key", "")
    if old == key:
        print("[INFO] openclaw.json em_api_key 已是最新, 无需更新", file=sys.stderr)
        return True
    backup = OPENCLAW_JSON.with_name(f"openclaw.json.bak.{old[:8] or 'empty'}")
    shutil.copy2(OPENCLAW_JSON, backup)
    print(f"[INFO] 已备份旧配置 -> {backup}", file=sys.stderr)
    headers["em_api_key"] = key
    with open(OPENCLAW_JSON, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("[INFO] openclaw.json em_api_key 已更新 (mx-ds-mcp)", file=sys.stderr)
    return True


def main() -> int:
    save = "--save" in sys.argv
    update = "--update-openclaw" in sys.argv
    want_json = "--json" in sys.argv
    index = 0
    if "--index" in sys.argv:
        try:
            index = int(sys.argv[sys.argv.index("--index") + 1])
        except (ValueError, IndexError):
            print("[ERROR] --index 需要整数参数(0=主凭据, 1~4=备用)", file=sys.stderr)
            return 2
    if index < 0 or index > 4:
        print("[ERROR] --index 范围 0~4(0=主凭据, 1~4=备用)", file=sys.stderr)
        return 2

    t0 = time.time()
    cred = load_credentials(index)
    label = "主凭据" if index == 0 else f"备用{index}"
    storage = None
    if "--storage" in sys.argv:
        try:
            storage = sys.argv[sys.argv.index("--storage") + 1]
        except IndexError:
            print("[ERROR] --storage 需要参数(playwright storage_state JSON 路径)", file=sys.stderr)
            return 2

    def _fail(reason: str) -> int:
        elapsed = round(time.time() - t0, 1)
        if want_json:
            print(json.dumps({"ok": False, "reason": reason, "index": index,
                              "elapsed_s": elapsed}, ensure_ascii=False))
        print(f"[ERROR] {label}登录失败: {reason}", file=sys.stderr)
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            channel="chromium",  # 新无头模式, 指纹接近真实浏览器
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        # storage_state 复用: 免登录直接拿 Key
        if storage:
            ctx = browser.new_context(
                storage_state=storage,
                user_agent=UA,
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )
            page = ctx.new_page()
            try:
                key = get_key_via_storage(page, storage)
                print(f"[INFO] storage 复用成功(免登录)", file=sys.stderr)
            except Exception as ex:
                print(f"[WARN] storage 复用失败({ex}), 回退完整登录流程", file=sys.stderr)
                ctx.close()
                key = None
            if key is not None:
                browser.close()
                return _finish(key, index, t0, want_json, save, update)
        # 完整登录流程(账号密码 + 滑块)
        ctx = browser.new_context(
            user_agent=UA,
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        page = ctx.new_page()
        try:
            key = login_and_get_key(page, cred["username"], cred["password"])
        except Exception as ex:
            page.screenshot(path="/tmp/choice_login_fail.jpg", type="jpeg", quality=80)
            browser.close()
            return _fail(str(ex))
        browser.close()

    elapsed = round(time.time() - t0, 1)
    if want_json:
        print(json.dumps({"ok": True, "key": key, "index": index, "elapsed_s": elapsed},
                         ensure_ascii=False))
    else:
        print(key)
    print(f"[INFO] {label}登录成功, 耗时 {elapsed}s", file=sys.stderr)

    # 与已保存 Key 对比提示
    saved = os.environ.get("CHOICE_MCP_API_KEY", "").strip()
    if saved and saved != key:
        print(f"[WARN] 新 Key 与 CHOICE_MCP_API_KEY 不一致, 请更新 ~/.bashrc", file=sys.stderr)

    if save:
        path = pathlib.Path.home() / ".config" / "choice_mcp_api_key"
        path.write_text(key + "\n")
        print(f"[INFO] Key 已写入 {path}", file=sys.stderr)

    if update:
        if not update_openclaw(key):
            return 1
    return 0


def _finish(key: str, index: int, t0: float, want_json: bool, save: bool, update: bool) -> int:
    """登录/storage 成功后统一收尾: 输出、保存、更新 openclaw。"""
    elapsed = round(time.time() - t0, 1)
    if want_json:
        print(json.dumps({"ok": True, "key": key, "index": index, "elapsed_s": elapsed},
                         ensure_ascii=False))
    else:
        print(key)
    label = "主凭据" if index == 0 else f"备用{index}"
    print(f"[INFO] {label}取 Key 成功, 耗时 {elapsed}s", file=sys.stderr)
    saved = os.environ.get("CHOICE_MCP_API_KEY", "").strip()
    if saved and saved != key:
        print(f"[WARN] 新 Key 与 CHOICE_MCP_API_KEY 不一致, 请更新 ~/.bashrc", file=sys.stderr)
    if save:
        path = pathlib.Path.home() / ".config" / "choice_mcp_api_key"
        path.write_text(key + "\n")
        print(f"[INFO] Key 已写入 {path}", file=sys.stderr)
    if update:
        if not update_openclaw(key):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
