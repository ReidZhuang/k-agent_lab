#!/usr/bin/env python3
"""
mx-public guardian: 新前端 agent 的生命周期守护脚本
职责（全部由 policy.json 驱动）：
  status          - 显示当前 token 用量与开关状态
  apply           - 把 policy.json 应用到 openclaw.json（agent 注册 + compaction 配置）
  monitor         - 统计 token 用量，超限自动禁用（model -> disabled/disabled）
  unlock          - 管理员解封（恢复 model）
  archive         - 归档清理旧会话 transcript（保留 keepArchivedDays）
  flush-memory    - 触发记忆冲刷（agent 蒸馏当天对话到 memory/YYYY-MM-DD.md）
用法：
  python3 guardian.py <command>
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

BASE = os.path.expanduser("~/.openclaw")
# policy.json 主副本已迁移至项目目录（report_chat/mx-public），运行时数据仍在 ~/.openclaw 下
POLICY_PATH = os.path.expanduser("~/project_space/research/experiments/report_machine/report_chat/mx-public/policy.json")
SESSIONS_DIR = os.path.join(BASE, "agents/mx-public/sessions")
MEMORY_DIR = os.path.join(BASE, "workspace-mx-public/memory")
CONFIG_PATH = os.path.join(BASE, "openclaw.json")

def load_policy():
    with open(POLICY_PATH) as f:
        return json.load(f)

def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ---------- token 统计 ----------
def scan_tokens():
    """扫描 mx-public sessions 目录所有 transcript，累加 usage.totalTokens 与 cost"""
    total_tokens = 0
    total_cost = 0.0
    files_scanned = 0
    if not os.path.isdir(SESSIONS_DIR):
        return 0, 0.0, 0
    for fn in os.listdir(SESSIONS_DIR):
        if not fn.endswith(".jsonl") or ".reset." in fn or ".trajectory" in fn:
            continue
        fp = os.path.join(SESSIONS_DIR, fn)
        try:
            with open(fp) as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(rec, dict) and rec.get("type") == "message":
                        m = rec.get("message", {})
                        if m.get("role") == "assistant" and m.get("usage"):
                            u = m["usage"]
                            total_tokens += int(u.get("totalTokens", 0) or 0)
                            cost = u.get("cost", {})
                            total_cost += float(cost.get("total", 0) or 0)
            files_scanned += 1
        except Exception as e:
            print(f"[warn] 读取 {fn} 失败: {e}", file=sys.stderr)
    return total_tokens, total_cost, files_scanned

# ---------- agent 注册 / 配置 ----------
def apply_config():
    policy = load_policy()
    agent = policy["agent"]
    compaction = policy["compaction"]

    # 读取当前配置
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)

    agents = cfg.setdefault("agents", {})
    defaults = agents.setdefault("defaults", {})
    a_list = agents.setdefault("list", [])

    # 1. compaction 全局配置 —— 用官方 CLI 写入（apply_compaction_cli，见下方）
    #    历史教训（8/11、8/16 两次崩溃）：
    #    - 直接改 openclaw.json 的 compaction 块（含非法顶层 enabled 字段）被 gateway
    #      强校验拒绝（agents.defaults.compaction: Invalid input）→ startup_failed；
    #    - 即使格式正确，直接编辑文件也会被 gateway 重启时的内存配置覆盖（未同步）。
    #    正确姿势：openclaw config patch --stdin（CLI 写入，schema 校验 + 磁盘/内存同步），
    #    格式必须 schema 合法（顶层无 enabled，midTurnPrecheck/memoryFlush 为对象）。

    # 2. 注册 mx-public agent（若无）
    existing = [a for a in a_list if a.get("id") == agent["id"]]
    entry = {
        "id": agent["id"],
        "name": agent["name"],
        "workspace": agent["workspace"],
        "agentDir": agent["agentDir"],
        "model": agent["model"],
    }
    if existing:
        existing[0].update(entry)
    else:
        a_list.append(entry)

    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    # 3. compaction 全局配置 —— 用官方 CLI 写入（正确姿势）
    #    历史教训（8/11、8/16 两次事故）：直接改 openclaw.json 写 compaction 会因
    #    (a) 非法顶层 enabled 字段 或 (b) gateway 内存未同步被重启覆盖 而失败/崩溃。
    #    正确姿势：openclaw config patch --stdin（schema 校验 + 磁盘/内存同步），
    #    且格式必须为 schema 合法：顶层无 enabled，midTurnPrecheck/memoryFlush 为对象。
    try:
        apply_compaction_cli(compaction)
    except Exception as e:
        print(f"[warn] compaction 写入失败: {e}", file=sys.stderr)

    print(f"[{now_iso()}] apply 完成：agent={agent['id']} model={agent['model']}")
    print("  提示：agents.list 为 hot-reload；compaction 已通过 CLI 写入，需重启 gateway 生效。")
    return 0


def apply_compaction_cli(compaction: dict):
    """用 openclaw config patch --stdin 写入 compaction（schema 合法格式）。"""
    if not compaction:
        return
    # 转换为 schema 合法格式：顶层无 enabled；midTurnPrecheck/memoryFlush 为对象
    out = {}
    for k in ("reserveTokens", "keepRecentTokens", "maxActiveTranscriptBytes",
              "truncateAfterCompaction", "notifyUser"):
        if k in compaction:
            out[k] = compaction[k]
    if compaction.get("midTurnPrecheck"):
        out["midTurnPrecheck"] = {"enabled": True}
    if compaction.get("memoryFlush"):
        out["memoryFlush"] = {"enabled": True}
    patch = {"agents": {"defaults": {"compaction": out}}}
    cmd = ["openclaw", "config", "patch", "--stdin"]
    r = subprocess.run(cmd, input=json.dumps(patch), capture_output=True,
                       text=True, timeout=60, cwd=os.path.expanduser("~"))
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or "CLI patch failed")
    print(f"[ok] compaction CLI 写入: {r.stdout.strip()}")

# ---------- 用量监控 / 禁用 / 解封 ----------
def _set_model(model: str):
    policy = load_policy()
    agent_id = policy["agent"]["id"]
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    for a in cfg.setdefault("agents", {}).setdefault("list", []):
        if a.get("id") == agent_id:
            a["model"] = model
            break
    else:
        print(f"[error] agents.list 中找不到 {agent_id}，先执行 apply", file=sys.stderr)
        return 1
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"[{now_iso()}] 已设置 {agent_id} model = {model}")
    return 0

def monitor():
    policy = load_policy()
    budget = policy["tokenBudget"]
    if not budget.get("enabled"):
        print("tokenBudget 未启用，跳过")
        return 0
    limit = int(budget["maxTotalTokens"])
    tokens, cost, files = scan_tokens()
    print(f"[{now_iso()}] token 用量: {tokens:,} / {limit:,} (成本 ¥{cost:.2f}, {files} 个 transcript)")

    # 当前是否已禁用
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    for a in cfg.get("agents", {}).get("list", []):
        if a.get("id") == policy["agent"]["id"]:
            current_model = a.get("model")
            break
    disabled = current_model == budget.get("disabledModel")

    if tokens >= limit:
        if not disabled:
            print(f"⚠️ 超过上限 {limit:,} tokens → 强制禁用服务")
            return _set_model(budget["disabledModel"])
        else:
            print("已处于禁用状态（等待管理员解封）")
    else:
        print(f"用量正常（{limit - tokens:,} tokens 剩余）")
    return 0

def unlock():
    policy = load_policy()
    agent = policy["agent"]
    budget = policy["tokenBudget"]
    tokens, cost, files = scan_tokens()
    print(f"[{now_iso()}] 当前用量: {tokens:,} tokens / 上限 {budget['maxTotalTokens']:,}")
    if tokens >= int(budget["maxTotalTokens"]):
        print("⚠️ 用量仍超上限，解封后将在下次 monitor 再次被禁用。确认继续？(y/N)")
        if input().strip().lower() != "y":
            print("已取消")
            return 1
    return _set_model(agent["model"])

# ---------- 会话归档 ----------
def archive():
    policy = load_policy()
    sa = policy["sessionArchive"]
    if not sa.get("enabled"):
        print("sessionArchive 未启用，跳过")
        return 0
    keep_days = int(sa["keepArchivedDays"])
    cutoff = time.time() - keep_days * 86400
    removed = 0
    if os.path.isdir(SESSIONS_DIR):
        for fn in os.listdir(SESSIONS_DIR):
            if not fn.endswith(".jsonl"):
                continue
            fp = os.path.join(SESSIONS_DIR, fn)
            try:
                if os.path.getmtime(fp) < cutoff:
                    os.remove(fp)
                    removed += 1
            except Exception as e:
                print(f"[warn] 清理 {fn} 失败: {e}", file=sys.stderr)
    print(f"[{now_iso()}] 归档清理完成：删除 {removed} 个超过 {keep_days} 天的 transcript")
    return 0

# ---------- 记忆冲刷 ----------
def flush_memory(force_if_over=False):
    policy = load_policy()
    mf = policy["memoryFlush"]
    if not mf.get("enabled"):
        print("memoryFlush 未启用，跳过")
        return 0
    agent_id = policy["agent"]["id"]
    max_bytes = int(mf["maxMemoryFileBytes"])
    today = datetime.now().strftime("%Y-%m-%d")
    mem_file = os.path.join(MEMORY_DIR, f"{today}.md")
    size = os.path.getsize(mem_file) if os.path.exists(mem_file) else 0

    over = size > max_bytes
    if force_if_over and not over:
        # 高频守卫模式：未超限直接静默返回（NO_REPLY 语义）
        print("未超限，无需冲刷")
        return 0
    if over:
        print(f"⚠️ 当日记忆文件 {size:,} 字节 > 上限 {max_bytes:,} → 触发强制冲刷")
    else:
        print(f"当日记忆文件 {size:,} 字节（上限 {max_bytes:,}），定时冲刷")
        if os.path.exists(mem_file) and size == 0:
            print("记忆文件为空，跳过 agent 调用")
            return 0

    # 调用 agent 蒸馏：把当天对话要点写入 memory/YYYY-MM-DD.md（幂等，追加或重写）
    prompt = (
        f"请阅读你工作区 memory/ 目录中今天的对话记录与相关文件，"
        f"把当天的关键决策、数据结论、挂起事项蒸馏成结构化条目，"
        f"写入 memory/{today}.md（保持文件不超过 {max_bytes} 字节，精简为要）。"
        f"这是定时记忆冲刷任务，完成后回复 NO_REPLY。"
    )
    cmd = ["openclaw", "agent", "--agent", agent_id, "--prompt", prompt]
    print(f"[{now_iso()}] 触发 agent 记忆冲刷: {' '.join(cmd[:6])}...")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        print("agent 返回:", (r.stdout or r.stderr)[:300])
    except subprocess.TimeoutExpired:
        print("[warn] 记忆冲刷超时（600s），请手动检查", file=sys.stderr)
    return 0

def status():
    policy = load_policy()
    budget = policy["tokenBudget"]
    tokens, cost, files = scan_tokens()
    print(f"agent      : {policy['agent']['id']} (model={policy['agent']['model']})")
    print(f"workspace  : {policy['agent']['workspace']}")
    print(f"token 用量 : {tokens:,} / {budget['maxTotalTokens']:,} (成本 ¥{cost:.2f}, {files} transcripts)")
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    for a in cfg.get("agents", {}).get("list", []):
        if a.get("id") == policy["agent"]["id"]:
            print(f"当前 model : {a.get('model')}")
            if a.get("model") == budget.get("disabledModel"):
                print("状态       : 🔴 已禁用（需管理员 unlock 解封）")
            else:
                print("状态       : 🟢 服务中")
            break
    else:
        print("状态       : ⚠️ 未注册（先执行 apply）")
    print(f"归档策略   : interval={policy['sessionArchive'].get('intervalMinutes')}min, "
          f"archiveAfter={policy['sessionArchive'].get('archiveAfterMinutes')}min, "
          f"keep={policy['sessionArchive'].get('keepArchivedDays')}d")
    print(f"记忆冲刷   : cron={policy['memoryFlush'].get('scheduleCron')}, "
          f"max={policy['memoryFlush'].get('maxMemoryFileBytes')}B")
    return 0

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    extra = sys.argv[2:]
    handlers = {
        "status": status,
        "apply": apply_config,
        "monitor": monitor,
        "unlock": unlock,
        "archive": archive,
        "flush-memory": lambda: flush_memory(force_if_over="--force-if-over" in extra),
    }
    fn = handlers.get(cmd)
    if not fn:
        print(f"未知命令: {cmd}", file=sys.stderr)
        print(__doc__)
        return 1
    return fn()

if __name__ == "__main__":
    sys.exit(main())
