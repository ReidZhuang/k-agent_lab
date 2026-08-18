# reporter 切换 opencode GO 迁移参考(2026-08-18 已执行)

> 状态: **已切换**。2026-08-18 reporter 的 LLM 调用从 DeepSeek 官方 API 切到 opencode GO 订阅。
> 两套测试(隔离单测 + 端到端)均通过,运行正常。

---

## 1. 现状:直连 DeepSeek 的位置

整个 `office` 下只有 **一处** LLM 调用点:

| 项 | 位置 | 说明 |
|---|---|---|
| SDK | `office/reporter/agent.py:468` | `from openai import OpenAI`,`OpenAI(api_key, base_url, max_retries)` |
| 调用 | `office/reporter/agent.py:501` | `client.chat.completions.create(...)` |
| key | `office/reporter/agent.py:49` | `os.environ.get("DEEPSEEK_API_KEY")`,未设置即 `raise RuntimeError` |
| 配置 | `office/cfg/config.yaml` → `reporter.deepseek:` 块 | api_base / model / max_tokens / timeout / max_retries |
| key 注入 | `~/.bashrc:150` | `export DEEPSEEK_API_KEY=sk-aac4****`(脱敏),由调度进程 source bashrc 获得 |

reporter 用到的模型能力:
- `chat.completions.create` 普通对话
- **function calling**(`tools` + `tool_choice="auto"`,抓取文章正文)
- `max_tokens: 64000`(config.yaml 配置值,注意很大)

## 2. opencode GO 端点兼容性实测(2026-08-17,HTTP 全 200)

opencode GO 端点(base `https://opencode.ai/zen/go/v1`)提供 OpenAI 兼容 `/chat/completions`,
key 走环境变量 `OPENCODE_GO_API_KEY`(来源:`~/.config/systemd/user/oc-cc-proxy.service.d/env.conf`)。

| reporter 的用法 | 实测结果 |
|---|---|
| 普通 chat 完成 | ✅ 正常返回,`cost:"0"`(走订阅,不额外扣费) |
| function calling(`tools`) | ✅ 返回 `finish_reason:"tool_calls"`,工具名/参数结构正确 |
| `max_tokens: 64000` | ✅ 接受,返回 `finish_reason:"stop"` |

差异点: 响应里多一个 `message.reasoning` 字段(deepseek 内部思考)。OpenAI SDK 只读
`choices[].message` 的 content / tool_calls,该字段被忽略,不会报错。

## 3. 迁移步骤(总共 3 处,均为配置级,无代码重构)

### 3.1 改 `office/cfg/config.yaml` 的 `reporter.deepseek:` 块

```yaml
deepseek:
  model: deepseek-v4-flash          # 不变,两端模型一致
  api_base: https://opencode.ai/zen/go/v1   # ← 改这一行(原来是 https://api.deepseek.com)
  max_tokens: 64000                 # 已实测 opencode 接受,可不改
  timeout: 180                      # 不变
  connect_timeout: 10               # 不变
  max_retries: 2                    # 不变(429/5xx 语义两端一致)
```

### 3.2 key 注入(二选一)

- **A. 最小改动**: 把 opencode 的 key 写进 `~/.bashrc` 的 `DEEPSEEK_API_KEY`(把原值替换掉)。
  代码零改动,但语义名不副实(变量名还是 DEEPSEEK)。
- **B. 干净做法(推荐,唯一动代码的地方)**: 改 `agent.py:49` 为双键兜底:

  ```python
  API_KEY = os.environ.get("OPENCODE_GO_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")
  ```

  然后在 bashrc 里改为 `export OPENCODE_GO_API_KEY=<新key>`,DEEPSEEK_API_KEY 可留作回滚兜底。

### 3.3 若 bashrc 被新会话继承时序问题

注意: 定时任务调度进程启动时读 bashrc。改完 bashrc 后需重启调度进程(newer 会话/daemon),
否则还是旧 env。

## 4. 风险与注意事项

- **协议/功能**: 无影响。OpenAI SDK 的 `chat.completions.create` 两端 API 一致;
  function calling、max_tokens、timeout、max_retries 全原样可用,agent loop 逻辑不动。
- **代码改动量**: 最小方案第 0 行,推荐方案 1 行(agent.py:49)。
- **报表质量**: 两端同模型 `deepseek-v4-flash`,但经过 opencode 网关,如观察
  finish_reason / content 结构异常,回滚 api_base 即可。
- **回滚**: 改回 `api_base: https://api.deepseek.com` + bashrc 还原,即完全恢复。

## 5. 相关文件

- 调用方: `office/reporter/agent.py`
- 配置: `office/cfg/config.yaml`
- key 注入: `~/.bashrc`
- 验证脚本(实测用,临时): `$CLAUDE_JOB_DIR/tmp/test_opencode_chat.sh` /
  `test_opencode_tools.sh` / `test_opencode_maxtokens.sh`(从 systemd drop-in 读 key,不落明文)

## 6. 变更记录

- 2026-08-17: 调查完成,3 项兼容性实测通过;当前不切换,文档留存供未来参考。
- 2026-08-18: **正式切换**。改动:
  - `office/cfg/config.yaml`: `reporter.deepseek.api_base` → `https://opencode.ai/zen/go/v1`
  - `office/reporter/agent.py:49`: 双键兜底 `OPENCODE_GO_API_KEY or DEEPSEEK_API_KEY`
  - `~/.bashrc`: 新增 `export OPENCODE_GO_API_KEY="..."`(DEEPSEEK_API_KEY 保留作回滚)
  - 测试: ① 隔离单测(TEST A 普通对话 rounds=1 + TEST B 带 tool call rounds=2,worktree 副本直调 agent.run);② 端到端(临时 commander 配置只跑 zqt 3 只股票: 茅台/平安/五粮液,全链路 reporter→writer→分发 3/3 成功)。测试后 zqt 股票池已清空恢复原状。
  - 备份: `office/backup_opencode_migration_20260818/`(agent.py.bak + config.yaml.bak)
  - 回滚: 还原 config.yaml 的 api_base + agent.py 单键 + bashrc,重启 reporter 即可完全恢复。
  - 注意: bashrc 第 22 行 `*) return;;` 使非交互 source 不生效;长驻 reporter 进程已带 key 运行,
    健康检测通过即不重启。cron 极端重启场景下 key 注入是既有架构限制(与切换前一致)。