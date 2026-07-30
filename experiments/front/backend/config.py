"""
前端服务 — 配置
"""
import os
from pathlib import Path

# ── 路径 ──
BASE_DIR = Path(__file__).resolve().parent  # backend/
FRONT_DIR = BASE_DIR.parent                 # front/
DB_PATH = Path("/home/stockagent/project_space/database/report_market.db")

# Office 系统路径（用于 md_to_docx）
OFFICE_DIR = Path("/home/stockagent/project_space/research/experiments/report_machine/office")

# 用户文件空间（按用户名动态解析）
USER_SPACE_BASE = Path("/home/stockagent/project_space/research/experiments/report_machine/user")

# ── 服务 ──
HOST = "0.0.0.0"
PORT = 8320

# ── 会话密钥（生产环境需改为随机字符串） ──
SECRET_KEY = "front-secret-key-change-in-production"
TOKEN_EXPIRE_HOURS = 24
