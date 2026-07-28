"""
Agent Loop — DeepSeek 报告生成核心

接收 ReportContext → 组装 prompt → 进入 agent loop（最多 8 轮）
  → LLM 返回 tool call → 解析 article_ids → 调 middleman Type B → 返回正文
  → LLM 返回 final answer → 保存为 md 文档

遵循 exp02 的 agent loop 模式（OpenAI SDK + tool definition + prompt assembler）。
"""
import os
import sys
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from openai import OpenAI

# ── sys.path ──
_OFFICE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _OFFICE_DIR not in sys.path:
    sys.path.insert(0, _OFFICE_DIR)

from models import ReportContext
from cfg import load_config
from database import log_office_error
from middleman.server import TypeBResponse

# ── 配置 ──
_cfg = load_config()
_reporter_cfg = _cfg.get("reporter", {})
_middleman_cfg = _cfg.get("middleman", {})
_ds_cfg = _reporter_cfg.get("deepseek", {})

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY 环境变量未设置")

DEFAULT_MODEL = _ds_cfg.get("model", "deepseek-v4-flash")
DEFAULT_MAX_TOKENS = _ds_cfg.get("max_tokens", 4000)
API_BASE_URL = _ds_cfg.get("api_base", "https://api.deepseek.com")
MAX_ROUNDS = _reporter_cfg.get("max_loop_rounds", 8)
ARTICLE_TIMEOUT = _reporter_cfg.get("article_timeout", 120)
MIDDLEMAN_URL = (
    f"http://{_middleman_cfg.get('host', 'localhost')}"
    f":{_middleman_cfg.get('port', 8311)}"
)

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

# ── 工具定义 ──
_GET_ARTICLE_BODY_TOOL = {
    "type": "function",
    "function": {
        "name": "get_article_body",
        "description": "获取指定文章的完整正文。只有 body_avail='有' 的文章可以调用。详细规则见技能说明。",
        "parameters": {
            "type": "object",
            "properties": {
                "article_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "需要获取正文的文章 ID 列表，如 ['a_01', 'a_02']。只应包含 body_avail='有' 的文章。",
                }
            },
            "required": ["article_ids"],
        },
    },
}

_OUTPUT_DIR = os.path.normpath(
    os.path.join(_OFFICE_DIR, "output")
)


# ======================================================================
# Prompt 组装
# ======================================================================

def _read_prompt(name: str) -> str:
    """读取 prompt 文件"""
    path = os.path.join(_PROMPTS_DIR, name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def _load_skill(name: str) -> str:
    """加载技能说明"""
    path = os.path.join(_PROMPTS_DIR, "skills", name, "SKILL.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def _build_system_prompt(stock_name: str, ts_code: str) -> str:
    """组装 system prompt"""
    parts = [
        _read_prompt("soul.md"),
        _read_prompt("agent.md"),
        _read_prompt("preference.md"),
        "",
        "## 工具技能说明",
        _load_skill("fetch_article_body"),
    ]
    return "\n\n".join(p for p in parts if p)


def _build_user_context(ctx: ReportContext) -> str:
    """将 context 组装为用户消息"""
    lines = [
        f"请生成 {ctx.stock_name}（{ctx.ts_code}）的午间分析报告。",
        "",
        "数据源包含以下部分：",
        "",
    ]

    if ctx.fetch_data:
        lines.append("### 盘中数据")
        lines.append(ctx.fetch_data)
        lines.append("")

    if ctx.fetch_message:
        lines.append("### 盘中消息")
        lines.append(ctx.fetch_message)
        lines.append("")

    # 展示可用的新闻文章（带 body_avail 标签）
    if ctx.articles:
        lines.append("### 相关新闻资讯列表")
        lines.append("")
        for engine, result in ctx.articles.items():
            preview = result.get("preview")
            if not preview:
                continue
            articles = preview.get("articles", [])
            if not articles:
                continue
            error = result.get("error", "")
            lines.append(f"**来源: {engine}**" + (f"（{error}）" if error else ""))
            for art in articles:
                title = art.get("title", "")
                art_id = art.get("id", "")
                body_avail = art.get("body_avail", "无")
                snippet = art.get("snippet", "")[:200]
                date = art.get("date", "")
                category = art.get("_category", "")
                ba_tag = "【有正文】" if body_avail == "有" else "【无正文】"
                lines.append(f"  - ID: {art_id} {ba_tag} {title}")
                if date:
                    lines.append(f"    时间: {date}")
                if category:
                    lines.append(f"    分类: {category}")
                if snippet:
                    lines.append(f"    摘要: {snippet}")
                lines.append("")

    if ctx.middleman_warnings:
        lines.append("### 注意事项")
        for w in ctx.middleman_warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("请开始你的分析。如果需要查看文章正文，使用 get_article_body 工具。")
    return "\n".join(lines)


# ======================================================================
# Tool Call 处理
# ======================================================================

def _fetch_article_bodies(article_ids: list[str],
                           articles_meta: dict) -> tuple[dict, list[str]]:
    """获取文章正文

    1. 按 engine 分组（从 articles_meta 查询每个 article_id 所属 engine）
    2. 验证 body_avail
    3. 并发调 middleman Type B
    4. 120s 超时

    Args:
        article_ids: LLM 请求的 article_ids
        articles_meta: {engine: {session_id, preview, ...}}

    Returns:
        (results, warnings)
        results: {engine: [article_data, ...]} 或 {engine: {}}
        warnings: 异常信息列表
    """
    # ── 建立 article_id → (engine, session_id, body_avail) 映射 ──
    id_map = {}  # article_id -> {engine, session_id, body_avail}
    for engine, result in articles_meta.items():
        preview = result.get("preview", {})
        articles = preview.get("articles", [])
        session_id = result.get("session_id", "")
        for art in articles:
            aid = art.get("id", "")
            if aid in article_ids:
                id_map[aid] = {
                    "engine": engine,
                    "session_id": session_id,
                    "body_avail": art.get("body_avail", "无"),
                }

    # ── 过滤无效的 article_id ──
    valid_ids = {aid for aid in article_ids
                 if aid in id_map and id_map[aid]["body_avail"] == "有"}
    invalid_count = len(article_ids) - len(valid_ids)
    warnings = []
    if invalid_count:
        warnings.append(f"{invalid_count} 篇文章无正文，已跳过")

    # ── 按 engine 分组 ──
    engine_groups = {}
    for aid in valid_ids:
        info = id_map[aid]
        key = info["engine"]
        if key not in engine_groups:
            engine_groups[key] = {
                "session_id": info["session_id"],
                "article_ids": [],
            }
        engine_groups[key]["article_ids"].append(aid)

    if not engine_groups:
        return {}, warnings + ["没有可获取正文的文章"]

    # ── 并发调 Type B ──
    results = {}
    with ThreadPoolExecutor(max_workers=len(engine_groups)) as pool:
        def _fetch(engine, eg):
            try:
                resp = requests.post(
                    f"{MIDDLEMAN_URL}/api/v1/article",
                    json={
                        "report_id": "",
                        "engine": engine,
                        "session_id": eg["session_id"],
                        "article_ids": eg["article_ids"],
                    },
                    timeout=ARTICLE_TIMEOUT + 10,
                )
                if resp.ok:
                    return engine, resp.json()
                return engine, {"status": "error", "articles": []}
            except Exception as e:
                return engine, {"status": "error", "articles": []}

        fut_map = {
            pool.submit(_fetch, engine, eg): engine
            for engine, eg in engine_groups.items()
        }
        for fut in as_completed(fut_map, timeout=ARTICLE_TIMEOUT + 20):
            try:
                engine, data = fut.result()
                results[engine] = data
            except Exception:
                engine = fut_map[fut]
                results[engine] = {"status": "timeout", "articles": []}
                warnings.append(f"{engine} 正文获取超时")

    return results, warnings


# ======================================================================
# 输出
# ======================================================================

def _save_report(stock_name: str, ts_code: str, content: str) -> str:
    """保存报告到 output 目录

    Args:
        stock_name: 股票名称
        content: 报告的 markdown 内容

    Returns:
        输出文件路径
    """
    today = datetime.now().strftime("%Y%m%d")
    stock_dir = os.path.join(_OUTPUT_DIR, stock_name)
    os.makedirs(stock_dir, exist_ok=True)

    filename = f"{today}_{stock_name}_midday.md"
    filepath = os.path.join(stock_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


# ======================================================================
# Agent Loop
# ======================================================================

def run(ctx: ReportContext) -> tuple[str, int]:
    """运行 agent loop，生成报告

    Args:
        ctx: ReportContext（由 sub writer 组装）

    Returns:
        (output_path, rounds_used)
    """
    client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

    # ── 组装 prompt ──
    system_prompt = _build_system_prompt(ctx.stock_name, ctx.ts_code)
    user_context = _build_user_context(ctx)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_context},
    ]

    # ── Agent Loop ──
    for round_num in range(1, MAX_ROUNDS + 1):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=[_GET_ARTICLE_BODY_TOOL],
                tool_choice="auto",
                max_tokens=DEFAULT_MAX_TOKENS,
                timeout=_ds_cfg.get("timeout", 130),
            )
        except Exception as e:
            log_office_error(
                module="office.reporter",
                function="agent.run",
                level="ERROR",
                stock_name=ctx.stock_name, ts_code=ctx.ts_code,
                error_msg=f"LLM API 调用异常: {e}",
                error_code="REPORTER_LLM_ERROR",
            )
            # 如果已有部分内容，返回
            partial = _extract_partial(messages)
            if partial:
                path = _save_report(ctx.stock_name, ctx.ts_code, partial)
                return path, round_num - 1
            raise

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message

        if finish == "stop":
            # 完成
            content = msg.content or ""
            path = _save_report(ctx.stock_name, ctx.ts_code, content)
            return path, round_num

        if finish == "tool_calls" and msg.tool_calls:
            # ── 处理 tool call ──
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                if tc.function.name == "get_article_body":
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        continue

                    article_ids = args.get("article_ids", [])
                    if not article_ids:
                        continue

                    # 验证 body_avail + 调 middleman
                    body_results, body_warnings = _fetch_article_bodies(
                        article_ids, ctx.articles
                    )

                    # 组装 tool result
                    tool_result_parts = []
                    for engine, data in body_results.items():
                        status = data.get("status", "error")
                        articles = data.get("articles", [])
                        if status == "ready" and articles:
                            tool_result_parts.append(
                                f"### {engine} 正文\n"
                            )
                            for art in articles:
                                art_id = art.get("article_id", "")
                                body = art.get("body_text", "")
                                truncated = art.get("truncated", False)
                                tool_result_parts.append(f"**文章 {art_id}**")
                                tool_result_parts.append(body)
                                if truncated:
                                    tool_result_parts.append(
                                        "*（正文过长已截断）*"
                                    )
                                tool_result_parts.append("")
                        elif status == "timeout":
                            tool_result_parts.append(
                                f"### {engine}\n正文获取超时，请根据标题和摘要自行判断。\n"
                            )

                    if not tool_result_parts:
                        tool_result_parts.append(
                            "所有请求的文章正文均无法获取，请根据已有的标题和摘要进行分析。"
                        )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "\n".join(tool_result_parts),
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "未知工具调用",
                    })
            continue

        # finish="length"或其他 → 继续或退出
        if finish == "length":
            # token 超限，可能仍有部分内容
            if msg.content:
                path = _save_report(ctx.stock_name, ctx.ts_code, msg.content)
                return path, round_num
            break

    # 达到最大轮次，取已有内容
    partial = _extract_partial(messages)
    if partial:
        path = _save_report(ctx.stock_name, ctx.ts_code, partial)
        return path, MAX_ROUNDS

    log_office_error(
        module="office.reporter",
        function="agent.run",
        level="WARNING",
        stock_name=ctx.stock_name, ts_code=ctx.ts_code,
        error_msg=f"达到最大轮次 {MAX_ROUNDS}，未生成最终报告",
        error_code="REPORTER_LOOP_TIMEOUT",
    )
    return "", MAX_ROUNDS


def _extract_partial(messages: list) -> str:
    """从 messages 中提取 LLM 最后一次回复的内容"""
    for msg in reversed(messages):
        if msg["role"] == "assistant" and msg.get("content"):
            content = msg["content"]
            # 至少要有一定长度的实质内容
            if len(content) > 100:
                return content + "\n\n*（注：报告未完全生成，以上为部分内容）*"
    return ""
