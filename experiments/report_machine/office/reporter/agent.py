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

# ── 调试日志 ──
from dlog.debug_logger import get_logger

# ── 共享 HTTP 连接池（大连接池防耗尽） ──
_HTTP_SESSION = requests.Session()
_HTTP_ADAPTER = requests.adapters.HTTPAdapter(
    pool_connections=200, pool_maxsize=200, max_retries=0
)
_HTTP_SESSION.mount("http://", _HTTP_ADAPTER)
_HTTP_SESSION.mount("https://", _HTTP_ADAPTER)

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

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), _reporter_cfg.get("prompts_dir", "prompts"))

_ARTICLE_TOOL_NAME = _reporter_cfg.get("article_tool_name", "get_article_body")

# ── 工具定义 ──
_GET_ARTICLE_BODY_TOOL = {
    "type": "function",
    "function": {
        "name": _ARTICLE_TOOL_NAME,
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

# ── 端到端测试保存钩子(生产环境不生效) ──
# 设置环境变量 E2E_SAVE_DIR 后, 每轮调用 LLM 前保存完整 messages(context)到该目录
_E2E_SAVE_DIR = os.environ.get("E2E_SAVE_DIR", "").strip()
if _E2E_SAVE_DIR:
    os.makedirs(_E2E_SAVE_DIR, exist_ok=True)


def _e2e_save_context(stock_name: str, round_num: int, messages: list) -> None:
    """端到端测试: 保存调用 LLM 前的完整 context(每轮一份)"""
    if not _E2E_SAVE_DIR:
        return
    try:
        safe = "".join(c for c in stock_name if c.isalnum() or c in "._-")
        path = os.path.join(_E2E_SAVE_DIR, f"{safe}_round{round_num:02d}.json")
        payload = {
            "stock_name": stock_name,
            "round": round_num,
            "messages": messages,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _has_fetchable_articles(articles: dict) -> bool:
    """检查是否有 body_avail='有' 的文章"""
    for engine, result in articles.items():
        if not result:
            continue
        preview = result.get("preview")
        if not preview:
            continue
        for art in preview.get("articles", []):
            if art.get("body_avail") == "有":
                return True
    return False


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


# 报告类型 → skill 目录名 / 中文名
_SKILL_BY_TYPE = {
    "noon": "noon_report",
    "endday": "endday_report",
}
_REPORT_TYPE_NAME = {
    "noon": "午间",
    "endday": "日终",
}


def _load_skill(skill_name: str) -> list[str]:
    """按 report_type 只加载对应的一个 skill（避免多 skill 同时注入）"""
    if not skill_name:
        return []
    skill_path = os.path.join(_PROMPTS_DIR, "skills", skill_name, "SKILL.md")
    if not os.path.isfile(skill_path):
        return []
    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return [f"### {skill_name}\n\n{content}"] if content else []


def _build_system_prompt(stock_name: str, ts_code: str, report_type: str = "noon") -> str:
    """组装 system prompt（只加载 report_type 对应的 skill）"""
    skill_parts = _load_skill(_SKILL_BY_TYPE.get(report_type, "noon_report"))
    parts = [
        _read_prompt("soul.md"),
        _read_prompt("agent.md"),
        _read_prompt("preference.md"),
    ]
    if skill_parts:
        parts.append("")
        parts.append("## 工具技能说明")
        parts.extend(skill_parts)
    return "\n\n".join(p for p in parts if p)


def _build_user_context(ctx: ReportContext) -> str:
    """将 context 组装为用户消息"""
    report_name = _REPORT_TYPE_NAME.get(ctx.report_type, "午间")
    lines = [
        f"请生成 {ctx.stock_name}（{ctx.ts_code}）的{report_name}分析报告。",
        "",
        "数据源包含以下部分：",
        "",
    ]

    if ctx.fetch_data:
        lines.append(f"### {ctx.stock_name}（{ctx.ts_code}）盘中数据")
        lines.append(ctx.fetch_data)
        lines.append("")

    if ctx.fetch_message:
        lines.append(f"### {ctx.stock_name}（{ctx.ts_code}）盘中消息")
        lines.append(ctx.fetch_message)
        lines.append("")

    # 展示可用的新闻文章（带 body_avail 标签）
    if ctx.articles:
        lines.append(f"### {ctx.stock_name}（{ctx.ts_code}）相关新闻资讯列表")
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
                lines.append(f"  - ID: {art_id}")
                lines.append(f"    body_avail: {body_avail}")
                lines.append(f"    title: {title}")
                if date:
                    lines.append(f"    时间: {date}")
                if category:
                    lines.append(f"    分类: {category}")
                if snippet and engine != "sinafin":
                    lines.append(f"    摘要: {snippet}")
                lines.append("")

    if ctx.middleman_warnings:
        lines.append("### 注意事项")
        for w in ctx.middleman_warnings:
            lines.append(f"- {w}")
        lines.append("")

    if ctx.query:
        lines.append(f"需求：{ctx.query}")
        lines.append("")

    if _has_fetchable_articles(ctx.articles):
        lines.append(f"请开始你的分析。如果需要查看文章正文，使用 {_ARTICLE_TOOL_NAME} 工具。")
    else:
        lines.append("请开始你的分析。")
    lines.append("")
    lines.append("【关键提醒】输出最终报告时，直接以 Markdown 标题开头，不要有任何前缀、思考过程或过渡语句。")
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
        preview = result.get("preview")
        if not preview:
            continue
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
    _dl = get_logger("reporter_type_b")
    results = {}
    with ThreadPoolExecutor(max_workers=len(engine_groups)) as pool:
        def _fetch(engine, eg):
            t0 = time.time()
            try:
                resp = _HTTP_SESSION.post(
                    f"{MIDDLEMAN_URL}/api/v1/article",
                    json={
                        "report_id": "",
                        "engine": engine,
                        "session_id": eg["session_id"],
                        "article_ids": eg["article_ids"],
                    },
                    timeout=ARTICLE_TIMEOUT + 10,
                )
                el = time.time() - t0
                if resp.ok:
                    data = resp.json()
                    _dl("type_b_result", engine=engine,
                        requested=len(eg["article_ids"]),
                        returned=len(data.get("articles", [])),
                        status=data.get("status"),
                        _elapsed=el)
                    return engine, data
                _dl("type_b_result", engine=engine,
                    requested=len(eg["article_ids"]),
                    http=resp.status_code, _elapsed=el)
                return engine, {"status": "error", "articles": []}
            except Exception as e:
                _dl("type_b_result", engine=engine,
                    requested=len(eg["article_ids"]),
                    error=str(e)[:60], _elapsed=time.time()-t0)
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

def _save_report(stock_name: str, ts_code: str, content: str, report_type: str = "noon") -> str:
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

    # 清理：截掉第一个 # 标题之前的所有内容（LLM 可能输出的思考过程）
    first_heading = content.find("\n# ")
    if first_heading == -1:
        first_heading = content.find("# ")
    else:
        heading_at_start = content[:2] == "# "
        if not heading_at_start:
            first_heading = content.find("# ")
    if first_heading > 0:
        # 有内容在第一个标题之前 → 从第一个标题处截断
        # 找到真正的行首
        nl_before = content.rfind("\n", 0, first_heading)
        if nl_before >= 0:
            content = content[nl_before + 1:]
        else:
            content = content[first_heading:]

    # 保存 .md 版本（文件名按报告类型）
    report_name = _REPORT_TYPE_NAME.get(report_type, "午间")
    filename = f"{today}_{stock_name}_{report_name}收盘报告"
    md_path = os.path.join(stock_dir, filename + ".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

    return md_path


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

    # ── 调试日志 ──
    _dl = get_logger("reporter_round")

    # ── 组装 prompt ──
    system_prompt = _build_system_prompt(ctx.stock_name, ctx.ts_code, ctx.report_type)
    user_context = _build_user_context(ctx)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_context},
    ]

    # ── 判断是否有可获取正文的文章 ──
    has_articles = _has_fetchable_articles(ctx.articles)
    tools = [_GET_ARTICLE_BODY_TOOL] if has_articles else []
    tool_choice = "auto" if has_articles else "none"

    _dl("agent_start", stock_name=ctx.stock_name, ts_code=ctx.ts_code,
        has_articles=has_articles, num_engines=len(ctx.articles),
        user_context_len=len(user_context))

    # ── Agent Loop ──
    for round_num in range(1, MAX_ROUNDS + 1):
        # 端到端测试: 调用 LLM 前保存完整 context(含 tool 正文追加后的每轮状态)
        _e2e_save_context(ctx.stock_name, round_num, messages)
        _dl("round_llm_call", stock_name=ctx.stock_name, round=round_num,
            messages_count=len(messages),
            last_role=messages[-1]["role"],
            last_content_len=len(str(messages[-1].get("content", ""))),
            tool_choice=tool_choice)
        try:
            t0 = time.time()
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=tools or None,
                tool_choice=tool_choice,
                max_tokens=DEFAULT_MAX_TOKENS,
                timeout=_ds_cfg.get("timeout", 130),
            )
            llm_elapsed = time.time() - t0
        except Exception as e:
            llm_elapsed = time.time() - t0
            _dl("round_llm_error", stock_name=ctx.stock_name, round=round_num,
                error=str(e)[:200], _elapsed=llm_elapsed)
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
                path = _save_report(ctx.stock_name, ctx.ts_code, partial, ctx.report_type)
                return path, round_num - 1
            raise

        choice = response.choices[0]
        finish = choice.finish_reason
        msg = choice.message

        _dl("round_llm_response", stock_name=ctx.stock_name, round=round_num,
            finish_reason=finish, content_len=len(msg.content or ""),
            content_preview=(msg.content or "")[:150],
            tool_calls_count=len(msg.tool_calls) if msg.tool_calls else 0,
            _elapsed=llm_elapsed)

        if finish == "stop":
            # 完成
            content = msg.content or ""
            _dl("round_finish", stock_name=ctx.stock_name, round=round_num,
                output_len=len(content), output_preview=content[:200])
            path = _save_report(ctx.stock_name, ctx.ts_code, content, ctx.report_type)
            return path, round_num

        if finish == "tool_calls" and msg.tool_calls:
            # ── 记录 tool call 信息 ──
            tool_names = [tc.function.name for tc in msg.tool_calls]
            tool_args_list = []
            for tc in msg.tool_calls:
                try:
                    tool_args_list.append(json.loads(tc.function.arguments))
                except Exception:
                    tool_args_list.append({"parse_error": tc.function.arguments[:100]})
            _dl("round_tool_calls", stock_name=ctx.stock_name, round=round_num,
                tool_names=tool_names, tool_args=tool_args_list,
                assistant_content=(msg.content or "")[:200])

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
                if tc.function.name == _ARTICLE_TOOL_NAME:
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
                    _dl("round_tool_result", stock_name=ctx.stock_name,
                        round=round_num, article_ids=article_ids,
                        engines_with_data=[k for k, v in body_results.items()
                                          if v.get("status") == "ready" and v.get("articles")],
                        warnings=body_warnings,
                        result_len=len("\n".join(tool_result_parts)))
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "未知工具调用",
                    })
            continue

        # finish="length"或其他 → 继续或退出
        if finish == "length":
            _dl("round_length", stock_name=ctx.stock_name, round=round_num,
                content_len=len(msg.content or ""),
                content_preview=(msg.content or "")[:200])
            # token 超限，可能仍有部分内容
            if msg.content:
                path = _save_report(ctx.stock_name, ctx.ts_code, msg.content, ctx.report_type)
                return path, round_num
            break

    # 达到最大轮次，取已有内容
    # 取最后一次 assistant 消息的内容做日志
    _last_assistant = next((m for m in reversed(messages)
                           if m["role"] == "assistant" and m.get("content")), None)
    _dl("agent_max_rounds", stock_name=ctx.stock_name,
        rounds=MAX_ROUNDS, messages_count=len(messages),
        last_assistant_content=(_last_assistant and _last_assistant["content"][:200]) or "")
    partial = _extract_partial(messages)
    if partial:
        path = _save_report(ctx.stock_name, ctx.ts_code, partial, ctx.report_type)
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
