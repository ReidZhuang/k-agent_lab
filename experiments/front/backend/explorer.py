"""
文件浏览与下载模块
"""
import os
import sys
import zipfile
import tempfile
from pathlib import Path

from config import USER_SPACE_BASE, OFFICE_DIR
from database import db

# md→docx 转换: 使用同目录 md2docx.py(源: demand/cases/md2docx.py)
from md2docx import convert_md_to_docx as md_to_docx_convert


def _user_base(username: str) -> Path:
    """获取用户个人空间根目录"""
    return USER_SPACE_BASE / username


def _resolve_path(rel_path: str, username: str) -> Path | None:
    """解析相对路径，防止路径穿越"""
    base = _user_base(username)
    target = (base / rel_path).resolve()
    if not str(target).startswith(str(base)):
        return None
    return target


def list_dir(rel_path: str = "", username: str = "", user_id: int = 0) -> list[dict]:
    """列出目录内容

    Args:
        rel_path: 相对用户空间的路径
        username: 用户名（用于确定目录）
        user_id: 用户 ID（用于判断收藏状态）

    Returns:
        [{name, path, type, is_favorite}]
    """
    base = _user_base(username)
    if rel_path:
        target = (base / rel_path).resolve()
        if not str(target).startswith(str(base)):
            return []
    else:
        target = base

    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)

    items = []
    for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
        rel = str(entry.relative_to(base))
        is_fav = False
        if user_id and entry.is_file():
            is_fav = db.is_favorite(user_id, str(entry))
        items.append({
            "name": entry.name,
            "path": rel,
            "type": "dir" if entry.is_dir() else "file",
            "is_favorite": is_fav,
            "mtime": entry.stat().st_mtime,
        })
    return items


def search_files(q: str, username: str) -> list[dict]:
    """按文件名(子串, 不区分大小写)递归搜索用户空间, 返回 [{name, path, type, mtime}]。

    目录名匹配同样返回(便于定位到报告目录如 宁德时代/), 全部限定在
    用户根目录内, 无路径穿越风险。
    """
    base = _user_base(username)
    q_lower = (q or "").strip().lower()
    if not q_lower or not base.exists():
        return []
    results = []
    for entry in sorted(base.rglob("*"), key=lambda e: e.name.lower()):
        if q_lower in entry.name.lower():
            results.append({
                "name": entry.name,
                "path": str(entry.relative_to(base)),
                "type": "dir" if entry.is_dir() else "file",
                "mtime": entry.stat().st_mtime,
            })
    return results


def delete_item(rel_path: str, username: str) -> bool:
    """删除文件或空目录"""
    full_path = _resolve_path(rel_path, username)
    if not full_path or not full_path.exists():
        return False
    if full_path.is_file():
        full_path.unlink()
        return True
    if full_path.is_dir():
        if any(full_path.iterdir()):
            return False  # 非空目录不删
        full_path.rmdir()
        return True
    return False


def get_file_content(rel_path: str, username: str) -> str | None:
    """读取文件内容（仅支持 .md 文件）"""
    full_path = _resolve_path(rel_path, username)
    if not full_path or not full_path.exists():
        return None
    if full_path.suffix not in (".md", ".txt"):
        return None
    return full_path.read_text("utf-8")


def convert_single_to_docx(rel_path: str, username: str,
                           output_dir: str | Path | None = None) -> str | None:
    """将单个 md 文件转为 docx，返回输出路径"""
    full_path = _resolve_path(rel_path, username)
    if not full_path or not full_path.exists() or full_path.suffix != ".md":
        return None

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="docx_"))
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{full_path.stem}.docx"
    md_to_docx_convert(str(full_path), str(output_path))
    return str(output_path) if output_path.exists() else None


def convert_batch_to_docx(rel_paths: list[str], username: str) -> str | None:
    """批量转换 md 为 docx，打包为 zip，返回 zip 路径"""
    tmp_dir = Path(tempfile.mkdtemp(prefix="docx_batch_"))
    zip_path = tmp_dir / "documents.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in rel_paths:
            full_path = _resolve_path(rel, username)
            if not full_path or not full_path.exists() or full_path.suffix != ".md":
                continue
            docx_name = f"{full_path.stem}.docx"
            docx_tmp = tmp_dir / docx_name
            try:
                md_to_docx_convert(str(full_path), str(docx_tmp))
                if docx_tmp.exists():
                    zf.write(docx_tmp, docx_name)
            except Exception as e:
                print(f"  ⚠️  转换失败 {rel}: {e}")

    return str(zip_path) if zip_path.exists() else None
