# 公司分析报告生成服务 — 接口与使用文档

服务地址: `http://<host>:8323`(本机 `127.0.0.1:8323`)
服务文件: `experiments/report_machine/mx_company_reporter/report_server.py`

功能: 前端传入**一个或多个股票名称**, 后端**串行**调用 openclaw `mx-agent`
生成每只股票的上市公司深度分析报告, 保存为 Markdown, 并通过 **SSE 实时推送**
生成进度(每日首次登录 / 换 key / 每只股票的开始与完成 / 最终结果)。

---

## 1. 启动 / 停止服务

```bash
cd experiments/report_machine/mx_company_reporter
./report_server.sh start      # 启动(nohup, 日志 log/report_server.log)
./report_server.sh status     # 查看状态
./report_server.sh restart    # 重启
./report_server.sh stop       # 停止
```

依赖: conda env `stock_agent`(playwright + fastapi); openclaw-gateway 用户级
systemd 服务须在运行(`systemctl --user status openclaw-gateway`)。

## 2. 接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/reports` | 创建生成任务(股票列表, 串行), 返回 `task_id` |
| GET | `/api/reports/{task_id}/events` | **SSE** 实时进度流 |
| GET | `/api/reports/{task_id}/status` | 兜底状态查询(含最近 20 条事件) |
| GET | `/health` | 健康检查(含凭据可用性与当日状态) |

---

## 3. 创建任务

```
POST /api/reports
Content-Type: application/json

{"stocks": ["宁德时代", "淮北矿业"], "username": "zgx"}
```

参数说明:

| 字段 | 必填 | 说明 |
|---|---|---|
| `stocks` | 是 | 股票名称列表, 1~5 只, 串行生成 |
| `username` | 否 | 前端登录用户名。传入后每份报告生成成功会**自动复制**到
  `experiments/report_machine/user/{username}/{股票名}/`, 前端文件区直接可见;
  不传则只保存到服务端 `reports/` 目录 |

**成功(202)**:

```json
{"task_id": "a1b2c3d4e5f6", "status": "queued"}
```

**失败响应**:

| 状态码 | 场景 |
|---|---|
| 400 | 股票列表为空, 或超过 5 只 |
| 409 | 当日全部凭据积分已用尽("今日用户积分已用尽,请明日再试") |
| 503 | 凭据配置文件缺失/格式错误(见第 7 节) |

限制: 单次最多 **5 只**(串行生成, 每只约 1~10 分钟); 服务全局单队列,
同时只有一个任务在生成, 其余任务排队(通过 `task_queued` 事件的
`position` 字段可知道排在第几位)。

## 4. 订阅进度(SSE)

```
GET /api/reports/{task_id}/events
Accept: text/event-stream
```

事件格式(标准 SSE): `event: <type>\ndata: <json>\n\n`, data 为 JSON,
每个事件都含基础字段 `type` / `ts`(秒级时间戳) / `seq`(递增序号)。

### 事件类型表

| event | 附加字段 | 含义 |
|---|---|---|
| `task_queued` | `task_id, stocks, position` | 任务已入队, position 为队列位置 |
| `login_started` | `credential, reason` | 开始登录(reason: `daily_first`=每日首次 / `quota_switch`=换key) |
| `login_ok` | `credential, key_prefix` | 登录成功, 已取得新 API Key |
| `login_failed` | `credential, reason` | 登录失败(每日首次失败 → 任务整体失败) |
| `generating` | `stock, index, total` | 开始生成第 index+1 只股票 |
| `stock_done` | `stock, index, total, file, path, user_path` | 该股报告生成成功, 已保存;
  `user_path` 为复制到 `user/{username}/{股票名}/` 的路径(POST 传了 username 且复制成功时才有,
  用于前端文件区定位; 复制失败不阻塞任务, 报告仍在 `reports/`) |
| `stock_failed` | `stock, index, total, error` | 该股生成失败(超时/其他错误/积分用尽) |
| `quota_switching` | `from_credential, to_credential` | 检测到积分耗尽, 开始换备用凭据 |
| `retrying` | `stock, credential, attempt` | gateway 已恢复, 重试该股生成 |
| `all_quota_exhausted` | `used_credentials` | 全部凭据(主+备用)积分已用尽 |
| `task_done` | `task_id, files, failed, duration_s` | **任务终态**: files=成功报告路径列表, failed=[{stock,error}] |
| `task_failed` | `task_id, error` | 任务整体失败(如每日首次登录失败) |

**前端使用要点**:
- 收到 `task_done` 或 `task_failed` 后**必须** `EventSource.close()`, 流会自动结束;
  中途断开后重连会从头重放全部事件直到终态, 前端按 `seq` 去重即可。
- 连接空闲时服务端每 15s 发一次 `: ping` 心跳注释行(EventSource 自动忽略)。

### 前端示例(Vue3 + fetch + EventSource)

```js
// 1) 创建任务
const res = await fetch(`${BASE}/api/reports`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({stocks: ['宁德时代', '淮北矿业']}),
});
if (!res.ok) { /* 400/409/503, 见第 3 节; 409 = 今日积分已用尽 */ }
const {task_id} = await res.json();

// 2) 订阅进度
const es = new EventSource(`${BASE}/api/reports/${task_id}/events`);
const done = new Promise((resolve) => {
  es.addEventListener('task_done', (e) => {
    const data = JSON.parse(e.data);
    console.log('成功报告:', data.files, '失败:', data.failed);
    es.close();                 // 必须关闭
    resolve(data);
  });
  es.addEventListener('task_failed', (e) => {
    es.close(); resolve({error: JSON.parse(e.data).error});
  });
});
// 其他事件: login_started / generating / stock_done / stock_failed /
// quota_switching / retrying / all_quota_exhausted —— 用于进度文案展示
```

> 前端 `BASE` 建议直连 `http://<host>:8323`(不要走 8320 的 `/api` 代理,
> 代理 SSE 需要关闭 buffer, 会增加复杂度)。

## 5. 兜底状态查询

```
GET /api/reports/{task_id}/status
```

```json
{
  "task_id": "a1b2c3d4e5f6",
  "status": "running",             // queued | running | done | failed
  "stocks": ["宁德时代", "淮北矿业"],
  "files": ["/.../reports/20260814_宁德时代_公司分析报告.md"],
  "failed": [],
  "last_events": [ ...最近 20 条事件... ]
}
```

## 6. 报告输出

- 保存目录: `mx_company_reporter/reports/`
- 命名规则(与 office/output 一致, 日期在前):
  `20260814_宁德时代_公司分析报告.md`
- **同日重复生成直接覆盖同名文件**(不加 _v2/_v3; 单 worker 串行写入无并发竞争)
- 报告文件头含生成时间与生成方式。
- POST 传了 `username` 时, 服务端在每只股票生成成功后**自动复制**到
  `experiments/report_machine/user/{username}/{股票名}/`(事件 `stock_done` 的
  `user_path` 字段), 前端文件区按该用户名即可浏览; 复制失败只记 WARN 日志,
  不阻塞任务, 报告仍在 `reports/` 下。
- 文件区 md 文件可经前端 explorer 下载, 转换用 `md2docx.py`
  (微软雅黑正文、无封面, 与 demand/cases/md2docx.py 同源)。

## 7. 配置备用用户名密码(重要)

### 文件位置

`~/.config/choice_mcp_credentials.json`(即 `/home/stockagent/.config/choice_mcp_credentials.json`,
在用户家目录 `.config` 下, **不会进入 git**)。创建后权限为 `600`。

### 正确格式

每套凭据是一个 JSON 对象, 只含 `username`(东财账号手机号/邮箱)和 `password`
两个字段, 不要加其他字段:

```json
{
  "primary": {
    "username": "176xxxxxxxx",
    "password": "xxxxxxxxxx"
  },
  "backups": [
    {
      "username": "176xxxxxxxx",
      "password": "xxxxxxxxxx"
    },
    {
      "username": "176xxxxxxxx",
      "password": "xxxxxxxxxx"
    },
    {
      "username": "176xxxxxxxx",
      "password": "xxxxxxxxxx"
    },
    {
      "username": "176xxxxxxxx",
      "password": "xxxxxxxxxx"
    }
  ]
}
```

- `primary`: 主账号(每日第一次调用时**必定**用它登录, 每日积分恢复)
- `backups`: 备用账号数组, **按顺序**最多 4 套(备用1 → 备用2 → 备用3 → 备用4)。
  主账号积分耗尽时按数组顺序依次切换; 全部用尽后当天不再尝试。
- 当前可只有主账号(`"backups": []`), 此时主账号耗尽即返回
  "今日用户积分已用尽,报告无法生成,请明日再试"。

### 操作方法

1. 编辑文件:
   ```bash
   nano ~/.config/choice_mcp_credentials.json
   ```
2. 新增/轮换备用账号: 把新账号密码填进 `backups` 数组(保持 JSON 合法,
   注意逗号)。**改完无需重启服务**, 每次登录时实时读取。
3. 验证配置:
   ```bash
   cd experiments/report_machine/mx_company_reporter
   python credential_store.py          # 打印 凭据可用/凭据数/当前状态
   python choice_get_api_key.py --index 1 --json   # 实测备用1能否登录拿 Key
   ```

### 常见错误(会导致服务返回 503)

| 错误 | 说明 |
|---|---|
| 文件不存在 | 未创建配置, 服务拒绝创建任务 |
| JSON 尾逗号 / 花括号不配对 | 不是合法 JSON, 服务无法解析 |
| 字段名拼错(如 `user_name`) | 读取不到 username/password |
| 密码前后有空格 | 登录会失败(密码被视为含空格) |
| `backups` 不是数组 | 格式错误 |

## 8. 积分耗尽自动换 Key 机制

- 生成过程中 agent 若返回积分耗尽错误(错误码 `MX_QUOTA_EXHAUSTED`,
  官方文案"你的积分已用完~请前往 https://ai.eastmoney.com/skills 购买套餐补充积分"),
  服务会自动: 记录当前凭据已耗尽 → 用下一套备用凭据登录取得新 API Key →
  更新 openclaw.json 的 `mcp.servers.mx-ds-mcp.headers.em_api_key`(修改前自动备份
  `openclaw.json.bak.<旧key前8位>`)→ 重启 openclaw-gateway(仅 key 变化时)→
  验证 gateway 恢复 → **重试刚才失败的股票**(事件: `quota_switching` → `login_*` → `retrying`)。
- 主+备用全部用尽: 该任务及之后的任务直接返回
  "今日用户积分已用尽,报告无法生成,请明日再试", 次日自动恢复(每日首次登录重置)。
- 前端无需处理换 key 逻辑, 只需按事件更新文案(如"检测到积分不足,正在切换备用账号…")。

## 9. 登录方式: CDP 连接真实 Chrome(自动启动, 免人工)

- **每日第一次调用**会自动先登录主账号(事件 `login_started`), 这是正常流程。
- 登录走 **CDP 模式**(默认, 无需任何人工操作):
  - 脚本通过 `--cdp` 连接 `127.0.0.1:9222` 的 Chrome **远程调试端口**;
    端口不可达时**自动后台启动** Chrome(数据目录 `/tmp/chrome-cdp-test`,
    `CDP_CHROME_CMD` 环境变量可覆盖启动命令)并轮询等待就绪 —— 服务运行期间
    无需手动开浏览器。
  - 由于连接的是**真实 Chrome(指纹=真实用户)**, 点"开始验证"后滑块验证
    **自动放行**(0.5~2s), 不再需要人工拼图。
  - 登录态**跨次复用**: 数据目录保留了登录 cookies, 脚本用登录标记文件
    (`/tmp/chrome-cdp-test/mx_login_state.json`)确认当前登录态属于目标账号 →
    直接"查询 API Key"拿 Key(约 10~15 秒, 免账号密码)。标记与目标账号
    不匹配时先清 cookies 退出, 再完整登录目标账号, **保证不串号**。
  - 完整登录全程人类化(逐字符输入账号密码 + 随机停顿), 日志在 stderr。
- 手动触发登录可验证/排查(见第 7 节):
  ```bash
  python choice_get_api_key.py --index 0 --json   # 主账号(CDP, 自动起 Chrome)
  python choice_get_api_key.py --index 1 --json   # 备用1
  ```
- 旧方案 `--storage <storage_state>` 仍保留(仅兼容), 服务端默认不再使用。
  人工拼图方案(`--challenge-dir`)为实验性, 不再维护。

## 10. 注意事项

- 服务重启后内存中的任务会丢失(`/events` 返回 404), 前端应提示用户重新发起;
  当日已用过的凭据状态在文件中持久化, 不会重复消耗。
- 积分是稀缺资源: 单只股票生成约消耗若干积分, 请合理控制调用频率。
- 测试模式 `MX_REPORT_FAKE_EXHAUST=1` 启动时, 首次生成会伪造积分耗尽以演练换 key 流程,
  **生产环境不要设置**。
