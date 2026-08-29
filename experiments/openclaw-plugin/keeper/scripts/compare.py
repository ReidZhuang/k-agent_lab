#!/usr/bin/env python3
# ==============================================================================
# keeper U11 —— 效果对比脚本（对照组 vs 插件组）
# ==============================================================================
# 输入：两（或多）组运行产物。每组目录可以是：
#   - "run" 布局    ：gen_report.py 的运行目录（run.json / usage.json / report.md /
#                     result.json / error.txt），即"无插件对照组 / 无 trace 的插件组"。
#   - "trace" 布局  ：插件 U6 trace 目录（trace.jsonl / run_stats.json / trace_payloads/），
#                     记录每轮 token 与压缩。同一目录可并列 report.md。
# 自动识别布局，归一化成 RunSummary，再聚合指标：token（prompt/completion/total）、
# 压缩节省、质量分（骨架完整/草稿污染/引用准确/免责结尾）、性价比（质量÷total）、稳定性。
#
# 方案（见 DEVELOPMENT_PLAN.md §6）：
#   方案 A（同上下文重放）/ 方案 B（去皮重放）：本脚本做"前置数据校验 + 上下文重建"。
#     数据就绪 → 把每轮"压缩前/后 messages + 原始 tool 结果"重建为 replay 上下文并落盘；
#     数据缺失 → 给出缺什么、补哪个事件字段（不含糊，不静默）。
#     本脚本不负责调用 LLM 重放（需 gateway，见输出 replay_cmd 提示）。
#   方案 C（重复取样）：一组目录含多个 run → token/质量取中位数聚合（真实可用）。
#
# 变更纪律：本文件不引第三方依赖（stdlib only），测试见 compare.test.py（T-U11-*）。
# 运行约定：conda stock_agent 环境，`python3 compare.py ...`。
# ==============================================================================

import argparse
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量与默认规则（本地确定性规则，非 LLM 判评判）
# ---------------------------------------------------------------------------

# company-analysis-simple 固定报告骨架（与 gen_report.py PROMPT 保持一致）
DEFAULT_SKELETON = [
    "## 〇、一句话定位",
    "## 〇、总体结论",
    "## 一、公司今日盘面分析",
    "## 二、公司基本面分析",
    "## 三、综合前瞻判断",
    "## 附：数据缺口说明",
]

# 免责声明标记（仅检查报告末尾 DISCLAIMER_TAIL 字符窗口内，保证"结尾"语义）
DISCLAIMER_MARKERS = ["免责声明", "风险提示", "不构成投资建议", "不作为投资建议"]
DISCLAIMER_TAIL = 500

# 草稿污染标记（规划草稿/思考过程残留被当成正文输出）
DRAFT_MARKERS = [
    "草稿", "思考过程", "规划草稿", "ATTENTION", "TODO", "FIXME",
    r"\d+\s*[.、)]\s*(步骤|step)", "下面我来规划", "我先想一下",
]

# trace 中代表"稳定性风险"的事件类型（超窗/压缩/截断/失败/重试）
SUSPICIOUS_EVENT_RE = re.compile(
    r"compaction|truncat|overflow|overwindow|^error|fail|timeout|retry", re.I)

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _norm_ws(s: str) -> str:
    """去所有空白：行内加固、跨行匹配骨架都用它。"""
    return re.sub(r"\s+", "", s)


def _read_trace_events(trace_path: Path):
    """解析 trace.jsonl → list[dict]；坏行跳过，不崩。"""
    events = []
    for line in trace_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    return events


# ---------------------------------------------------------------------------
# JSON 读取（graceful：缺失/损坏返回 None）
# ---------------------------------------------------------------------------

def load_json(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 布局识别
# ---------------------------------------------------------------------------

def detect_layout(d: Path) -> str:
    """返回 'run' | 'trace' | 'both' | 'none'。none = 目录不存在或两者皆无。"""
    if not d.is_dir():
        return "none"
    has_trace = (d / "trace.jsonl").is_file()
    has_run = (d / "run.json").is_file() and (d / "report.md").is_file()
    if has_trace and has_run:
        return "both"
    if has_trace:
        return "trace"
    if has_run:
        return "run"
    return "none"


# ---------------------------------------------------------------------------
# 归一化：run 布局 → RunSummary
# ---------------------------------------------------------------------------

def run_summary_from_run_dir(d: Path, group: str) -> dict:
    """gen_report.py 布局（单次 completion）。"""
    meta = load_json(d / "run.json") or {}
    usage = load_json(d / "usage.json") or {}
    usage_obj = usage.get("usage") or {}
    report = ""
    rp = d / "report.md"
    if rp.is_file():
        report = rp.read_text(encoding="utf-8", errors="replace")

    pt = usage_obj.get("prompt_tokens")
    ct = usage_obj.get("completion_tokens")
    tt = usage_obj.get("total_tokens")
    if tt is None and (pt is not None or ct is not None):
        tt = (pt or 0) + (ct or 0)
    has_usage = pt is not None or ct is not None or tt is not None

    suspicious = []
    if (d / "error.txt").is_file():
        suspicious.append({"type": "run_error",
                           "note": (d / "error.txt").read_text(errors="replace")[:200]})

    return {
        "run_id": meta.get("run_id") or meta.get("run_tag") or d.name,
        "group": group,
        "layout": "run",
        "stock": meta.get("stock"),
        "rounds": 1,
        "tokens": {
            "input_total": pt or 0,
            "output_total": ct or 0,
            "total": tt or 0,
            "usage_rounds": 1 if has_usage else 0,
            "usage_unavailable": not has_usage,
        },
        "saved_total": 0,
        "compression": {
            "docs_tagged": 0, "docs_pruned": 0,
            "rows_deleted": 0, "rows_left": 0,
            "discard_events": 0, "discard_empty": 0, "docs_payload": 0,
        },
        "stability": {"suspicious": suspicious},
        "report": report,
        "report_chars": len(report),
        "elapsed_sec": usage.get("elapsed_sec"),
    }


# ---------------------------------------------------------------------------
# 归一化：trace 布局 → RunSummary
# ---------------------------------------------------------------------------

def run_summary_from_trace_dir(d: Path, group: str) -> dict:
    """插件 U6 trace 布局（逐轮 token_round / view_before|after / discard_*）。"""
    events = _read_trace_events(d / "trace.jsonl") if (d / "trace.jsonl").is_file() else []
    stats = load_json(d / "run_stats.json") or {}

    inputs, outputs, saved_list, usage_flags = [], [], [], []
    saved_from_view = []
    n_del, n_left = 0, 0
    discard_events = discard_empty = docs_tagged = docs_payload = 0
    suspicious = []

    for ev in events:
        et = ev.get("type")
        if et == "token_round":
            u = ev.get("usage") or {}
            if u.get("prompt_tokens") is not None or u.get("completion_tokens") is not None:
                inputs.append(u.get("prompt_tokens", 0))
                outputs.append(u.get("completion_tokens", 0))
                usage_flags.append(True)
            else:
                inputs.append(ev.get("input") or 0)
                outputs.append(ev.get("output") or 0)
                usage_flags.append(False)
            if ev.get("saved") is not None:
                saved_list.append(max(0, ev["saved"]))
        elif et == "view_after":
            # 同一轮的 saved 在 token_round 与 view_after 各写一次（防重复计）：
            # 仅当没有任何 token_round.saved 时才以 view_after.saved 兜底。
            if ev.get("saved") is not None:
                saved_from_view.append(max(0, ev["saved"]))
        elif et == "discard_applied":
            n_del += ev.get("n_del") or 0
            n_left += ev.get("n_left") or 0
        elif et == "assistant_discard":
            discard_events += 1
        elif et == "discard_empty":
            discard_empty += 1
        elif et == "tagger_doc":
            docs_tagged += 1
        elif et == "payload_doc":
            docs_payload += 1
        if SUSPICIOUS_EVENT_RE.search(et or ""):
            suspicious.append({"ts": ev.get("ts"), "type": et, "note": ev.get("note") or ""})

    if stats.get("degraded") or (stats.get("warn_fallbacks") or 0) > 0:
        suspicious.append({"type": "logger_degraded",
                           "note": "warn_fallbacks=%s" % stats.get("warn_fallbacks")})

    report = ""
    for rp in (d / "report.md", d.parent / "report.md", d / "REPORT.md"):
        if rp.is_file():
            report = rp.read_text(encoding="utf-8", errors="replace")
            break

    # saved：以 token_round.saved 为准；无任何 token_round 记录时以 view_after.saved 兜底
    saved_total = sum(saved_list) if saved_list else sum(saved_from_view)

    return {
        "run_id": stats.get("runId") or d.name,
        "group": group,
        "layout": "trace",
        "stock": None,
        "rounds": len(inputs),
        "tokens": {
            "input_total": sum(inputs),
            "output_total": sum(outputs),
            "total": sum(inputs) + sum(outputs),
            "usage_rounds": sum(usage_flags),
            "usage_unavailable": (not usage_flags) or not any(usage_flags),
        },
        "saved_total": saved_total,
        "compression": {
            "docs_tagged": docs_tagged,
            "docs_pruned": min(docs_tagged, discard_events),
            "rows_deleted": n_del,
            "rows_left": n_left,
            "discard_events": discard_events,
            "discard_empty": discard_empty,
            "docs_payload": docs_payload,
        },
        "stability": {"suspicious": suspicious},
        "report": report,
        "report_chars": len(report),
        "elapsed_sec": None,
    }


# ---------------------------------------------------------------------------
# 质量打分（规则式，本地确定性）
# ---------------------------------------------------------------------------

def quality_score(report: str, *, skeleton=None, draft_markers=None,
                  citation_facts=None, disclaimer_markers=None,
                  disclaimer_tail=DISCLAIMER_TAIL) -> dict:
    """四规则打分，输出 0..1 总分（只对"可用"规则平均；无引源时引用规则记 N/A）。

    规则：
      1) 骨架完整 —— 必需章节标题是否齐全（空白不敏感）
      2) 草稿污染 —— 正文是否混入规划草稿/思考过程标记（命中即扣 0）
      3) 引用准确 —— 与给定事实源比对：数值在原报告文本中是否对得上
         （无事实源 → N/A，不计入总分）
      4) 免责结尾 —— 末尾 disclaimer_tail 字符内是否出现免责标记
    """
    skeleton = skeleton or DEFAULT_SKELETON
    draft_markers = draft_markers or DRAFT_MARKERS
    parts = {}

    norm = _norm_ws(report or "")
    found = 0
    missing_headings = []
    for h in skeleton:
        core = _norm_ws(re.sub(r"^[#\s]+", "", h))
        if core and core in norm:
            found += 1
        else:
            missing_headings.append(h)
    parts["skeleton"] = (found / len(skeleton)) if skeleton else 0.0

    body = report or ""
    hits = []
    for m in draft_markers:
        try:
            if re.search(m, body, re.I):
                hits.append(m)
        except re.error:
            pass
    parts["no_draft_pollution"] = 0.0 if hits else 1.0

    citation_miss = []
    if citation_facts:
        matched = 0
        for fact in citation_facts:
            expected = str(fact.get("value", "")).strip()
            if not expected:
                continue
            if _fact_present(body, expected):
                matched += 1
            else:
                citation_miss.append(fact.get("label", expected))
        parts["citation_accuracy"] = (matched / len(citation_facts)
                                      if citation_facts else 0.0)
    else:
        parts["citation_accuracy"] = None  # N/A：无源无法抽查

    tail = (report or "")[-disclaimer_tail:]
    parts["disclaimer"] = 1.0 if any(
        mk in tail for mk in (disclaimer_markers or DISCLAIMER_MARKERS)) else 0.0

    avail = [v for v in parts.values() if isinstance(v, (int, float))]
    score = (sum(avail) / len(avail)) if avail else 0.0
    return {
        "score": round(score, 6),
        "parts": parts,
        "available": len(avail),
        "details": {"skeleton_missing": missing_headings, "draft_hits": hits,
                    "citation_miss": citation_miss},
    }


def _fact_present(text: str, expected: str) -> bool:
    """数值核对：字符串直接命中（"12.34亿"等）优先，否则按数值在 1% 容差内比对。"""
    if expected in text:
        return True
    try:
        exp_f = float(expected)
    except ValueError:
        return False
    for tok in _NUM_RE.findall(text):
        try:
            act_f = float(tok)
        except ValueError:
            continue
        if act_f == exp_f:
            return True
        if exp_f != 0 and abs(act_f - exp_f) / abs(exp_f) <= 0.01:
            return True
    return False


# ---------------------------------------------------------------------------
# 方案 A / B：上下文重建 + 前置数据校验（不调用 LLM）
# ---------------------------------------------------------------------------

_PLAN_B_PARTIAL_NOTE = (
    "仅找到最终 prompt.txt（单段）；方案 B 需要逐轮 tool_call→tool_result 的 "
    "message 往返才可去皮重放。需在运行端（gen_report.py / gateway）落盘每轮 messages。")

def replay_prereqs_plan_a(trace_dir: Path) -> dict:
    """方案 A：插件组"每轮压缩前（原始未删减）messages"是否就绪。

    §6/§U6 验收要求 trace 记录每轮压缩前/后 messages（存 payload 文件）+ 原始 tool 结果。
    当前 U6 只写了 view_before/view_after 的 token 摘要，未持久化 messages 本体。
    检测到具备 payload 引用（view_before 带 payload_ref）或 contexts/ 目录 → ready；
    否则给出明确的补数据规格（不漏在状态外）。
    """
    missing = []
    ctx_dir = trace_dir / "contexts"
    events_with_payload = []
    tp = trace_dir / "trace.jsonl"
    if tp.is_file():
        for ev in _read_trace_events(tp):
            if ev.get("type") == "view_before" and (ev.get("payload_ref") or ev.get("payload")):
                events_with_payload.append(ev)

    if ctx_dir.is_dir():
        items = sorted(p.name for p in ctx_dir.glob("round_*.json"))
        status = "ready"
        spec = {"ctx_files": items}
    elif events_with_payload:
        refs = [e["payload_ref"] for e in events_with_payload if e.get("payload_ref")]
        inline = [e.get("ts") for e in events_with_payload if not e.get("payload_ref")]
        items = refs
        status = "ready"
        spec = {"payload_refs": refs,
                "inline_count": len(inline),
                "hint": "payload_ref → trace_payloads/<id>.json；inline 事件内 payload 字段即压缩前 messages"}
    else:
        items = []
        status = "prereq_missing"
        missing.append(
            "view_before 未携带每轮压缩前 messages（缺 payload_ref / payload 字段）。"
            "插件端需开启 persistViewPayloads（默认 true；该 trace 可能来自关闭此配置的 run，"
            "或上一版插件未入库）——装配层已实现：每轮 context 组装后、压缩前把 messages 写 "
            "trace_payloads/ 并在 view_before 带 payload_ref（§6 验收）。")
        spec = {"expected_event": "view_before", "expected_payload_ref": True,
                "config_flag": "persistViewPayloads"}

    return {
        "plan": "A", "status": status, "missing": missing,
        "replay_ready": items, "spec": spec,
        "replay_cmd": (
            "python3 gen_report.py <stock> --context-file <round_N.json>   "
            "# 逐轮把重建上下文喂全新 LLM 会话，对比 R_plug vs R_full"
            if status == "ready"
            else "（前置数据缺失：补 trace 后再重放）"),
    }


def replay_prereqs_plan_b(run_dir: Path) -> dict:
    """方案 B：无插件组"每轮原始上下文段"是否就绪（去皮重放输入）。

    需要 ctx_noplug 的逐段上下文（contexts/*.json 或 requests/*.json）。
    现 gen_report.py 只落 prompt.txt（单次 completion 的最终 prompt）→ 判为 partial/缺失。
    """
    missing = []
    files = []
    ctx_dir = run_dir / "contexts"
    req_dir = run_dir / "requests"
    prompt_only = (req_dir / "prompt.txt").is_file()

    if ctx_dir.is_dir():
        files = sorted(p.name for p in ctx_dir.glob("*.json"))
        if files:
            status = "ready"
        elif prompt_only:
            status = "partial"
            files = ["prompt.txt"]
            missing.append(_PLAN_B_PARTIAL_NOTE)
        else:
            status = "prereq_missing"
            missing.append("contexts/ 目录存在但没有 *.json。")
    elif req_dir.is_dir():
        files = sorted(p.name for p in req_dir.glob("*.json"))
        if files:
            status = "ready"
        elif prompt_only:
            # 只有最终 prompt：可作"单段"输入（无中间 tool 往返），标注受限
            status = "partial"
            files = ["prompt.txt"]
            missing.append(_PLAN_B_PARTIAL_NOTE)
        else:
            status = "prereq_missing"
            missing.append("requests/ 目录存在但没有 *.json。")
    else:
        status = "prereq_missing"
        missing.append(
            "未找到任何上下文段（contexts/*.json 或 requests/*.json）。"
            "需在无插件组运行端持久化每轮完整 messages。")

    return {
        "plan": "B", "status": status, "missing": missing,
        "ctx_files": files,
        "replay_cmd": (
            "把各上下文段逐段喂装有插件的 agent：不取模型输出，只跑删行逻辑，"
            "删减结果按序拼接喂同一 LLM 生成 R_replay（对比 R_base）。"
            if status in ("ready", "partial")
            else "（前置数据缺失：补中间轮 messages 后再重放）"),
    }


# ---------------------------------------------------------------------------
# 聚合与对比
# ---------------------------------------------------------------------------

def _median(xs):
    return statistics.median(xs) if xs else None


def aggregate_runs(runs, group_name):
    """方案 C：组内多 run 聚合（token/质量中位数）。"""
    totals = [r["tokens"]["total"] for r in runs]
    inpts = [r["tokens"]["input_total"] for r in runs]
    outpts = [r["tokens"]["output_total"] for r in runs]
    saved = [r["saved_total"] for r in runs]
    quals = [r["quality"]["score"] for r in runs
             if isinstance(r.get("quality"), dict) and "score" in r["quality"]]
    vals = [r["value"] for r in runs if r.get("value") is not None]
    usage_unavail_runs = [r["run_id"] for r in runs if r["tokens"]["usage_unavailable"]]

    def st(xs):
        m = _median(xs)
        return {"median": round(m, 6) if m is not None else None, "n": len(xs)}

    susp = []
    for r in runs:
        for s in r.get("stability", {}).get("suspicious", []):
            susp.append({**s, "run_id": r.get("run_id", "")})

    return {
        "name": group_name,
        "n_runs": len(runs),
        "tokens": {
            "input": st(inpts), "output": st(outpts), "total": st(totals),
            "usage_unavailable_runs": usage_unavail_runs,
        },
        "saved": st(saved),
        "quality": st(quals),
        "value": st(vals),
        "stability": {"suspicious_total": len(susp), "suspicious": susp},
    }


def compare(groups, *, facts=None, out_dir=None, skeleton=None) -> dict:
    """主流程：groups=[{name, paths:[Path,...], role?}] → 结果 dict。"""
    out_dir = Path(out_dir) if out_dir else None
    group_summaries = []
    per_run = {}

    for g in groups:
        runs = []
        for p in g["paths"]:
            p = Path(p)
            layout = detect_layout(p)
            if layout == "none":
                runs.append({
                    "run_id": p.name, "group": g["name"], "layout": "none",
                    "error": "目录不存在或产物不可识别（无 report.md / trace.jsonl）",
                    "report": "", "report_chars": 0, "tokens": None,
                    "quality": None, "value": None, "elapsed_sec": None,
                })
                continue
            if layout in ("run", "both"):
                rs = run_summary_from_run_dir(p, g["name"])
            else:
                rs = run_summary_from_trace_dir(p, g["name"])
            if rs["report"]:
                q = quality_score(rs["report"], citation_facts=facts, skeleton=skeleton)
            else:
                q = None  # 无报告文本 → 质量 N/A（不计入组中位数）
            total = (rs["tokens"] or {}).get("total") or 0
            rs["quality"] = q
            rs["value"] = (q["score"] / total) if (q and total > 0) else None
            runs.append(rs)
        per_run[g["name"]] = runs
        group_summaries.append(
            aggregate_runs([r for r in runs if r.get("layout") != "none"], g["name"]))

    # 方案 A/B 前置校验：插件组 trace 目录 → A；对照组 run 目录 → B
    plans = {}
    plugin = next((g for g in groups if g.get("role") == "plugin"), None)
    baseline = next((g for g in groups if g.get("role") == "baseline"), None)
    if plugin:
        plans["A"] = [
            replay_prereqs_plan_a(Path(p)) for p in plugin["paths"]
            if detect_layout(Path(p)) in ("trace", "both")
        ]
    if baseline:
        plans["B"] = [
            replay_prereqs_plan_b(Path(p)) for p in baseline["paths"]
            if detect_layout(Path(p)) in ("run", "both")
        ]

    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "groups": [{"name": g["name"], "paths": [str(x) for x in g["paths"]],
                    "role": g.get("role", "compare")} for g in groups],
        "per_group": group_summaries,
        "per_run": per_run,
        "plans": plans,
        "facts_used": bool(facts),
    }
    if out_dir:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "compare_metrics.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "compare_report.md").write_text(
            render_markdown(result), encoding="utf-8")
        _dump_replay_ctx(result, out_dir)
    return result


def _dump_replay_ctx(result, out_dir):
    """方案 A/B 就绪项的 replay 上下文（spec + 命令）落盘，供联调阶段直接消费。"""
    for plan, entries in result.get("plans", {}).items():
        for i, e in enumerate(entries):
            if e.get("status") == "ready":
                d = out_dir / f"plan_{plan.lower()}_ctx" / f"item_{i}"
                d.mkdir(parents=True, exist_ok=True)
                (d / "replay_item.json").write_text(
                    json.dumps(
                        {"plan": plan, "spec": e.get("spec", {}),
                         "replay_ready": e.get("replay_ready", []),
                         "replay_cmd": e.get("replay_cmd", "")},
                        ensure_ascii=False, indent=2),
                    encoding="utf-8")


# ---------------------------------------------------------------------------
# Markdown 渲染
# ---------------------------------------------------------------------------

def render_markdown(result: dict) -> str:
    L = []
    L.append("# keeper 效果对比报告\n")
    L.append(f"> 生成时间：{result['generated_at']}")
    L.append(f"> 引用抽查：{'启用' if result['facts_used'] else '未启用（引用规则记 N/A）'}\n")

    for g in result["per_group"]:
        L.append(f"## 组：{g['name']}（{g['n_runs']} runs）\n")
        if g["n_runs"] == 0:
            L.append("> ⚠️ **数据缺失**：本组无可用 run（目录不存在或产物不可识别）\n")
            continue
        t = g["tokens"]
        L.append("| 指标 | 中位数 |")
        L.append("|---|---|")
        L.append(f"| token input | {t['input']['median']} |")
        L.append(f"| token output | {t['output']['median']} |")
        L.append(f"| token total | {t['total']['median']} |")
        L.append(f"| 压缩节省 saved | {g['saved']['median']} |")
        L.append(f"| 质量分 | {g['quality']['median']} |")
        L.append(f"| 性价比(质量/total) | {g['value']['median']} |")
        if t.get("usage_unavailable_runs"):
            L.append(f"| usage 缺失 run | {', '.join(t['usage_unavailable_runs'])} |")
        L.append(f"| 稳定性可疑事件 | {g['stability']['suspicious_total']} |\n")
        for s in g["stability"]["suspicious"][:10]:
            L.append(f"- ⚠️ `{s.get('run_id', '')}` {s.get('type')}: {s.get('note', '')}")
        if g["stability"]["suspicious"]:
            L.append("")

    names = [g["name"] for g in result["per_group"]]
    if len(names) == 2:
        a, b = result["per_group"][0], result["per_group"][1]
        ta, tb = a["tokens"]["total"]["median"], b["tokens"]["total"]["median"]
        qa, qb = a["quality"]["median"], b["quality"]["median"]
        L.append("## 组间对比\n")
        L.append("| 指标 | baseline | plugin | Δ(插件−基线) |")
        L.append("|---|---|---|---|")
        L.append(f"| token total | {ta} | {tb} | {_delta(ta, tb)} |")
        L.append(f"| 质量分 | {qa} | {qb} | {_delta(qa, qb)} |")
        if ta and tb:
            L.append(f"| token 节省率 | — | — | {(1 - tb / ta) * 100:+.1f}% |\n")

    for plan in ("A", "B"):
        entries = result.get("plans", {}).get(plan, [])
        L.append(f"## 方案 {plan} 状态\n")
        if not entries:
            L.append("> 无对应组/目录，跳过。\n")
            continue
        for e in entries:
            why = "; ".join(e.get("missing", [])) or "数据就绪"
            L.append(f"- **{e['status']}**：{why}")
            if e.get("replay_cmd"):
                L.append(f"  - 重放：`{e['replay_cmd']}`")
        L.append("")

    L.append("## 方案 C（重复取样）\n")
    L.append("各组中位数已在上文列出；N≥3 时中位数口径可压制 temperature≠0 的单次随机性。\n")
    return "\n".join(L)


def _delta(a, b):
    if a is None and b is None:
        return "—"
    if a is None or b is None:
        return "见单组值"
    return f"{b - a:+.4g}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_group_from_arg(arg: str) -> dict:
    """接受 `name=dir[;dir2...]`（多 dir 为多 run，方案 C 中位数聚合）。"""
    parts = arg.split("=", 1)
    if len(parts) != 2:
        raise SystemExit(f"组参数格式错误：{arg!r}（应为 name=dir[;dir2...]）")
    name, rest = parts
    paths = [p for p in re.split(r"[;=]", rest) if p]
    if not paths:
        raise SystemExit(f"组 {name!r} 未给出任何目录")
    return {"name": name, "paths": paths}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="keeper 效果对比：质量/token/性价比/稳定性 + 方案 A/B/C",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--group", action="append", required=True, metavar="name=dir[;dir2...]",
                    help="组定义，可多个。dir 可为 run 布局或 trace 布局；多 dir = 方案 C")
    ap.add_argument("--role-baseline", metavar="name", help="标记该组为对照组（供方案 B）")
    ap.add_argument("--role-plugin", metavar="name", help="标记该组为插件组（供方案 A）")
    ap.add_argument("--facts", metavar="JSON", help="引用抽查事实源 {label,value}[]（可选）")
    ap.add_argument("--out", metavar="DIR", help="输出目录（默认 compare_out/时间戳）")
    args = ap.parse_args(argv)

    groups = [build_group_from_arg(g) for g in args.group]
    for g in groups:
        if g["name"] == args.role_baseline:
            g["role"] = "baseline"
        elif g["name"] == args.role_plugin:
            g["role"] = "plugin"

    facts = None
    if args.facts:
        f = load_json(Path(args.facts))
        if not isinstance(f, list):
            raise SystemExit(f"--facts 应为 JSON 数组（{args.facts}）")
        facts = f

    out_dir = args.out or f"compare_out/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    result = compare(groups, facts=facts, out_dir=out_dir)
    print(render_markdown(result))
    print(f"\n📄 指标 JSON: {Path(out_dir) / 'compare_metrics.json'}")
    print(f"📄 报告 MD  : {Path(out_dir) / 'compare_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())