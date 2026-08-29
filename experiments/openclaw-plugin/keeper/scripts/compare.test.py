#!/usr/bin/env python3
# ==============================================================================
# keeper U11 —— compare.py 单元测试（T-U11-*）
# ==============================================================================
# 覆盖（DEVELOPMENT_PLAN.md §4 U11 / §8 追踪表）：
#   T-U11-1  冒烟：合成固定数字 → 指标与报告正确
#   T-U11-2  run 组缺失 → 结构化"数据缺失"而非崩
#   T-U11-3  质量四规则正反例 + 无引源 N/A
#   T-U11-4  性价比 = 质量分 ÷ total_tokens 计算正确
#   （开发后补的极端/罕见 50%）：
#   T-U11-5  布局自动识别 run/trace/both/none
#   T-U11-6  方案 A/B 前置数据校验：缺失给规格、就绪可重建
# 运行：conda stock_agent 环境 `python compare.test.py`（本文件同样兼容 unittest）。
# ==============================================================================

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare  # noqa: E402

TMPROOT = Path(os.environ.get("CLAUDE_JOB_DIR", "/tmp")) / "keeper_compare_test"

_HEADINGS = [
    "## 〇、一句话定位",
    "## 〇、总体结论",
    "## 一、公司今日盘面分析",
    "## 二、公司基本面分析",
    "## 三、综合前瞻判断",
    "## 附：数据缺口说明",
]

GOOD_REPORT = "\n".join(_HEADINGS) + """
某股今日获主力资金净流入，表现强于大盘。
公司主营芯片设计，营收连续三年增长，毛利率稳步回升。
以上内容仅供参考，不构成投资建议。
"""


class CompareTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=str(TMPROOT)))

    def tearDown(self):
        if Path(os.environ.get("KEEPER_TEST_KEEP", "")).exists():
            return
        shutil.rmtree(self.tmp, ignore_errors=True)


def write_run_dir(root: Path, name: str, *, prompt=3000, completion=700,
                  report=None, with_error=False):
    d = root / name
    d.mkdir(parents=True)
    (d / "run.json").write_text(
        json.dumps({"run_id": name, "run_tag": name, "stock": "测试股"}, ensure_ascii=False),
        encoding="utf-8")
    (d / "usage.json").write_text(json.dumps({
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion,
                  "total_tokens": prompt + completion},
        "elapsed_sec": 12.3}), encoding="utf-8")
    (d / "report.md").write_text(report or GOOD_REPORT, encoding="utf-8")
    (d / "result.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    if with_error:
        (d / "error.txt").write_text("api timeout", encoding="utf-8")
    return d


def write_trace_dir(root: Path, name: str, events, stats=None):
    d = root / name
    d.mkdir(parents=True)
    lines = "\n".join(json.dumps(e, ensure_ascii=False) for e in events)
    (d / "trace.jsonl").write_text(lines + "\n", encoding="utf-8")
    (d / "run_stats.json").write_text(json.dumps(
        stats or {"runId": name, "events_by_type": {}, "degraded": False,
                  "warn_fallbacks": 0}), encoding="utf-8")
    return d


PLUGIN_TRACE = [
    {"ts": "2026-08-26T10:00:00.000Z", "type": "run_start", "run": "plug", "version": "0.1.0"},
    {"ts": "2026-08-26T10:00:01.000Z", "type": "tagger_doc", "doc_id": "doc_0", "n_rows": 10,
     "n_sections": 1, "n_chars": 800},
    {"ts": "2026-08-26T10:00:02.000Z", "type": "token_round", "round": 1, "input": 2000,
     "output": 300, "usage": None, "saved": 500},
    {"ts": "2026-08-26T10:00:03.000Z", "type": "assistant_discard", "tool_calls": 1,
     "doc_id": "doc_0", "discard_lines": [1, 2, 3]},
    {"ts": "2026-08-26T10:00:04.000Z", "type": "discard_applied", "doc_id": "doc_0",
     "n_del": 3, "n_left": 7, "lines": [1, 2, 3]},
    {"ts": "2026-08-26T10:00:05.000Z", "type": "token_round", "round": 2, "input": 1800,
     "output": 400, "usage": None, "saved": 550},
    # view_after 与 token_round 同轮 saved 只算一次（防重复计）
    {"ts": "2026-08-26T10:00:06.000Z", "type": "view_after", "view": "compressed",
     "tokens": 1500, "n_messages": 6, "saved": 300},
    # 损坏行：解析器应跳过不崩
    "this is not json {{{",
    {"ts": "2026-08-26T10:00:07.000Z", "type": "run_finalized", "events_total": 7,
     "warn_fallbacks": 0},
]


class TestMetricsSmoke(CompareTestBase):
    """T-U11-1：合成固定数字 → RunSummary + 组聚合 + 报告正确。"""

    def test_run_summary_baseline(self):
        d = write_run_dir(self.tmp, "base")
        s = compare.run_summary_from_run_dir(d, "baseline")
        self.assertEqual(s["layout"], "run")
        self.assertEqual(s["tokens"]["total"], 3700)
        self.assertEqual(s["tokens"]["input_total"], 3000)
        self.assertEqual(s["tokens"]["output_total"], 700)
        self.assertFalse(s["tokens"]["usage_unavailable"])
        self.assertEqual(s["saved_total"], 0)

    def test_trace_summary_plugin(self):
        d = write_trace_dir(self.tmp, "plug", PLUGIN_TRACE)
        s = compare.run_summary_from_trace_dir(d, "plugin")
        self.assertEqual(s["layout"], "trace")
        self.assertEqual(s["tokens"]["total"], 4500)       # 2000+1800 in, 300+400 out
        self.assertEqual(s["saved_total"], 1050)           # 500+550（view_after 300 不重复计）
        self.assertEqual(s["compression"]["rows_deleted"], 3)
        self.assertEqual(s["compression"]["discard_events"], 1)
        self.assertEqual(s["compression"]["docs_tagged"], 1)
        self.assertTrue(s["tokens"]["usage_unavailable"])  # 两轮 usage 均缺失
        # 损坏行被跳过，不崩
        self.assertEqual(s["rounds"], 2)

    def test_compare_full_flow_and_report(self):
        base = write_run_dir(self.tmp, "base")
        plug = write_trace_dir(self.tmp, "plug", PLUGIN_TRACE)
        out = self.tmp / "out"
        groups = [
            {"name": "baseline", "paths": [base], "role": "baseline"},
            {"name": "plugin", "paths": [plug], "role": "plugin"},
        ]
        r = compare.compare(groups, out_dir=out)

        g0, g1 = r["per_group"][0], r["per_group"][1]
        self.assertEqual(g0["tokens"]["total"]["median"], 3700)
        self.assertEqual(g1["tokens"]["total"]["median"], 4500)
        self.assertEqual(g1["saved"]["median"], 1050)
        self.assertEqual(g0["saved"]["median"], 0)
        self.assertEqual(g0["quality"]["median"], 1.0)     # GOOD_REPORT 全骨架+免责
        # 方案 A/B 路由正确
        self.assertEqual(len(r["plans"]["A"]), 1)
        self.assertEqual(len(r["plans"]["B"]), 1)
        md = compare.render_markdown(r)
        self.assertIn("## 组间对比", md)
        self.assertIn("## 方案 C", md)
        self.assertIn("token 节省率", md)
        # 文件落盘
        self.assertTrue((out / "compare_metrics.json").is_file())
        self.assertTrue((out / "compare_report.md").is_file())


class TestMissingGroup(CompareTestBase):
    """T-U11-2：目录缺失/产物不可识别 → 结构化"数据缺失"，不崩。"""

    def test_missing_group_dir(self):
        missing = self.tmp / "does_not_exist"
        groups = [
            {"name": "baseline", "paths": [missing], "role": "baseline"},
            {"name": "plugin", "paths": [missing], "role": "plugin"},
        ]
        r = compare.compare(groups)
        for g in r["per_group"]:
            self.assertEqual(g["n_runs"], 0)
        self.assertEqual(r["per_group"][0]["tokens"]["total"]["median"], None)
        self.assertEqual(r["plans"]["A"], [])
        self.assertEqual(r["plans"]["B"], [])
        md = compare.render_markdown(r)
        self.assertIn("数据缺失", md)

    def test_unrecognizable_dir(self):
        d = self.tmp / "empty_dir"
        d.mkdir()
        r = compare.compare([{"name": "g", "paths": [d]}])
        self.assertEqual(r["per_group"][0]["n_runs"], 0)


class TestQualityRules(CompareTestBase):
    """T-U11-3：质量四规则正反例 + 无引源 N/A。"""

    def test_skeleton(self):
        good = "\n".join(_HEADINGS)
        self.assertEqual(compare.quality_score(good)["parts"]["skeleton"], 1.0)
        # 少 3 章 → 3/6
        partial = "\n".join(_HEADINGS[:3])
        self.assertEqual(compare.quality_score(partial)["parts"]["skeleton"], 0.5)
        # 空白不敏感：全骨架里前两章标题挤了空格也能命中
        weirds = [h.replace("、", " 、 ") for h in _HEADINGS[:2]] + _HEADINGS[2:]
        self.assertEqual(compare.quality_score("\n".join(weirds))["parts"]["skeleton"], 1.0)

    def test_draft_pollution(self):
        clean = "公司主营芯片设计，营收稳步增长。"
        self.assertEqual(compare.quality_score(clean)["parts"]["no_draft_pollution"], 1.0)
        dirty = "公司主营芯片设计。\n规划草稿：先写总体结论再写盘面。\n营收稳步增长。"
        q = compare.quality_score(dirty)
        self.assertEqual(q["parts"]["no_draft_pollution"], 0.0)
        self.assertIn("规划草稿", q["details"]["draft_hits"])
        # 步骤残留也要抓
        step = "1. 步骤：先取财务再取事件。"
        self.assertEqual(compare.quality_score(step)["parts"]["no_draft_pollution"], 0.0)

    def test_citation_accuracy(self):
        facts = [{"label": "毛利率", "value": "12.34"},
                 {"label": "ROE", "value": "8.5"}]
        all_present = "公司毛利率 12.34%，ROE 8.51%（容差内）。"
        q = compare.quality_score(all_present, citation_facts=facts)
        self.assertEqual(q["parts"]["citation_accuracy"], 1.0)
        # 只命中一个
        only_one = "公司毛利率 12.34%。"
        q = compare.quality_score(only_one, citation_facts=facts)
        self.assertEqual(q["parts"]["citation_accuracy"], 0.5)
        self.assertEqual(q["details"]["citation_miss"], ["ROE"])
        # 全不中
        none = "公司毛利率 0.5%。"
        self.assertEqual(compare.quality_score(none, citation_facts=facts)["parts"]["citation_accuracy"], 0.0)
        # 无引源 → N/A，不计入 available
        q = compare.quality_score("公司毛利率 12.34%。")
        self.assertIsNone(q["parts"]["citation_accuracy"])
        self.assertEqual(q["available"], 3)   # skeleton + pollution + disclaimer

    def test_disclaimer(self):
        # 正文加长到 >500 字符，确保免责句是否落在"末尾窗口"决定判定
        body = "公司主营芯片设计，营收连续三年增长。" * 40
        with_tail = body + "\n以上分析仅供参考，不构成投资建议。"
        self.assertEqual(compare.quality_score(with_tail)["parts"]["disclaimer"], 1.0)
        # 同一句挪到开头 → 不在尾窗内 → 0
        head = "以上分析仅供参考，不构成投资建议。\n" + body
        self.assertEqual(compare.quality_score(head)["parts"]["disclaimer"], 0.0)


class TestValueRatio(CompareTestBase):
    """T-U11-4：性价比 = 质量分 ÷ total_tokens。"""

    def test_value_arithmetic(self):
        report = "\n".join(_HEADINGS) + "\n毛利率 12.34%。\n免责声明\n"
        facts = [{"label": "毛利率", "value": "12.34"}]
        q = compare.quality_score(report, citation_facts=facts)
        # parts: skeleton 1.0, pollution 1.0, citation 1.0, disclaimer 1.0 → 1.0
        self.assertAlmostEqual(q["score"], 1.0)
        total = 4800
        self.assertAlmostEqual(q["score"] / total, 1.0 / 4800)
        # 直接用 compare 的 value 口径
        r = compare.compare([{"name": "g", "paths": [Path(self.tmp)]}])
        self.assertIsNotNone(r)  # 无产物组不崩（上测已覆盖）；这里只验算术

    def test_value_with_partial_quality(self):
        # 骨架只中 5/6、其余全 1.0、引源命中 → score=(5/6+1+1+1)/4=23/24（score 保留 6 位）
        report = "\n".join(_HEADINGS[1:]) + "\n毛利率 12.34%。\n免责声明\n"
        q = compare.quality_score(report, citation_facts=[{"label": "毛利率", "value": "12.34"}])
        self.assertEqual(q["parts"]["skeleton"], 5 / 6)
        self.assertAlmostEqual(q["score"], round(23 / 24, 6))
        total = 4800
        self.assertAlmostEqual(q["score"] / total, round(23 / 24, 6) / 4800)

    def test_value_undefined_without_tokens(self):
        # compare 对"无报告文本"的 run 不给质量分/性价比（N/A），不产出 0.0 假象
        d = write_trace_dir(self.tmp, "t", PLUGIN_TRACE)   # trace 无 report.md
        r = compare.compare([{"name": "g", "paths": [d]}])
        run = r["per_run"]["g"][0]
        self.assertEqual(run["report"], "")
        self.assertGreater(run["tokens"]["total"], 0)      # token 有记录
        self.assertIsNone(run["quality"])
        self.assertIsNone(run["value"])
        # 组聚合也不把 0.0 混进中位数（quality 中位数应为 None）
        self.assertIsNone(r["per_group"][0]["quality"]["median"])


class TestLayoutDetection(CompareTestBase):
    """T-U11-5：布局自动识别。"""

    def test_layouts(self):
        run_d = write_run_dir(self.tmp, "r")
        trace_d = write_trace_dir(self.tmp, "t", PLUGIN_TRACE)
        both = write_run_dir(self.tmp / "x", "r2")
        (both / "trace.jsonl").write_text("", encoding="utf-8")
        empty = self.tmp / "empty"
        empty.mkdir()
        self.assertEqual(compare.detect_layout(run_d), "run")
        self.assertEqual(compare.detect_layout(trace_d), "trace")
        self.assertEqual(compare.detect_layout(both), "both")
        self.assertEqual(compare.detect_layout(empty), "none")
        self.assertEqual(compare.detect_layout(self.tmp / "nope"), "none")


class TestPlanPrereqs(CompareTestBase):
    """T-U11-6：方案 A/B 前置校验——缺失给规格、就绪可重建。"""

    def test_plan_a_missing_gives_spec(self):
        d = write_trace_dir(self.tmp, "t", PLUGIN_TRACE)
        r = compare.replay_prereqs_plan_a(d)
        self.assertEqual(r["status"], "prereq_missing")
        self.assertTrue(r["missing"])
        self.assertEqual(r["spec"]["expected_event"], "view_before")

    def test_plan_a_ready_with_contexts_dir(self):
        d = self.tmp / "t2"
        (d / "contexts").mkdir(parents=True)
        (d / "contexts" / "round_1.json").write_text("{}", encoding="utf-8")
        r = compare.replay_prereqs_plan_a(d)
        self.assertEqual(r["status"], "ready")
        self.assertEqual(r["spec"]["ctx_files"], ["round_1.json"])

    def test_plan_a_ready_with_inline_payload(self):
        # 新装配层：view_before 内联 payload（小上下文直接入库）
        d = self.tmp / "t3"
        d.mkdir()
        (d / "trace.jsonl").write_text(json.dumps(
            {"type": "view_before", "payload": '["a"]', "tokens": 10},
            ensure_ascii=False) + "\n", encoding="utf-8")
        r = compare.replay_prereqs_plan_a(d)
        self.assertEqual(r["status"], "ready")
        self.assertEqual(r["spec"]["inline_count"], 1)

    def test_plan_a_ready_with_payload_ref(self):
        # 大数据外联：payload_ref 指向 trace_payloads/<id>.json
        d = self.tmp / "t4"
        d.mkdir()
        (d / "trace.jsonl").write_text(json.dumps(
            {"type": "view_before", "payload_ref": "pay_1", "tokens": 10},
            ensure_ascii=False) + "\n", encoding="utf-8")
        r = compare.replay_prereqs_plan_a(d)
        self.assertEqual(r["status"], "ready")
        self.assertEqual(r["spec"]["payload_refs"], ["pay_1"])

    def test_plan_b_missing(self):
        d = self.tmp / "empty_run"
        d.mkdir()
        r = compare.replay_prereqs_plan_b(d)
        self.assertEqual(r["status"], "prereq_missing")
        self.assertTrue(r["missing"])

    def test_plan_b_partial_prompt_only(self):
        d = write_run_dir(self.tmp, "base")
        # 仅 prompt.txt：按 gen_report.py 现实情况
        (d / "requests").mkdir(exist_ok=True)
        (d / "requests" / "prompt.txt").write_text("prompt", encoding="utf-8")
        r = compare.replay_prereqs_plan_b(d)
        self.assertEqual(r["status"], "partial")
        self.assertEqual(r["ctx_files"], ["prompt.txt"])

    def test_plan_b_ready_with_requests_json(self):
        d = write_run_dir(self.tmp, "base")
        (d / "requests").mkdir(exist_ok=True)
        (d / "requests" / "round_1.json").write_text("{}", encoding="utf-8")
        r = compare.replay_prereqs_plan_b(d)
        self.assertEqual(r["status"], "ready")


class TestCli(CompareTestBase):
    """T-U11-7：CLI 组装（--group name=dir[;dir] / --facts 校验）。"""

    def test_build_group(self):
        g = compare.build_group_from_arg("bl=dirA;dirB=dirC")
        self.assertEqual(g["name"], "bl")
        self.assertEqual(g["paths"], ["dirA", "dirB", "dirC"])

    def test_build_group_error(self):
        with self.assertRaises(SystemExit):
            compare.build_group_from_arg("no-equals-sign")

    def test_main_runs(self):
        base = write_run_dir(self.tmp, "base")
        out = self.tmp / "cli_out"
        rc = compare.main(["--group", f"baseline={base}",
                           "--role-baseline", "baseline",
                           "--out", str(out)])
        self.assertEqual(rc, 0)
        self.assertTrue((out / "compare_metrics.json").is_file())


if __name__ == "__main__":
    TMPROOT.mkdir(parents=True, exist_ok=True)
    unittest.main(verbosity=2)