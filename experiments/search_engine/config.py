"""search_engine 配置"""
import subprocess, os

# 搜索工具使用的代理（仅搜索需要代理）
# 默认端口，Windows 端 Clash/SSR/v2rayN 等一般在此端口监听
_PROXY_PORT = "7890"

def _detect_gateway() -> str:
    """自动检测 WSL2 默认网关 IP（代理服务器地址）"""
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True, timeout=3
        )
        parts = result.stdout.strip().split()
        if len(parts) >= 3 and parts[0] == "default":
            return parts[2]  # 如 172.25.32.1
    except Exception:
        pass
    # 兜底
    return "172.25.32.1"

PROXY = os.environ.get("SEARCH_PROXY") or f"http://{_detect_gateway()}:{_PROXY_PORT}"

# sinafin_artical_tool 服务端点
SNAFIN_ENDPOINT = os.environ.get("SNAFIN_ENDPOINT") or "http://localhost:8000"
