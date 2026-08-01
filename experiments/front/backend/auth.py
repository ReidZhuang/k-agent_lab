"""
登录认证模块
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from database import db


def hash_password(password: str) -> str:
    """SHA256 哈希（生产环境应改用 bcrypt）"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


# 简易内存 Token 存储（生产环境应改用 JWT）
_tokens: dict[str, dict] = {}


def create_token(user_id: int, username: str) -> str:
    token = secrets.token_hex(24)
    _tokens[token] = {
        "user_id": user_id,
        "username": username,
        "expires": datetime.now() + timedelta(hours=24),
    }
    # 清理过期 token
    expired = [k for k, v in _tokens.items() if v["expires"] < datetime.now()]
    for k in expired:
        _tokens.pop(k, None)
    return token


def validate_token(token: str) -> dict | None:
    info = _tokens.get(token)
    if not info:
        return None
    if info["expires"] < datetime.now():
        _tokens.pop(token, None)
        return None
    return {"user_id": info["user_id"], "username": info["username"]}


def init_default_users():
    """初始化默认用户（admin / admin123）"""
    from config import BASE_DIR
    # 检查是否有用户，没有则创建默认用户
    users = db.execute("SELECT COUNT(*) as c FROM user")
    if users and users[0]["c"] == 0:
        db.create_user("admin", hash_password("admin123"))
        print("  ✅ 默认用户已创建: admin / admin123")
