"""
前端配置加载器
"""
import os
import yaml
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent
_CACHE = {}


def load_config(name: str) -> dict:
    """加载 YAML 配置文件（带缓存）"""
    if name in _CACHE:
        return _CACHE[name]

    path = _CONFIG_DIR / name
    if not path.suffix:
        path = path.with_suffix(".yaml")

    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        _CACHE[name] = yaml.safe_load(f)
    return _CACHE[name]


def get_report_users() -> list[str]:
    """获取需要生成报告的用户列表"""
    cfg = load_config("report_users.yaml")
    return cfg.get("report_users", [])
