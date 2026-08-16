#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公司分析报告 API（纯标准库，零第三方依赖）

用法:
    from company_report_api import generate_company_report
    result = generate_company_report("淮北矿业")
    print(result["md_path"])          # 报告已保存的 Markdown 路径
    print(result["session_deleted"])  # True = 临时会话已清理

命令行:
    python3 company_report_api.py 淮北矿业

机制:
    1. 每次调用生成唯一 session key，通过 Gateway 的 OpenAI 兼容端点
       (/v1/chat/completions) 让 mx-agent 执行公司深度分析
       （自动调用 company-analysis 技能 + 东方财富 MCP 数据工具）
    2. 报告落盘为 Markdown
    3. finally 中通过 Gateway WS RPC (sessions.delete) 立即删除临时会话
       —— 上下文零残留、token 零累积、磁盘不增长
"""
import json
import os
import re
import time
import uuid
import urllib.request
from datetime import datetime

from openclaw_rpc import delete_session

GATEWAY_BASE = "http://127.0.0.1:18789"
AGENT_MODEL = "openclaw/mx-agent"          # 路由到 mx-agent（带金融数据工具+分析技能）
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

# 关键: session key 必须带 agent:mx-agent: 前缀。
# Gateway 按 session key 归属解析加载哪个 agent 的 workspace/skills：
# 裸 key（如 report-xxx）会 fallback 到默认 agent(main)，
# 而 main 的 skills 是旧框架（investment-assistant-core 等），
# 不会加载 company-analysis / mx-mcp-quota-exhausted-handler。
# 2026-08-16 实测: 带前缀的 key 正确加载 mx-agent workspace 与 company-analysis 技能。
SESSION_AGENT_PREFIX = "agent:mx-agent:"

PROMPT_TEMPLATE = """请对【{stock}】进行上市公司深度分析。

要求：
1. 先读取并使用你的 company-analysis 技能框架（SKILL.md，v3.3），严格按其"固定报告骨架"输出，不得自行增减章节：
   ## 〇、一句话定位
   ## 〇、总体结论（2-4 段，每段=总结句+知识点 bullets）
   ## 一、公司今日盘面分析（六章：当前表现/资金动向/融资融券与筹码博弈/机构成本参考/涨跌归因/行情总结与策略思考）
   ## 二、公司基本面分析（五章：业务与发展/行业面/盈利模式/财务面含近3年趋势表/人力资源面含研发领军人物展示分析）
   ## 三、综合前瞻判断
   ## 附：数据缺口说明
   末尾附免责声明。
2. 输出铁律：每章先写"综合总结"散文段（含 1-2 句前瞻），再用加粗子项 bullets 展开；结论导向不堆数据（每子项 1-3 个关键数据，用语言描述）；禁止黑话压缩过程，展开"谁做了什么→结果→接下来怎样"；基础股市术语直接用不翻译；加粗=核心结论/关键数据、斜体=前瞻/外部引用/缺失、⚠️=风险、✅=积极信号。
3. 调用 mx-ds-mcp 系列东方财富数据工具，获取以下数据：
   - 盘面：近10个交易日行情、技术指标、主力资金流向、融资融券、股东户数与筹码
   - 基本面：最新财报（营收/净利/毛利率/现金流/资产负债率/ROE）、估值（PE/PB/股息率）、股本与股东结构
   - 事件：最近公告（分红/增减持/重大项目）、新闻研报（券商评级/目标价/盈利预测）
   - 行业：所属行业景气度、产品价格趋势（如煤炭/化工品价格）
4. 数据不足的项明确标注缺失（斜体），不做无依据推测；研发领军人物语料不足时按 skill 衔接协议处理。
5. 取数守卫（最高优先级，先读取 mx-mcp-quota-exhausted-handler 技能并严格遵守）：
   若任一 mx-ds-mcp 工具返回积分耗尽类错误（如“你的积分已用完~请前往
   https://ai.eastmoney.com/skills 购买套餐补充积分，即可继续使用”），
   立即停止所有后续查询，不重试、不编造数据、不切换数据源、不产出报告，
   按该技能规定的规范格式输出错误块（错误码 MX_QUOTA_EXHAUSTED）。"""


# 与 mx-mcp-quota-exhausted-handler 技能约定的错误码（2026-08-14 实测官方错误）
QUOTA_EXHAUSTED_CODE = "MX_QUOTA_EXHAUSTED"
# 一级命中关键词（官方积分耗尽错误特征，作兜底）。
# 注意：官方整句文案由 OFFICIAL_QUOTA_MSG 单独匹配；"补充积分/购买套餐"等
# 通用词可能出现在正常语境（如"可购买套餐获得更多服务"），不在此列。
_QUOTA_PATTERNS_L1 = [
    "积分已用完", "积分用尽", "积分不足",
    "ai.eastmoney.com/skills",
]
# 官方错误原文（完整整句，正常报告几乎不可能出现）
OFFICIAL_QUOTA_MSG = ("你的积分已用完~请前往 https://ai.eastmoney.com/skills "
                      "购买套餐补充积分，即可继续使用")
# 人类可读错误块的稳定结构（MX_MCP_QUOTA_EXHAUSTED_HANDLER.md 第 4.1 节）
ERR_BLOCK_TITLE = "数据服务不可用"
ERR_CODE_FIELD_RE = re.compile(r"错误码\s*[:：]\s*MX_QUOTA_EXHAUSTED")

# 否定语境过滤：agent 报告头部会写"配额守卫：未触发 MX_QUOTA_EXHAUSTED（仅遇普通限流）"，
# 错误码/关键词出现在否定语境时不判定为配额耗尽（2026-08-14 误判修复）
_NEGATION_RE = re.compile(
    r"(?:未|没|不|无|没有|非)\s*(?:触发|命中|检测|出现|存在)|"
    r"未触发|未命中|未检测到|无需|不属于|不是"
)


def _extract_mcp_error(text: str) -> dict | None:
    """从 agent 回复中解析积分耗尽错误（MX_QUOTA_EXHAUSTED）。

    检测按 MX_MCP_QUOTA_EXHAUSTED_HANDLER.md 第 4 节的标准错误块结构识别
    （不对外层报告全文做宽松子串匹配，避免正常报告被误判为配额耗尽）：
      1) 机器可读 JSON 错误块：error.code == "MX_QUOTA_EXHAUSTED"（规约 4.2）
      2) 人类可读错误块："错误码 : MX_QUOTA_EXHAUSTED" 字段行，或
         "数据服务不可用" 标题 + 错误码（规约 4.1）
      3) 官方完整文案整句
      4) 纯错误码 / 一级关键词兜底（均排除否定语境，如"未触发 MX_QUOTA_EXHAUSTED"）

    命中返回: {"code", "stage", "detail", "type", "tool", "request"}；否则 None。
    注意：限流类（操作过于频繁/429/rate limit）是可恢复错误，不属于本函数范围。
    注意：2026-08-14 曾因 agent 报告头部"配额守卫：未触发 MX_QUOTA_EXHAUSTED"
    元信息误判为配额耗尽（正常报告被丢弃），已按标准错误块结构重构检测并加
    否定语境过滤；原"二级组合"启发式（"积分/套餐"与"余额/不足"等词同时出现
    即判定）误判风险过高，已移除。
    """
    if not text:
        return None
    # 容忍 markdown 代码块包裹
    stripped = re.sub(r"```(?:json)?\s*|\s*```", "", text)

    # 1) 机器可读 JSON 错误块
    m = re.search(r"\{.*\}", stripped, re.S)
    if m:
        try:
            payload = json.loads(m.group(0))
            err = payload.get("error")
            if isinstance(err, dict) and err.get("code") == QUOTA_EXHAUSTED_CODE:
                return {
                    "code": QUOTA_EXHAUSTED_CODE,
                    "stage": "mid-run",
                    "detail": err.get("message", ""),
                    "type": err.get("type", "quota_exhausted"),
                    "tool": err.get("tool", ""),
                    "request": err.get("request", ""),
                }
        except json.JSONDecodeError:
            pass

    # 2) 人类可读错误块（规约 4.1）: "错误码 : MX_QUOTA_EXHAUSTED" 字段行
    if ERR_CODE_FIELD_RE.search(stripped):
        return {"code": QUOTA_EXHAUSTED_CODE, "stage": "mid-run",
                "detail": "agent 输出积分耗尽错误块（错误码字段行）"}
    #    或 "数据服务不可用" 标题 + 错误码（排除否定语境）
    if ERR_BLOCK_TITLE in stripped:
        for m in re.finditer(QUOTA_EXHAUSTED_CODE, stripped):
            pre = stripped[max(0, m.start() - 40):m.start()]
            if _NEGATION_RE.search(pre):
                continue
            return {"code": QUOTA_EXHAUSTED_CODE, "stage": "mid-run",
                    "detail": "agent 输出积分耗尽错误块（数据服务不可用标题）"}

    # 3) 官方完整文案（整句精确匹配）
    if OFFICIAL_QUOTA_MSG in stripped:
        return {"code": QUOTA_EXHAUSTED_CODE, "stage": "mid-run",
                "detail": "检测到官方积分耗尽完整文案"}

    # 4) 纯错误码兜底（排除"未触发"等否定语境）
    for m in re.finditer(QUOTA_EXHAUSTED_CODE, stripped):
        pre = stripped[max(0, m.start() - 40):m.start()]
        if _NEGATION_RE.search(pre):
            continue
        return {"code": QUOTA_EXHAUSTED_CODE, "stage": "mid-run",
                "detail": "agent 输出积分耗尽错误块（MX_QUOTA_EXHAUSTED）"}

    # 5) 官方文案启发式（一级关键词，排除否定语境）
    for kw in _QUOTA_PATTERNS_L1:
        for m in re.finditer(re.escape(kw), stripped):
            pre = stripped[max(0, m.start() - 40):m.start()]
            if _NEGATION_RE.search(pre):
                continue
            return {"code": QUOTA_EXHAUSTED_CODE, "stage": "mid-run",
                    "detail": f"检测到官方积分耗尽文案（{kw}）"}

    return None


# ---------- 内部工具 ----------

def _load_token() -> str:
    env = os.environ.get("OPENCLAW_GATEWAY_TOKEN")
    if env:
        return env
    cfg = os.path.expanduser("~/.openclaw/openclaw.json")
    with open(cfg, encoding="utf-8") as f:
        return json.load(f)["gateway"]["auth"]["token"]


def _chat_once(session_key: str, user_message: str, timeout: int = 600) -> str:
    """通过 OpenAI 兼容端点执行一次 agent 调用，返回最终回复文本。"""
    body = json.dumps({
        "model": AGENT_MODEL,
        "messages": [{"role": "user", "content": user_message}],
    }).encode()
    req = urllib.request.Request(
        f"{GATEWAY_BASE}/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {_load_token()}",
            "Content-Type": "application/json",
            "x-openclaw-session-key": session_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return data["choices"][0]["message"]["content"]


def _delete_session_safe(session_key: str) -> bool:
    """删除临时会话（幂等）。返回是否删除成功。"""
    # session_key 已带 agent: 前缀时直接用它；兜底再加一次前缀尝试（兼容旧格式）
    candidates = ([session_key] if session_key.startswith("agent:")
                  else [f"{SESSION_AGENT_PREFIX}{session_key}", session_key])
    last_err = None
    for key in candidates:
        try:
            result = delete_session(key)
            if result.get("deleted") or result.get("ok"):
                return True
            last_err = f"未删除: {result}"
        except Exception as e:
            last_err = str(e)
    print(f"[warn] 临时会话清理失败({session_key}): {last_err}")
    return False


def _safe_filename(name: str) -> str:
    return "".join(c for c in name if c not in '\\/:*?"<>|').strip() or "stock"


def save_report_md(stock_name: str, report: str, output_dir: str | None = None) -> str:
    """报告落盘为 Markdown，返回文件路径。

    命名规则（与 office/output 一致）: {YYYYMMDD}_{股票名}_公司分析报告.md
    同日重复生成直接覆盖同名文件（单 worker 串行写入，无并发竞争）。
    """
    out = output_dir or OUTPUT_DIR
    os.makedirs(out, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")
    path = os.path.join(out, f"{date}_{_safe_filename(stock_name)}_公司分析报告.md")
    header = (
        f"# {stock_name} 公司分析报告\n\n"
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"> 生成方式: OpenClaw mx-agent（东方财富数据）\n\n"
        f"---\n\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + report + "\n")
    return path


# ---------- 对外主函数 ----------

def generate_company_report(stock_name: str, save_md: bool = True,
                            timeout: int = 600) -> dict:
    """
    输入股票名称，生成公司深度分析报告。

    返回（成功）:
      {"ok": true, "stock", "report", "md_path", "session_key", "session_deleted"}
    返回（积分耗尽/取数失败，进入兜底）:
      {"ok": false, "stock", "report",
       "error": {"code": "MX_QUOTA_EXHAUSTED", "stage", "detail", "type", "tool", "request"},
       "session_key", "session_deleted"}
    """
    session_key = f"{SESSION_AGENT_PREFIX}report-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    result = {
        "ok": True,
        "stock": stock_name,
        "report": "",
        "md_path": None,
        "session_key": session_key,
        "session_deleted": False,
    }
    try:
        prompt = PROMPT_TEMPLATE.format(stock=stock_name)
        text = _chat_once(session_key, prompt, timeout=timeout)

        # 检查积分耗尽错误块：命中 → 直接进入兜底，不落盘
        err = _extract_mcp_error(text)
        if err:
            result["ok"] = False
            result["error"] = err
            result["report"] = text
            return result

        result["report"] = text
        if save_md:
            result["md_path"] = save_report_md(stock_name, text)
        return result
    finally:
        # 关键：无论成功失败，用完即删临时会话
        result["session_deleted"] = _delete_session_safe(session_key)


if __name__ == "__main__":
    import sys
    stock = sys.argv[1] if len(sys.argv) > 1 else "淮北矿业"
    print(f"正在生成 {stock} 的分析报告（首次约需数分钟）...")
    r = generate_company_report(stock)
    if r.get("ok"):
        print("报告已生成:", r["md_path"])
    else:
        print("取数失败，进入兜底:", r.get("error"))
    print("临时会话已清理:", r["session_deleted"])
