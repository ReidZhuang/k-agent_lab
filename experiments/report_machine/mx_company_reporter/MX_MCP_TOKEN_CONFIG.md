# MX MCP Token 配置说明

本文档说明 mx-ds-mcp（东方财富数据 MCP 服务）的 API Token 在 OpenClaw 中的配置位置与修改方法。

> 换 key 全流程（手动/自动/备用凭据轮换）、多 agent 共享机制、双服务并发安全见
> [`MX_MCP_KEY_LIFECYCLE.md`](./MX_MCP_KEY_LIFECYCLE.md)。

## 配置位置

| 项目 | 值 |
|---|---|
| 配置文件 | `/home/stockagent/.openclaw/openclaw.json` |
| JSON 路径 | `mcp.servers.mx-ds-mcp.headers.em_api_key` |
| 配置形式 | 明文写入 headers（当前未启用 SecretRef 加密管理） |

## 配置结构

```json
{
  "mcp": {
    "servers": {
      "mx-ds-mcp": {
        "url": "https://mxapi.eastmoney.com/mxds/mcp",
        "transport": "streamable-http",
        "connectTimeout": 10,
        "timeout": 120,
        "headers": {
          "em_api_key": "<你的东方财富 MCP API Key>"
        }
      }
    }
  }
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `url` | MCP 服务地址（东方财富 mxds 网关） |
| `transport` | 传输协议，`streamable-http` |
| `connectTimeout` / `timeout` | 连接/请求超时（秒） |
| `headers.em_api_key` | **MCP API Token**，每次请求通过 header 携带 |

## 修改方法

1. 编辑 `/home/stockagent/.openclaw/openclaw.json`，替换 `em_api_key` 的值
2. 重启 Gateway 使配置生效：

```bash
systemctl --user restart openclaw-gateway
```

3. 验证（返回 agent 列表即正常）：

```bash
curl -sS http://127.0.0.1:18789/v1/models -H "Authorization: Bearer <gateway.auth.token>"
```

## ⚠️ 与另一个 Token 的区别

本机存在**两个独立 Token**，不要混淆：

| Token | 位置 | 用途 |
|---|---|---|
| `em_api_key` | `mcp.servers.mx-ds-mcp.headers.em_api_key` | 调用东方财富 MCP 数据服务（行情/财务/公告等） |
| `gateway.auth.token` | `gateway.auth.token` | 调用本机 OpenClaw Gateway（HTTP API / WS RPC） |

`mx_company_reporter` 报告 API（`company_report_api.py`）**只依赖 `gateway.auth.token`**，不直接使用 `em_api_key`——数据查询由 mx-agent 内部通过 MCP 完成。

## 安全建议

- 当前为明文写盘，仅适合本地单机场景
- 如需增强安全，可改用 OpenClaw SecretRef 机制或环境变量注入（`OPENCLAW_*` 系列），避免明文落盘
- 不要把 `em_api_key` 提交到任何代码仓库或分享给他人
