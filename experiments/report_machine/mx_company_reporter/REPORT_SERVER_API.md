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

{"stocks": ["宁德时代", "淮北矿业"]}
```

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
| `stock_done` | `stock, index, total, file, path` | 该股报告生成成功, 已保存 |
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
- 报告文件头含生成时间与生成方式; 由前端负责复制到用户目录
  (`experiments/report_machine/user/{username}/{股票名}/`)。

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

## 9. 登录方式与登录态复用(storage)

- **每日第一次调用**会自动先登录主账号(事件 `login_started`), 这是正常流程。
- 登录优先**复用浏览器登录态**(免滑块):
  - 登录态文件: `~/.config/choice_storage.json`(playwright `storage_state` JSON, 由
    choice 页面真实浏览器登录后导出, chmod 600, 不进 git)。
  - 服务调用 `choice_get_api_key.py --storage <路径> --json`: 登录态有效 → 直接打开页面
    "查询 API Key"拿 Key(约 10~15 秒, 无滑块); 失效 → 自动回退完整登录(账号密码 + 滑块)。
  - **登录态失效时需要人工刷新**: 用真实浏览器登录
    https://choice.eastmoney.com/mcp/ → 退出时(或会话有效期内)用 playwright 导出
    storage_state 覆盖 `~/.config/choice_storage.json`。
- 备用凭据没有 storage(它是主账号的登录态), 走完整登录流程。

## 10. 注意事项

- 服务重启后内存中的任务会丢失(`/events` 返回 404), 前端应提示用户重新发起;
  当日已用过的凭据状态在文件中持久化, 不会重复消耗。
- 积分是稀缺资源: 单只股票生成约消耗若干积分, 请合理控制调用频率。
- 测试模式 `MX_REPORT_FAKE_EXHAUST=1` 启动时, 首次生成会伪造积分耗尽以演练换 key 流程,
  **生产环境不要设置**。
