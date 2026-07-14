"""执行层适配器：执行 LLM 生成的取数代码

支持两种结果捕获方式：
1. print() 输出（通过 stdout）
2. _result 变量（列表，按顺序对应查询指标）
"""
import os, sys, json, subprocess, tempfile
from pathlib import Path

# 从安全存储加载 TUSHARE_TOKEN
_TOKEN_PATH = os.path.expanduser("~/.secrets/stockagent.env")
if Path(_TOKEN_PATH).exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_TOKEN_PATH)
    except ImportError:
        pass  # dotenv 未安装，走系统环境变量

TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")


def execute_code(code: str, timeout: int = 30) -> dict:
    """在隔离环境中执行 LLM 生成的 Python 代码

    代码中可定义 _result 列表变量，其顺序应与查询指标列表对应。
    执行结果通过 __RESULT_MARKER__ JSON 行返回。

    Args:
        code: LLM 生成的 Python 代码
        timeout: 超时秒数

    Returns:
        {"success": bool, "output": str, "result": list, "error": str}
        - output: print() 捕获的文本
        - result: _result 列表（若定义了的话）
    """
    env = os.environ.copy()
    if TUSHARE_TOKEN:
        env["TUSHARE_TOKEN"] = TUSHARE_TOKEN

    # 包装代码：捕获 stdout + _result 变量
    wrapped = (
        "import sys, io, json\n"
        "_out = io.StringIO()\n"
        "_old = sys.stdout\n"
        "sys.stdout = _out\n"
        "_result = []\n"
        "try:\n"
    )
    # 缩进 LLM 代码（放入 try 块）
    for line in code.split("\n"):
        wrapped += f"    {line}\n"
    wrapped += (
        "except Exception:\n"
        "    import traceback\n"
        "    traceback.print_exc()\n"
        "finally:\n"
        "    sys.stdout = _old\n"
        "    _captured_stdout = _out.getvalue()\n"
        "    print('__RESULT_MARKER__' + json.dumps({\n"
        "        'stdout': _captured_stdout,\n"
        "        '_result': _result,\n"
        "    }))\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(wrapped)
        fpath = f.name

    try:
        result = subprocess.run(
            [sys.executable, fpath],
            capture_output=True, text=True,
            timeout=timeout, env=env,
        )
        if result.returncode != 0 and not result.stdout:
            return {"success": False, "output": "", "result": [], "error": result.stderr.strip()}

        # 解析 __RESULT_MARKER__ JSON
        stdout = result.stdout
        marker = "__RESULT_MARKER__"
        if marker in stdout:
            parts = stdout.split(marker, 1)
            before = parts[0].strip()  # 之前的 print 输出
            try:
                meta = json.loads(parts[1])
                captured_stdout = meta.get("stdout", "")
                captured_result = meta.get("_result", [])
                # 合并 before 和 captured_stdout
                all_stdout = (before + "\n" + captured_stdout).strip()
                return {
                    "success": True,
                    "output": all_stdout,
                    "result": captured_result,
                    "error": "",
                }
            except json.JSONDecodeError:
                return {"success": True, "output": stdout.strip(), "result": [], "error": ""}
        else:
            return {"success": True, "output": stdout.strip(), "result": [], "error": ""}

    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "result": [], "error": f"执行超时 ({timeout}s)"}
    except Exception as e:
        return {"success": False, "output": "", "result": [], "error": str(e)}
    finally:
        os.unlink(fpath)


def test_tushare():
    """测试 tushare 接口是否可用"""
    try:
        import tushare as ts
        if not TUSHARE_TOKEN:
            return {"success": False, "error": "TUSHARE_TOKEN 未设置"}
        ts.set_token(TUSHARE_TOKEN)
        pro = ts.pro_api()
        df = pro.trade_cal(start_date="20260701", end_date="20260710")
        return {"success": True, "output": f"tushare OK, 行数: {len(df)}"}
    except Exception as e:
        return {"success": False, "error": f"tushare 初始化失败: {e}"}


def test_levistock():
    try:
        import levistock as lk
        emotion = lk.market_emotion_cls()
        return {"success": True, "output": f"levistock OK, 热度: {emotion.get('market_degree', '?')}"}
    except Exception as e:
        return {"success": False, "error": f"levistock 失败: {e}"}


def test_akshare():
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        return {"success": True, "output": f"akshare OK, {len(df)} 个板块"}
    except Exception as e:
        return {"success": False, "error": f"akshare 失败: {e}"}


if __name__ == "__main__":
    print("=== 接口可用性测试 ===")
    for name, fn in [("tushare", test_tushare), ("levistock", test_levistock), ("akshare", test_akshare)]:
        r = fn()
        status = "OK" if r["success"] else "FAIL"
        print(f"  {name}: {status} | {r.get('output', '') or r.get('error', '')}")
