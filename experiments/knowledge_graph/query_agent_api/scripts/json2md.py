#!/usr/bin/env python3
"""Convert e2e_detail JSON report to readable Markdown"""

import json, os, sys

REPORT_PATH = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "data", "e2e_detail_20260717_160405.json")

with open(REPORT_PATH, encoding="utf-8") as f:
    report = json.load(f)

tests = report["tests"]
ts = report["timestamp"]
model = report.get("model", "?")

total = len(tests)
passed = sum(1 for t in tests if t["success"])
failed = total - passed

# ── Build Markdown ──────────────────────────────────────────────
lines = []
lines.append(f"# 端到端全链路测试报告")
lines.append(f"")
lines.append(f"| 项目 | 值 |")
lines.append(f"|------|-----|")
lines.append(f"| 时间 | {ts} |")
lines.append(f"| 模型 | {model} |")
lines.append(f"| 测试总数 | {total} |")
lines.append(f"| ✅ 通过 | {passed} ({passed*100//total}%) |")
lines.append(f"| ❌ 失败 | {failed} |")
lines.append(f"")

# ── Summary Table ──
lines.append(f"## 测试总览")
lines.append(f"")
lines.append(f"| ID | 状态 | 查询 | 模式 | 结果 |")
lines.append(f"|:--|:---:|:-----|:----:|:-----|")
for t in tests:
    icon = "✅" if t["success"] else "❌"
    mode = t.get("mode", "?")
    summary = t.get("summary", "")
    lines.append(f"| {t['id']} | {icon} | {t['query']} | {mode} | {summary} |")
lines.append(f"")

# ── Failed Tests Highlight ──
if failed:
    lines.append(f"---")
    lines.append(f"## ❌ 失败测试详情")
    lines.append(f"")
    for t in tests:
        if not t["success"]:
            lines.append(f"### {t['id']}: {t['query']}")
            lines.append(f"")
            lines.append(f"**状态**: ❌ 失败")
            lines.append(f"")
            for req in t.get("requests", []):
                req_id = req.get("req_id", "?")
                err = req.get("error", "")
                lines.append(f"#### {req_id}")
                lines.append(f"")
                lines.append(f"```")
                lines.append(f"{err}")
                lines.append(f"```")
                lines.append(f"")
                # log steps (grouped by step name)
                grouped = {}
                for entry in req.get("log", []):
                    step = entry.get("step", "")
                    grouped.setdefault(step, {"action": "", "inputs": [], "outputs": [], "errors": [], "elapsed": ""})
                    g = grouped[step]
                    if entry.get("action"): g["action"] = entry["action"]
                    if entry.get("input"): g["inputs"].append(entry["input"])
                    if entry.get("output"): g["outputs"].append(entry["output"])
                    if entry.get("error"): g["errors"].append(entry["error"])
                    if entry.get("elapsed"): g["elapsed"] = entry["elapsed"]
                for step_name, g in grouped.items():
                    lines.append(f"**{step_name}** ({g['elapsed']}s)" if g['elapsed'] else f"**{step_name}**")
                    lines.append(f"")
                    if g.get("action"):
                        lines.append(f"*{g['action']}*")
                        lines.append(f"")
                    for inp in g["inputs"]:
                        lines.append(f"<details><summary>输入</summary>")
                        lines.append(f"")
                        lines.append(f"```json")
                        lines.append(json.dumps(inp, ensure_ascii=False, indent=2))
                        lines.append(f"```")
                        lines.append(f"</details>")
                        lines.append(f"")
                    for out in g["outputs"]:
                        lines.append(f"<details><summary>输出</summary>")
                        lines.append(f"")
                        lines.append(f"```json")
                        lines.append(json.dumps(out, ensure_ascii=False, indent=2))
                        lines.append(f"```")
                        lines.append(f"</details>")
                        lines.append(f"")
                    for err_ in g["errors"]:
                        lines.append(f"**错误**: {err_}")
                        lines.append(f"")

# ── Passed Tests ──
lines.append(f"---")
lines.append(f"## ✅ 通过测试详情")
lines.append(f"")

for t in tests:
    if not t["success"]:
        continue

    lines.append(f"### {t['id']}: {t['query']}")
    lines.append(f"")
    lines.append(f"**模式**: {t.get('mode', '')} | **chain**: {t.get('chain', False)} | **结果**: {t.get('summary', '')}")
    lines.append(f"")

    for req in t.get("requests", []):
        req_id = req.get("req_id", "?")
        entity_value = req.get("entity_value", "")
        field_id = req.get("field_id", "")
        ds_info = req.get("datasource", {})
        ds_id = ds_info.get("id", "")
        protocol = ds_info.get("protocol", "")
        result = req.get("result", [])

        lines.append(f"<details>")
        lines.append(f"<summary><b>{req_id}</b> — {ds_id} ({protocol}) | field: {field_id} | entity: {entity_value}</summary>")
        lines.append(f"")

        # result highlight
        if result:
            lines.append(f"**结果数据**: `{result}`")
            lines.append(f"")
        else:
            lines.append(f"**结果**: 空数据（路由验证模式）")
            lines.append(f"")

        # 按 step 名称分组（合并同一个 step 的 input/output）
        grouped = {}
        for entry in req.get("log", []):
            step = entry.get("step", "")
            grouped.setdefault(step, {"action": "", "inputs": [], "outputs": [], "errors": [], "elapsed": ""})
            g = grouped[step]
            if entry.get("action"): g["action"] = entry["action"]
            if entry.get("input"): g["inputs"].append(entry["input"])
            if entry.get("output"): g["outputs"].append(entry["output"])
            if entry.get("error"): g["errors"].append(entry["error"])
            if entry.get("elapsed"): g["elapsed"] = entry["elapsed"]

        for step_name, g in grouped.items():
            lines.append(f"**{step_name}** ({g['elapsed']}s)" if g['elapsed'] else f"**{step_name}**")
            lines.append(f"")
            if g.get("action"):
                lines.append(f"*{g['action']}*")
                lines.append(f"")
            for inp in g["inputs"]:
                inp_str = json.dumps(inp, ensure_ascii=False, indent=2)
                lines.append(f"```json")
                lines.append(f"{inp_str}")
                lines.append(f"```")
                lines.append(f"")
            for out in g["outputs"]:
                out_str = json.dumps(out, ensure_ascii=False, indent=2, default=str)
                lines.append(f"```json")
                lines.append(f"{out_str}")
                lines.append(f"```")
                lines.append(f"")
            for err_ in g["errors"]:
                lines.append(f"> ❌ **错误**: {err_}")
                lines.append(f"")

        lines.append(f"</details>")
        lines.append(f"")

# ── Known Issues ──
lines.append(f"---")
lines.append(f"## 已知问题")
lines.append(f"")
lines.append(f"| 测试 | 问题 | 原因 |")
lines.append(f"|:----|:-----|:-----|")
lines.append(f"| E2E-06 / E2E-10 | Tushare index_daily 当日数据为空 | Tushare 指数日线数据在收盘后才能获取，盘中/盘前无数据 |")
lines.append(f"| E2E-17 | Tushare fina_indicator ROE 返回空数据 | 财务指标数据按季度发布，当前非财报季可能无最新值 |")
lines.append(f"| E2E-22 | Tushare cn_macro 接口名错误 | LLM 使用了 `pro.cn_macro()` 但实际接口为 `pro.cn_m()`，需完善 prompt |")
lines.append(f"")

lines.append(f"---")
lines.append(f"*报告生成时间: {ts}*")

md = "\n".join(lines)

out_path = REPORT_PATH.replace(".json", ".md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(md)

print(f"✅ 已生成: {out_path}")
print(f"   文件大小: {os.path.getsize(out_path)/1024:.1f} KB")
