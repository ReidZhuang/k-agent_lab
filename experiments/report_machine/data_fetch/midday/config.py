"""
数据取数配置中心

封装所有 API Token / 密钥的读取逻辑，提供统一的配置接口。

当前管理的 Token:
  - pysnowball (雪球): config/snowball_token.json
  - Tushare: 环境变量 TUSHARE_TOKEN 或 ~/tk.csv（由 tushare 库自行管理）

所有 config/*.json 不应提交到版本控制（已在 .gitignore 中排除）。
"""

import os
import json
from pathlib import Path

CONFIG_DIR = Path(__file__).parent / "config"

# ===== pysnowball / 雪球 Token =====

_SNOWBALL_TOKEN_CACHE = None


def get_snowball_token() -> str | None:
    """获取雪球 API Token（带惰性缓存）

    格式: "xq_a_token=xxx; u=yyy"
    来源: config/snowball_token.json
    过期: Token 有效期 7-30 天，过期后需手动更新 config/snowball_token.json
    """
    global _SNOWBALL_TOKEN_CACHE
    if _SNOWBALL_TOKEN_CACHE is not None:
        return _SNOWBALL_TOKEN_CACHE

    token_path = CONFIG_DIR / "snowball_token.json"
    if not token_path.exists():
        print("[config] ❌ 未找到 snowball_token.json", file=__import__("sys").stderr)
        _SNOWBALL_TOKEN_CACHE = ""
        return None

    try:
        with open(token_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        xq = data.get("xq_a_token", "")
        u = data.get("u", "")
        if xq and u:
            _SNOWBALL_TOKEN_CACHE = f"xq_a_token={xq}; u={u}"
            return _SNOWBALL_TOKEN_CACHE
        else:
            print("[config] ⚠️  snowball_token.json 中缺少 xq_a_token 或 u", file=__import__("sys").stderr)
            _SNOWBALL_TOKEN_CACHE = ""
            return None
    except Exception as e:
        print(f"[config] ❌ 读取 snowball_token.json 失败: {e}", file=__import__("sys").stderr)
        _SNOWBALL_TOKEN_CACHE = ""
        return None


# ===== Tushare Token =====

def get_tushare_token() -> str | None:
    """Tushare Token（由 tushare 库自行管理，此处仅作说明）

    优先级:
      1. 环境变量 TUSHARE_TOKEN
      2. 环境变量 TS_TOKEN
      3. ~/tk.csv（由 tushare 库自动读取）

    Returns:
        str or None（仅用于诊断）
    """
    token = os.environ.get("TUSHARE_TOKEN") or os.environ.get("TS_TOKEN")
    if token:
        return token

    # 检查 tk.csv
    tk_path = os.path.expanduser("~/tk.csv")
    if os.path.exists(tk_path):
        import pandas as pd
        try:
            df = pd.read_csv(tk_path)
            return str(df.loc[0]["token"])
        except Exception:
            pass

    return None


# ===== 诊断 =====

def check_all_tokens() -> dict:
    """检查所有 Token 状态"""
    snowball = get_snowball_token()
    tushare = get_tushare_token()

    result = {
        "snowball": {
            "configured": snowball is not None and snowball != "",
            "source": str(CONFIG_DIR / "snowball_token.json"),
            "preview": (snowball[:30] + "...") if snowball else None,
        },
        "tushare": {
            "configured": tushare is not None,
            "source": "env TUSHARE_TOKEN/TS_TOKEN or ~/tk.csv",
            "preview": (tushare[:15] + "...") if tushare else None,
        },
    }
    return result


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        status = check_all_tokens()
        for name, info in status.items():
            icon = "✅" if info["configured"] else "❌"
            print(f"{icon} {name}: {info['source']}")
            if info["preview"]:
                print(f"   token: {info['preview']}")
