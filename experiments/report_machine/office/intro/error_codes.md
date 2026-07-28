# Office 系统错误代码

本页定义 Office 系统（fetcher/writer/middleman/reporter）专用的错误代码。
所有错误通过 `database.log_office_error()` 写入数据库 `error_log` 表。

## 错误代码列表

| 错误代码 | 级别 | 含义 | 触发场景 |
|:---------|:----:|:-----|:---------|
| `FETCH_SCRIPT_FAILED` | ERROR | 取数脚本执行异常 | `fetch_midday_data` 或 `fetch_midday_message` 抛出异常 |
| `FETCH_ALL_FAILED` | ERROR | 所有股票取数失败 | 两个 fetch 脚本均未返回任何数据 |
| `FETCH_PARTIAL_DATA` | WARNING | 部分股票取数失败 | 部分股票未获取到数据，其他正常 |
| `WRITER_SUB_WORKER_FAILED` | ERROR | Sub worker 执行失败 | 某支股票的 sub writer 整体异常 |
| `WRITER_REPORTER_TIMEOUT` | ERROR | Reporter 响应超时 | POST Reporter 30s×3 全部超时 |
| `MIDDLEMAN_ENGINE_TIMEOUT` | WARNING | Type B 某 engine 正文超时 | /article 在 middleman 侧超时返回空 |
| `MIDDLEMAN_ENGINE_ERROR` | WARNING | Type B 某 engine 返回 error | mail_tower 返回 error 状态 |
| `MIDDLEMAN_SEARCH_FAILED` | WARNING | Type A 引擎搜索失败 | 个别引擎搜索异常（不影响整个请求） |
| `REPORTER_LLM_ERROR` | ERROR | LLM API 调用异常 | DeepSeek API 返回错误或网络异常 |
| `REPORTER_LOOP_TIMEOUT` | WARNING | Agent loop 超 8 轮未完成 | 强制退出时记录 |
| `REPORTER_AGENT_ERROR` | ERROR | Agent 循环异常退出 | agent.run() 未预期的异常 |

## 字段填写规范

| 字段 | 填写规则 |
|:-----|:---------|
| `module` | 统一格式 `"office.{component}"`，如 `"office.writer"`、`"office.middleman"` |
| `function` | 具体的函数名 |
| `stock_name` | 涉及的股票名称（有则填） |
| `ts_code` | 涉及的股票代码（有则填） |
| `error_code` | 本页定义的错误代码 |
| `error_msg` | 错误信息，最长 1024 字符 |
| `detail` | 详细堆栈（自动填充） |
| `data_snapshot` | 上下文数据 JSON（可选） |

## 查询错误

```sql
-- 查看所有 office 未处理错误
SELECT id, timestamp, module, function, error_code, stock_name, error_msg
FROM error_log
WHERE service_name = 'office' AND resolved = 0
ORDER BY timestamp DESC;

-- 按组件统计错误数
SELECT module, level, COUNT(*) as cnt
FROM error_log
WHERE service_name = 'office'
GROUP BY module, level
ORDER BY cnt DESC;
```
