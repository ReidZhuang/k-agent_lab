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
    --challenge-dir DIR  滑块人工验证模式: 出现滑块时把拼图(背景+滑块截图)写入
                     DIR/challenge.json, 等待前端用户完成拼图后写回 DIR/result.json,
                     再按用户轨迹在页面中重放鼠标事件完成验证(实验/人工兜底)。
                     不传则出现滑块时走自动等待(通常会被风控拦截)。
    --cdp [URL]     连接带远程调试端口的 Chrome 登录(指纹=真实用户, 点击验证自动
                     放行, 无需人工拼图)。URL 缺省 http://127.0.0.1:9222。若端口
                     不可达, 自动后台启动 Chrome(CDP_CHROME_CMD 环境变量可覆盖
                     启动命令)并等待就绪, 无需手动开浏览器。

登录全程采用人类化操作(鼠标分段移动+随机停顿+逐字符输入+协议框划动),
降低触发反爬滑块的概率。滑块人工验证失败/超时会自动重新触发验证码。

用法:
    python choice_get_api_key.py                       # 主凭据登录并打印 API Key
    python choice_get_api_key.py --index 1            # 备用1 登录
    python choice_get_api_key.py --index 1 --json     # 备用1 登录, stdout 输出 JSON
    python choice_get_api_key.py --storage ~/.config/choice_storage.json --json
                                                       # storage 复用(免滑块), 失效时回退登录
    python choice_get_api_key.py --challenge-dir ~/.config/mx_login_challenge --json
                                                       # 滑块人工验证模式
    python choice_get_api_key.py --save               # 登录,打印并把 Key 写入 ~/.config/choice_mcp_api_key
    python choice_get_api_key.py --update-openclaw    # 登录,并把 Key 更新到 openclaw.json 的 mx-ds-mcp em_api_key(自动备份)

--json 输出格式:
    成功: {"ok": true,  "key": "em_...", "index": 0, "elapsed_s": 42.1}
    失败: {"ok": false, "reason": "登录超时...", "index": 0, "elapsed_s": 33.5}
    人类可读日志始终走 stderr。

返回: 成功 exit 0; 失败 exit 1; 缺凭据 exit 2。
"""
import base64
import json
import math
import os
import pathlib
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

MCP_URL = "https://choice.eastmoney.com/mcp/"

# CDP 模式 Chrome 自启配置(端口不可达时自动启动, 无需手动开浏览器)
CDP_PORT = 9222
CDP_CHROME_DATA_DIR = "/tmp/chrome-cdp-test"
CDP_CHROME_CMD_DEFAULT = (
    "google-chrome --remote-debugging-port=%d --user-data-dir=%s "
    "--no-first-run --no-default-browser-check --no-sandbox"
) % (CDP_PORT, CDP_CHROME_DATA_DIR)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
KEY_PATTERN = re.compile(r"em_[A-Za-z0-9]{20,}")
CREDENTIALS_FILE = pathlib.Path.home() / ".config" / "choice_mcp_credentials.json"

CHALLENGE_TTL = 120            # 拼图挑战有效期(秒), 过期自动重新触发
REPLAY_JUDGE_TIMEOUT = 8       # 重放提交后的判定窗口(秒)
CHALLENGE_TOTAL_TIMEOUT = 420  # 人工验证整体上限(秒)


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


# ---------- 人类化动作(降低反爬触发概率) ----------

def _rs(a: float, b: float) -> float:
    return random.uniform(a, b)


def _human_click_at(mouse, x: float, y: float):
    """仿人类点击: 从远处分段移动(先快后慢+随机抖动), 停顿后按下"""
    mouse.move(x + _rs(-320, -120), y + _rs(-160, 120))
    time.sleep(_rs(0.25, 0.7))
    mouse.move(x + _rs(-45, -12), y + _rs(-35, 35), steps=random.randint(5, 9))
    time.sleep(_rs(0.12, 0.4))
    mouse.move(x + _rs(-8, -2), y + _rs(-8, 8), steps=random.randint(3, 5))
    time.sleep(_rs(0.15, 0.5))
    mouse.move(x, y, steps=2)
    time.sleep(_rs(0.12, 0.4))
    mouse.click(x, y)
    time.sleep(_rs(0.15, 0.5))


def _el_box(el) -> dict:
    return el.bounding_box() or {"x": 0, "y": 0, "width": 1, "height": 1}


def _human_click_el(page, el):
    """人类化点击元素(中心附近随机偏移)"""
    box = _el_box(el)
    _human_click_at(page.mouse,
                    box["x"] + box["width"] * _rs(0.35, 0.65),
                    box["y"] + box["height"] * _rs(0.35, 0.65))


def _human_type(page, el, text: str):
    """点击聚焦后逐字符敲击输入(模仿真人打字节奏)

    - 每字符间隔 90-250ms(打字速度波动)
    - 每 3-7 个字符随机一次"停顿" 300-900ms(看屏幕/思考)
    - 收尾停顿(确认输入完成再移开)
    """
    _human_click_el(page, el)
    time.sleep(_rs(0.4, 0.9))
    for i, ch in enumerate(text):
        page.keyboard.type(ch, delay=0)
        time.sleep(_rs(0.09, 0.25))
        if (i + 1) % random.randint(3, 7) == 0:
            time.sleep(_rs(0.3, 0.9))
    time.sleep(_rs(0.3, 0.7))


def _human_slide_then_click(page, el):
    """在勾选框上划动一下再点击选中(模拟鼠标划过协议文本)"""
    box = _el_box(el)
    y = box["y"] + box["height"] / 2
    x0 = box["x"] - 60
    x1 = box["x"] + box["width"] * _rs(0.2, 0.4)
    page.mouse.move(x0, y)
    time.sleep(_rs(0.15, 0.4))
    steps = random.randint(8, 14)
    for i in range(steps):
        t = i / steps
        page.mouse.move(x0 + (x1 - x0) * t, y + math.sin(t * math.pi) * _rs(-6, 6))
        time.sleep(_rs(0.03, 0.09))
    time.sleep(_rs(0.25, 0.6))
    _human_click_at(page.mouse,
                    box["x"] + box["width"] * _rs(0.1, 0.3),
                    box["y"] + box["height"] * _rs(0.3, 0.7))


# ---------- 滑块人工验证(文件协议: challenge.json / result.json) ----------

def _atomic_write_json(path: pathlib.Path, data: dict):
    """原子写 JSON(tmp + os.replace), 防止对端读到半截文件"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _find_frame_with(page, selectors: list[str], timeout: float):
    """轮询查找含任一可见选择器元素的 frame, 返回 (frame, el) 或 (None, None)。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for f in page.frames:
            try:
                for sel in selectors:
                    el = f.query_selector(sel)
                    if el and el.is_visible():
                        return f, el
            except Exception:
                continue
        page.wait_for_timeout(400)
    return None, None


def _shot_el_b64(el) -> str | None:
    """元素截图 → PNG base64(不依赖图片 URL, 与页面渲染 1:1)"""
    try:
        return base64.b64encode(el.screenshot(type="png")).decode("ascii")
    except Exception as e:
        print(f"[WARN] 元素截图失败: {e}", file=sys.stderr)
        return None


def _shot_region_b64(page, region: dict) -> str | None:
    """区域截图(clip) → PNG base64"""
    try:
        return base64.b64encode(
            page.screenshot(clip=region, type="png")).decode("ascii")
    except Exception as e:
        print(f"[WARN] 区域截图失败: {e}", file=sys.stderr)
        return None


def _replay_track(page, region: dict, slice_box: dict, result: dict):
    """按用户轨迹重放鼠标拖动(CDP 真实事件, isTrusted=true)。

    track: [{x, y, t}] 相对背景图左上角坐标 + 相对按下的毫秒时间。
    轨迹为空时退化为"按下→直接拖到 distance 距离"。
    """
    x0 = slice_box["x"] + slice_box["width"] / 2
    y0 = slice_box["y"] + slice_box["height"] / 2
    page.mouse.move(x0, y0)
    page.mouse.down()
    track = result.get("track") or []
    if track:
        prev_t = 0.0
        for pt in track:
            t = float(pt.get("t", 0))
            dt = t - prev_t
            if dt < 30:
                continue
            px = region["x"] + float(pt.get("x", 0))
            py = region["y"] + float(pt.get("y", 0))
            page.mouse.move(px, py)
            page.wait_for_timeout(min(dt, 1200))  # 按用户节奏, 上限防异常
            prev_t = t
    else:
        distance = float(result.get("distance", 0))
        steps = random.randint(5, 8)
        for i in range(1, steps + 1):
            t = i / steps
            page.mouse.move(x0 + distance * t, y0 + _rs(-4, 4))
            page.wait_for_timeout(_rs(30, 90))
    page.mouse.up()
    print(f"[INFO] 已按人工轨迹重放: {len(track)} 点, 距离 {result.get('distance', 0):.1f}px",
          file=sys.stderr)


def _wait_result(res_file: pathlib.Path, timeout: float, chal_id: str) -> dict | None:
    """轮询 result.json; 返回 result dict 或 None(超时/id 不匹配)。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if res_file.exists():
            try:
                data = json.loads(res_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                time.sleep(0.5)
                continue
            if data.get("id") == chal_id:
                return data
        time.sleep(1.0)
    return None


def _judge_after_replay(page) -> bool:
    """重放提交后的判定: 登录按钮消失=通过; 滑块重现=失败。"""
    deadline = time.time() + REPLAY_JUDGE_TIMEOUT
    while time.time() < deadline:
        if not page.query_selector("button.loginBtn___pFTz0"):
            return True
        _, el = _find_frame_with(page, [".em_slice"], 1)
        if el:
            return False
        page.wait_for_timeout(500)
    return False


def _retrigger_slider(page):
    """重新触发验证码(失败/超时后)。返回新的验证码 frame 或 None。"""
    frame, el = _find_frame_with(page, [".em_init"], 8)
    if not el:
        frame, el = _find_frame_with(page, [".em_init"], 10)
    if not el:
        print("[WARN] 重新触发失败: 未找到 .em_init(风控可能已锁定)", file=sys.stderr)
        return None
    _human_click_el(page, el)
    cap, _ = _find_frame_with(page, [".em_slice"], 8)
    if not cap:
        print("[WARN] 重新触发后滑块未出现(风控可能已锁定)", file=sys.stderr)
        return None
    return cap


def _solve_slider_challenge(page, cap_frame, challenge_dir: str) -> bool:
    """人工拼图验证主循环: 提取拼图 → 推送 → 等人工 → 重放 → 判定。

    失败/超时自动重新触发验证码(更新 challenge id, 前端自动刷新拼图)。
    返回 True = 验证通过。
    """
    cdir = pathlib.Path(challenge_dir)
    cdir.mkdir(parents=True, exist_ok=True)
    chal_file = cdir / "challenge.json"
    res_file = cdir / "result.json"
    deadline = time.time() + CHALLENGE_TOTAL_TIMEOUT
    round_no = 0
    while time.time() < deadline:
        round_no += 1
        # 1) 提取拼图(背景区域 + 滑块元素)
        try:
            region_el = cap_frame.query_selector(".em_cut_bg_slice")
            if not region_el:
                # 兜底: 用页面上最大的 .em_ 容器(联调时确认精确选择器)
                region_el = cap_frame.query_selector("[class*='em_'][class*='cut']")
            if not region_el:
                raise RuntimeError("未找到验证码背景容器")
            region = region_el.bounding_box()
            slice_el = cap_frame.query_selector(".em_slice")
            if not slice_el:
                raise RuntimeError("未找到 .em_slice 滑块元素")
            slice_box = slice_el.bounding_box()
        except Exception as e:
            print(f"[WARN] 提取拼图失败({e}), 重新触发", file=sys.stderr)
            cap_frame = _retrigger_slider(page)
            if not cap_frame:
                return False
            continue
        bg_b64 = _shot_region_b64(page, region)
        slice_b64 = _shot_el_b64(slice_el)
        if not bg_b64 or not slice_b64:
            cap_frame = _retrigger_slider(page)
            if not cap_frame:
                return False
            continue
        # 2) 写 challenge.json(原子)
        chal = {
            "id": f"r{round_no}",
            "bg": bg_b64, "slice": slice_b64,
            "bg_w": round(region["width"], 1), "bg_h": round(region["height"], 1),
            "slice_w": round(slice_box["width"], 1), "slice_h": round(slice_box["height"], 1),
            "slider_x": round(slice_box["x"] - region["x"], 1),
            "slider_y": round(slice_box["y"] - region["y"], 1),
            "expires_at": int(time.time()) + CHALLENGE_TTL,
            "status": "waiting",
        }
        _atomic_write_json(chal_file, chal)
        print(f"[INFO] 拼图挑战已推送(round {round_no}), 等待人工完成 {CHALLENGE_TTL}s ...",
              file=sys.stderr)
        # 3) 等人工结果
        result = _wait_result(res_file, CHALLENGE_TTL + 15, chal["id"])
        if result is None:
            print("[WARN] 人工挑战超时, 重新触发验证码", file=sys.stderr)
            _safe_unlink(res_file)
            cap_frame = _retrigger_slider(page)
            if not cap_frame:
                return False
            continue
        # 4) CDP 重放用户轨迹
        _replay_track(page, region, slice_box, result)
        # 5) 判定: 通过 → 删除挑战文件(前端据此判定成功)并返回
        if _judge_after_replay(page):
            print("[INFO] 拼图验证通过, 登录已继续", file=sys.stderr)
            _safe_unlink(chal_file)
            return True
        print("[WARN] 拼图验证未通过(提交被拒), 重新触发验证码", file=sys.stderr)
        _safe_unlink(res_file)
        cap_frame = _retrigger_slider(page)
        if not cap_frame:
            return False
    print("[ERROR] 人工拼图验证总超时", file=sys.stderr)
    return False


def _safe_unlink(path: pathlib.Path):
    try:
        path.unlink()
    except OSError:
        pass


def _handle_slider_after_init(page, challenge_dir: str | None):
    """点击 .em_init 后: 出现滑块 → 人工挑战(有 challenge_dir)或自动等待; 无滑块 → 等待"""
    cap, el = _find_frame_with(page, [".em_slice", ".em_init"], 10)
    if cap and cap.query_selector(".em_slice"):
        print("[INFO] 检测到滑块验证码", file=sys.stderr)
        if challenge_dir:
            if not _solve_slider_challenge(page, cap, challenge_dir):
                raise RuntimeError("人工滑块验证失败(多次失败/超时)")
        else:
            print("[INFO] 无 --challenge-dir, 走自动等待(可能被风控拦截)", file=sys.stderr)
    else:
        print("[INFO] 未检测到滑块(点击验证后直接通过, 或风控拦截)", file=sys.stderr)


# ---------- 登录主流程 ----------

def login_and_get_key(page, username: str, password: str,
                      challenge_dir: str | None = None) -> str:
    """执行登录并从'查询 API Key'弹窗提取 Key, 返回 Key 字符串

    全程人类化操作(鼠标移动/逐字符输入), 触发滑块时走 challenge_dir 人工验证。
    """
    page.goto(MCP_URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    # 1. 点登录按钮 → Login7 iframe
    login_btn = page.query_selector("button.loginBtn___pFTz0")
    if not login_btn:
        raise RuntimeError("未找到登录按钮(可能已登录或页面结构变化)")
    _human_click_el(page, login_btn)
    page.wait_for_timeout(4000)

    login_frame = None
    for f in page.frames:
        if "exaccount2" in f.url:
            login_frame = f
            break
    if not login_frame:
        raise RuntimeError("未找到登录 iframe")

    # 2. 切"账号登录"tab, 勾选协议(划过再点), 逐字符填凭据
    _human_click_el(page, login_frame.query_selector("span.account"))
    time.sleep(_rs(0.4, 0.9))
    _human_slide_then_click(page, login_frame.query_selector("img.selectbox"))
    _human_type(page, login_frame.query_selector("#txt_account"), username)
    time.sleep(_rs(0.2, 0.5))
    _human_type(page, login_frame.query_selector("#txt_pwd"), password)
    time.sleep(_rs(0.3, 0.8))
    _human_click_el(page, login_frame.query_selector("button.loginBtn"))
    page.wait_for_timeout(4000)

    # 3. 点"点击开始验证"(em_ 滑块验证)
    clicked = False
    for f in page.frames:
        try:
            el = f.query_selector(".em_init")
            if el and el.is_visible():
                _human_click_el(page, el)
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        raise RuntimeError("未找到'点击开始验证'按钮")

    # 3.5 滑块处理: 人工挑战或自动等待
    _handle_slider_after_init(page, challenge_dir)

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


def _extract_key_from_page(page) -> str:
    """从页面提取 em_ 开头的 API Key(先查弹窗, 再扫全页文本)。

    真实 Chrome 里点"查询 API Key"后弹窗可能出现也可能直接展示;
    探针验证: 页面 body 文本正则即能捕获 em_ 值。
    """
    dialog = page.query_selector(".ant-modal")
    if dialog:
        try:
            m = KEY_PATTERN.search(dialog.inner_text())
            if m:
                return m.group(0)
        except Exception:
            pass
    m = KEY_PATTERN.search(page.evaluate("() => document.body.innerText"))
    if m:
        return m.group(0)
    raise RuntimeError("页面中未找到 em_ 开头的 API Key")


def _click_query_key_btn(page):
    """点'查询 API Key'按钮(登录后页面按钮文案), 返回是否找到并点击。"""
    for e in page.query_selector_all("button, div, span, a"):
        try:
            t = (e.inner_text() or "").strip()
        except Exception:
            continue
        if t == "查询 API Key" and e.evaluate("el => el.tagName") in ("BUTTON", "A", "SPAN"):
            e.click()
            return True
    return False


def login_via_cdp(page, username: str, password: str,
                  challenge_dir: str | None = None) -> str:
    """通过 CDP 连接用户真实 Chrome 登录(指纹=真实用户, 点验证即自动通过)。

    探针(8/14)验证的差异点 vs playwright 自启动浏览器:
    - 登录按钮鼠标点击可能不生效(React 事件未绑定) → DOM click 兜底
    - iframe 内人类化操作(切tab/划协议/逐字符输入/点登录)全部有效
    - 点击 .em_init 后滑块闪现约 0.8s 自动通过, 无需人工拼图
    - Key 提取: 弹窗或全页文本正则均可捕获
    """
    page.goto(MCP_URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)

    # 1. 点登录按钮 → Login7 iframe(鼠标点击失效时 DOM click 兜底)
    login_btn = page.query_selector("button.loginBtn___pFTz0")
    if not login_btn:
        raise RuntimeError("未找到登录按钮(可能已登录或页面结构变化)")
    _human_click_el(page, login_btn)
    page.wait_for_timeout(5000)

    def _find_login_frame():
        return next((f for f in page.frames if "exaccount2" in f.url), None)

    login_frame = _find_login_frame()
    if not login_frame:
        try:
            page.evaluate("() => document.querySelector('button.loginBtn___pFTz0').click()")
        except Exception:
            pass
        page.wait_for_timeout(5000)
        login_frame = _find_login_frame()
    if not login_frame:
        raise RuntimeError("未找到登录 iframe")

    # 2. 切"账号登录"tab, 勾选协议(划过再点), 逐字符填凭据
    _human_click_el(page, login_frame.query_selector("span.account"))
    time.sleep(_rs(0.4, 0.9))
    _human_slide_then_click(page, login_frame.query_selector("img.selectbox"))
    _human_type(page, login_frame.query_selector("#txt_account"), username)
    time.sleep(_rs(0.2, 0.5))
    _human_type(page, login_frame.query_selector("#txt_pwd"), password)
    time.sleep(_rs(0.3, 0.8))
    _human_click_el(page, login_frame.query_selector("button.loginBtn"))
    page.wait_for_timeout(6000)

    # 3. 点"点击开始验证"(em_ 滑块验证; 真实 Chrome 下点击后自动通过)
    clicked = False
    for f in page.frames:
        try:
            el = f.query_selector(".em_init")
            if el and el.is_visible():
                _human_click_el(page, el)
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        raise RuntimeError("未找到'点击开始验证'按钮")

    # 3.5 滑块处理: 人工挑战(若真实 Chrome 也出现拼图)或自动等待
    _handle_slider_after_init(page, challenge_dir)

    # 4. 等登录完成(登录按钮消失)
    for _ in range(30):
        page.wait_for_timeout(1000)
        if not page.query_selector("button.loginBtn___pFTz0"):
            break
    else:
        raise RuntimeError("登录超时, 登录按钮未消失")

    page.wait_for_timeout(2000)

    # 5. 点"查询 API Key"提取 Key
    if not _click_query_key_btn(page):
        raise RuntimeError("未找到'查询 API Key'按钮")
    page.wait_for_timeout(5000)
    return _extract_key_from_page(page)


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


def _cdp_ready(url: str, timeout: float = 3.0) -> bool:
    """检查 CDP 端口是否可连接。"""
    try:
        with urllib.request.urlopen(url + "/json/version", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _login_marker() -> pathlib.Path:
    """登录标记文件(与 Chrome 数据目录同生命周期): 记录当前登录态属于哪个账号。

    完整登录成功后写入; 登录态复用时校验, 防止复用成别的账号的会话
    (例: 切到备用账号后, 次日想回主账号却复用了备用会话)。
    """
    return pathlib.Path(CDP_CHROME_DATA_DIR) / "mx_login_state.json"


def _write_login_marker(index: int) -> None:
    try:
        pathlib.Path(CDP_CHROME_DATA_DIR).mkdir(parents=True, exist_ok=True)
        tmp = _login_marker().with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"index": index, "ts": int(time.time())}),
                       encoding="utf-8")
        tmp.replace(_login_marker())
    except OSError:
        pass


def _marker_matches(index: int) -> bool:
    """登录态复用前校验: 标记存在且 index 一致才可复用。无标记 = 未知, 不可复用。"""
    try:
        m = json.loads(_login_marker().read_text(encoding="utf-8"))
        return m.get("index") == index
    except (OSError, json.JSONDecodeError):
        return False


def _ensure_cdp_chrome(url: str) -> bool:
    """确保带远程调试端口的 Chrome 在跑: 端口可达直接复用, 不可达自动启动。

    自启命令: CDP_CHROME_CMD 环境变量覆盖(默认 google-chrome + 固定数据目录,
    保持登录态)。启动后轮询 /json/version 最多 30s 等就绪。
    """
    if _cdp_ready(url):
        return True
    cmd = os.environ.get("CDP_CHROME_CMD", CDP_CHROME_CMD_DEFAULT)
    print(f"[INFO] CDP 端口不可达, 自动启动 Chrome: {cmd[:90]}...", file=sys.stderr)
    if not os.environ.get("DISPLAY"):
        print("[WARN] 未检测到 DISPLAY(WSLg), Chrome 可能无法显示窗口", file=sys.stderr)
    try:
        subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except FileNotFoundError:
        print("[ERROR] 未找到 google-chrome, 请安装或设置 CDP_CHROME_CMD", file=sys.stderr)
        return False
    t0 = time.time()
    while time.time() - t0 < 30:
        if _cdp_ready(url):
            print(f"[INFO] Chrome 已就绪({(time.time() - t0):.1f}s)", file=sys.stderr)
            return True
        time.sleep(0.5)
    print("[ERROR] Chrome 启动超时(30s), 请手动检查", file=sys.stderr)
    return False


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
    challenge_dir = None
    if "--challenge-dir" in sys.argv:
        try:
            challenge_dir = sys.argv[sys.argv.index("--challenge-dir") + 1]
        except IndexError:
            print("[ERROR] --challenge-dir 需要参数(拼图挑战目录)", file=sys.stderr)
            return 2
    cdp_url = None
    if "--cdp" in sys.argv:
        i = sys.argv.index("--cdp")
        nxt = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        # --cdp 后是参数名(以 - 开头)或没有 → 用缺省 URL
        cdp_url = nxt if nxt.startswith("http") else "http://127.0.0.1:9222"

    def _fail(reason: str) -> int:
        elapsed = round(time.time() - t0, 1)
        if want_json:
            print(json.dumps({"ok": False, "reason": reason, "index": index,
                              "elapsed_s": elapsed}, ensure_ascii=False))
        print(f"[ERROR] {label}登录失败: {reason}", file=sys.stderr)
        return 1

    with sync_playwright() as p:
        if cdp_url:
            # CDP 模式: 连接真实 Chrome(指纹=真实用户, 点验证自动通过);
            # 端口不可达时自动启动 Chrome, 无需手动开浏览器
            if not _ensure_cdp_chrome(cdp_url):
                return _fail("CDP Chrome 不可达且自动启动失败")
            browser = p.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0]
            # 清理遗留的 mcp 页面(多次探针会堆积 tab), 保留一个干净页
            for pg in list(ctx.pages):
                if "choice.eastmoney.com/mcp" in pg.url and pg != ctx.pages[-1]:
                    try:
                        pg.close()
                    except Exception:
                        pass
            page = ctx.new_page()
            try:
                page.goto(MCP_URL, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(6000)
                logged_in = not page.query_selector("button.loginBtn___pFTz0")
                if logged_in and _marker_matches(index):
                    # 登录态存在且标记确认属于目标账号 → 直接提 Key(免账号密码)
                    if not _click_query_key_btn(page):
                        raise RuntimeError("未找到'查询 API Key'按钮(登录态异常)")
                    page.wait_for_timeout(5000)
                    key = _extract_key_from_page(page)
                    print("[INFO] CDP 登录态复用(免账号密码)", file=sys.stderr)
                else:
                    if logged_in:
                        # 登录态属于其他账号(或未知) → 先退出再登录目标账号
                        print(f"[INFO] CDP 当前登录态非目标账号, 退出后登录", file=sys.stderr)
                        ctx.clear_cookies()
                        page.reload(wait_until="domcontentloaded")
                        page.wait_for_timeout(6000)
                    key = login_via_cdp(page, cred["username"], cred["password"],
                                        challenge_dir=challenge_dir)
                    _write_login_marker(index)
                    print("[INFO] CDP 完整登录成功", file=sys.stderr)
            except Exception as ex:
                page.screenshot(path="/tmp/choice_login_fail.jpg", type="jpeg", quality=80)
                browser.close()
                return _fail(str(ex))
            browser.close()
        else:
            browser = p.chromium.launch(
                headless=True,
                channel="chromium",  # 新无头模式, 指纹接近真实浏览器
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            ctx_opts = dict(
                user_agent=UA,
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                device_scale_factor=1,  # 截图与 CSS 像素 1:1, 保证拼图坐标换算
            )
            # storage_state 复用: 免登录直接拿 Key
            if storage:
                ctx = browser.new_context(storage_state=storage, **ctx_opts)
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
            # 完整登录流程(人类化操作 + 滑块人工挑战)
            ctx = browser.new_context(**ctx_opts)
            page = ctx.new_page()
            try:
                key = login_and_get_key(page, cred["username"], cred["password"],
                                        challenge_dir=challenge_dir)
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
