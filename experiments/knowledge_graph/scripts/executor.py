"""执行层适配器：执行 LLM 生成的取数代码"""
import os, sys, json, subprocess, tempfile

TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")


def execute_code(code: str, timeout: int = 30) -> dict:
    """在隔离环境中执行 LLM 生成的 Python 代码

    Args:
        code: LLM 生成的 Python 代码
        timeout: 超时秒数

    Returns:
        {"success": bool, "output": str, "error": str}
    """
    # 注入 Token 环境变量
    env = os.environ.copy()
    if TUSHARE_TOKEN:
        env["TUSHARE_TOKEN"] = TUSHARE_TOKEN

    # 写入临时文件执行
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        # 包装代码：捕获 print 输出
        wrapped = (
            "import sys, io\n"
            "_out = io.StringIO()\n"
            "_old = sys.stdout\n"
            "sys.stdout = _out\n"
            "try:\n"
        )
        for line in code.split("\n"):
            wrapped += f"    {line}\n"
        wrapped += (
            "finally:\n"
            "    sys.stdout = _old\n"
            "    _result = _out.getvalue()\n"
            "    print(_result, end='')\n"
        )
        f.write(wrapped)
        fpath = f.name

    try:
        result = subprocess.run(
            [sys.executable, fpath],
            capture_output=True, text=True,
            timeout=timeout, env=env,
        )
        if result.returncode == 0:
            return {"success": True, "output": result.stdout.strip()}
        else:
            return {"success": False, "output": result.stdout.strip(),
                    "error": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": f"执行超时 ({timeout}s)"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}
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
    """测试 levistock 接口是否可用"""
    try:
        import levistock as lk
        emotion = lk.market_emotion_cls()
        return {"success": True, "output": f"levistock OK, 热度: {emotion.get('market_degree', '?')}"}
    except Exception as e:
        return {"success": False, "error": f"levistock 失败: {e}"}


def test_akshare():
    """测试 akshare 接口是否可用"""
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
