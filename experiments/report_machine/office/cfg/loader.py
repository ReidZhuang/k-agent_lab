"""
Office 配置加载器

从 config.yaml 加载全局配置，模块级惰性缓存。
遵循 mail_tower 的 config.json 加载模式。
"""
import os
import yaml

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
_CONFIG_CACHE = None


def load_config(path: str | None = None) -> dict:
    """加载配置（带缓存）"""
    global _CONFIG_CACHE, _CONFIG_PATH
    if path:
        _CONFIG_PATH = path
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    if not os.path.exists(_CONFIG_PATH):
        raise FileNotFoundError(f"配置文件不存在: {_CONFIG_PATH}")
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        _CONFIG_CACHE = yaml.safe_load(f)
    return _CONFIG_CACHE


def get_config() -> dict:
    """获取缓存的配置"""
    if _CONFIG_CACHE is None:
        return load_config()
    return _CONFIG_CACHE
