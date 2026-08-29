#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
keeper 实验室 —— 简化版公司分析报告生成器 + 全过程日志

用途：在 keeper 独立 OpenClaw 环境里生成"简化版公司分析报告"，并把每次运行的
全过程（每轮 tool 调用、tool 结果、模型回复、token 度量、耗时）记录下来，
供诊断/效果评估/平行对比使用。

设计对照：
- 生产 `mx_company_reporter/company_report_api.py` 的简化版
- 差异：
  1) 不调 mx MCP（有限额）—— keeper 环境的 agent 用同花顺 IWENCAI 取数
  2) target keeper 独立 gateway（默认 127.0.0.1:19501）
  3) 记录完整日志到 logs/{run_tag}/
  4) 不依赖 openclaw_rpc（生产删会话那套），keeper 环境简单化，可选保留

用法：
    python3 gen_report.py <股票名> [--run-tag T] [--logs-dir DIR] [--reports-dir DIR] [--gateway PORT] [--agent keeper]
"""
import argparse
import json
import os
import sys
import time
import uuid
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------- 默认值 ----------
DEFAULT_GATEWAY = "http://127.0.0.1:19501"   # keeper profile gateway 端口
DEFAULT_AGENT_MODEL = "openclaw/keeper"       # 路由到 keeper agent
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

# ---------- 日志工具 ----------

def _load_token():
    """读取 keeper gateway 的 auth token（环境变量优先，其次 profile 配置）。"""
    env = os.environ.get("OPENCLAW_GATEWAY_TOKEN")
    if env:
        return env
    # keeper profile 配置
    for p in [Path.home()/".openclaw-keeper/openclaw.json",
              PROJECT_DIR/"config/openclaw.json"]:
        if p.exists():
            try:
                return json.load(open(p, encoding="utf-8"))["gateway"]["auth"]["token"]
            except Exception:
                continue
    return ""


def _chat_once(session_key: str, user_message: str,
               gateway_base: str, model: str, timeout: int = 600) -> dict:
    """通过 OpenAI 兼容端点执行一次 agent 调用。

    返回 {"content": 最终回复, "usage": {...}, "raw": 完整响应}。
    """
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": user_message}],
    }).encode()
    req = urllib.request.Request(
        f"{gateway_base}/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {_load_token()}",
            "Content-Type": "application/json",
            "x-openclaw-session-key": session_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = json.load(resp)
    choice = raw["choices"][0]["message"]
    return {
        "content": choice.get("content", ""),
        "usage": raw.get("usage", {}),
        "raw": raw,
    }


def _safe_filename(name: str) -> str:
    return "".join(c for c in name if c not in '\\/:*?"<>|').strip() or "stock"


# ---------- 报告 prompt ----------

PROMPT_TEMPLATE = """请对【{stock}】进行上市公司深度分析（keeper 实验版）。

要求：
1. 先读取并使用你的 company-analysis-simple 技能框架（SKILL.md，v1.0），严格按其"固定报告骨架"输出：
   ## 〇、一句话定位
   ## 〇、总体结论（2-4 段，每段=总结句+知识点 bullets）
   ## 一、公司今日盘面分析（六章：当前表现/资金动向/融资融券与筹码博弈/机构成本参考/涨跌归因/行情总结与策略思考）
   ## 二、公司基本面分析（五章：业务与发展/行业面/盈利模式/财务面含近3年趋势表/人力资源面）
   ## 三、综合前瞻判断
   ## 附：数据缺口说明
   末尾附免责声明。
2. 输出铁律：每章先写"综合总结"散文段（含 1-2 句前瞻），再用加粗子项 bullets 展开；
   结论导向不堆数据（每子项 1-3 个关键数据，用语言描述）；禁止黑话压缩过程，展开
   "谁做了什么→结果→接下来怎样"；基础股市/财务术语直接用不翻译；加粗=核心结论/关键数据、
   斜体=前瞻/外部引用/缺失、⚠️=风险、✅=积极信号。
3. 取数：**只使用同花顺 IWENCAI 系列 skill**（hithink-market-query / finance / management /
   business / event / industry / basicinfo-query），调用方式：
   python3 ~/stock_research_agent/skills/hithink-<name>/scripts/cli.py --query "<自然语言问句>"
   获取：盘面（近10交易日行情/资金流向/技术指标）、财务（近3年营收/净利/毛利率/ROE/负债率/现金流）、
   股本股东、估值、主营、事件公告、行业数据。
   **严禁调用 mx-ds-mcp 系列工具**（keeper 环境无 mx MCP）。
4. 数据不足的项明确标注"数据缺失（keeper 实验数据受限）"（斜体），不做无依据推测。"""


# ---------- 主流程 ----------

def run(stock: str, run_tag: str, logs_dir: Path, reports_dir: Path,
        gateway_base: str, model: str, timeout: int = 600) -> dict:
    """执行一次报告生成，记录日志，返回结果字典。"""
    session_key = f"keeper-report-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    run_dir = logs_dir / run_tag
    req_dir = run_dir / "requests"
    resp_dir = run_dir / "responses"
    req_dir.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)

    start = time.time()
    meta = {
        "run_id": run_tag,
        "run_tag": run_tag,
        "stock": stock,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_key": session_key,
        "gateway_base": gateway_base,
        "model": model,
        "skill": "company-analysis-simple",
        "data_source": "iwencai (同花顺)",
        "cwd": str(SCRIPT_DIR),
    }
    (run_dir / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                      encoding="utf-8")

    prompt = PROMPT_TEMPLATE.format(stock=stock)
    (req_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    result = {"ok": False, "stock": stock, "report": "", "md_path": None,
              "session_key": session_key, "meta": meta}
    try:
        print(f"[{run_tag}] 调用 keeper agent({model})...")
        chat = _chat_once(session_key, prompt, gateway_base, model, timeout=timeout)
        report = chat["content"]
        usage = chat["usage"]

        result["report"] = report
        result["usage"] = usage
        result["elapsed_sec"] = round(time.time() - start, 2)

        # 落盘报告
        reports_dir.mkdir(parents=True, exist_ok=True)
        date = datetime.now().strftime("%Y%m%d")
        md_path = reports_dir / f"{date}_{_safe_filename(stock)}_公司分析报告.md"
        header = (f"# {stock} 公司分析报告\n\n"
                  f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                  f"> 生成方式: keeper 实验环境 (同花顺数据)\n"
                  f"> run_tag: {run_tag}\n\n---\n\n")
        md_path.write_text(header + report + "\n", encoding="utf-8")
        result["md_path"] = str(md_path)

        # 写日志：usage + 最终回复
        (run_dir / "usage.json").write_text(
            json.dumps({"usage": usage, "elapsed_sec": result["elapsed_sec"],
                        "report_chars": len(report)},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "report.md").write_text(report, encoding="utf-8")

        # 完整响应（含中间 tool 过程的 agent 端返回，若有）
        (run_dir / "raw_response.json").write_text(
            json.dumps(chat.get("raw", {}), ensure_ascii=False, indent=2),
            encoding="utf-8")

        result["ok"] = True
        print(f"[{run_tag}] 完成，用时 {result['elapsed_sec']}s，报告 {len(report)} chars")
    except Exception as e:
        result["error"] = str(e)
        (run_dir / "error.txt").write_text(str(e), encoding="utf-8")
        print(f"[{run_tag}] 失败: {e}", file=sys.stderr)
    finally:
        result["elapsed_sec"] = result.get("elapsed_sec") or round(time.time() - start, 2)
        with (run_dir / "result.json").open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    return result


def main():
    ap = argparse.ArgumentParser(description="keeper 简化版公司报告生成 + 全日志")
    ap.add_argument("stock", help="股票名称")
    ap.add_argument("--run-tag", default=None, help="run 标识（默认时间戳）")
    ap.add_argument("--logs-dir", default=str(PROJECT_DIR / "logs"))
    ap.add_argument("--reports-dir", default=str(PROJECT_DIR / "data" / "reports"))
    ap.add_argument("--gateway", default=DEFAULT_GATEWAY, help=f"keeper gateway 基址（默认 {DEFAULT_GATEWAY}）")
    ap.add_argument("--agent", default="keeper", help="agent model 名（默认 openclaw/keeper）")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    run_tag = args.run_tag or datetime.now().strftime("%Y%m%d_%H%M%S")
    model = args.agent if args.agent.startswith(("openclaw/", "opencode")) else f"openclaw/{args.agent}"
    r = run(args.stock, run_tag, Path(args.logs_dir), Path(args.reports_dir),
            args.gateway, model, timeout=args.timeout)
    if r.get("ok"):
        print("✅ 报告已生成:", r["md_path"])
        print("📁 日志目录:", Path(args.logs_dir) / run_tag)
    else:
        print("❌ 失败:", r.get("error"))
        sys.exit(1)


if __name__ == "__main__":
    main()
