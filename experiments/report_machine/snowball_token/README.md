# snowball_token — 雪球 API Token 管理

## 概述

snowball_token 模块负责雪球（Xueqiu）API Token 的自动获取、刷新和管理。

**解决的问题**: 雪球使用阿里云 WAF 防护，普通 `requests` 请求会被拦截，无法通过代码登录获取 Token。本模块使用 Playwright 无头浏览器模拟真实用户登录，绕过 WAF 限制，自动提取 Cookie 中的 `xq_a_token` 和 `u`。

## 文件结构

```
snowball_token/
  refresh_token.py       Token 自动刷新脚本
  README.md              本文件
```

## 依赖

```bash
pip install pysnowball playwright
playwright install chromium
```

## 用法

### 检查并自动刷新 Token

```bash
conda run -n stock_agent python3 refresh_token.py
```

执行流程：
1. 读取 `data_fetch/midday/config/snowball_token.json` 中的现有 Token
2. 调用 `pysnowball.quotec()` 验证有效性
3. 有效 → 不需操作，直接退出
4. 无效/过期 → Playwright 无头浏览器登录 → 提取新 Token → 更新配置文件

### 强制刷新

```bash
conda run -n stock_agent python3 refresh_token.py --force
```

跳过 Token 有效性检查，直接重新登录获取新 Token。适用于首次配置或已知 Token 已过期。

### 仅验证

```bash
conda run -n stock_agent python3 refresh_token.py --verify
```

只检查当前 Token 是否有效，不尝试登录。返回码：0=有效，1=无效。

## Token 文件

**主文件（取数代码实际读取）：**
`data_fetch/midday/config/snowball_token.json`

```json
{
    "xq_a_token": "71dea811...",
    "u": "3755631005",
    "updated": "2026-07-25",
    "note": "雪球 API Token，Playwright 自动获取。过期特征: error_code: 400016"
}
```

**备份（知识库文档）：**
`web_search_base/knowledge/pysnowball/token.md`

## 集成机制

`fetch_midday_data.py` 中的 `_init_snowball()` 已集成自动刷新：

```
_init_snowball()
  ├─ 读取 snowball_token.json → Token 有效 → ball.set_token() → 返回
  └─ 文件缺失或内容为空
      └─ subprocess 调用 refresh_token.py --force
          ├─ 成功 → 重新读取 Token → ball.set_token()
          └─ 失败 → 打印提示，让用户手动处理
```

Token 过期时，`pysnowball` 返回 `error_code: 400016`。取数脚本在调用 `fetch_capital_flow()` 和 `fetch_capital_assort()` 时会先调用 `_init_snowball()` 确保 Token 就绪。

## 更新位置对照

| 字段 | 取值位置 |
|------|----------|
| `xq_a_token` | 浏览器 Cookie（xueqiu.com）→ `xq_a_token` |
| `u` | 浏览器 Cookie（xueqiu.com）→ `u` |
| 登录地址 | `https://xueqiu.com` |
| 凭证 | 用户名 `3755631005` / 密码 `zhuang321` |

## 过期特征

所有需要 Token 的接口返回以下错误时表示 Token 已过期：

```json
{"error_code": 400016, "error_description": "遇到错误，请刷新页面或者重新登录帐号后再试"}
```

无需 Token 的接口（`quotec` 行情、`pankou` 盘口）不受影响。

## 常见问题

### Q: Playwright 登录遇到验证码怎么办？
脚本会自动等待 15 秒，多数情况下验证码会在此期间自动通过。如果长时间卡住，可以手动在浏览器中完成验证，或在非交易时段运行（雪球的验证码策略在低峰期较宽松）。

### Q: 为什么不用 requests 直接登录？
雪球使用阿里云 WAF（Web Application Firewall）防护，普通 HTTP 客户端会被拦截，返回 403 或跳转到验证页面。Playwright 使用真实的 Chromium 浏览器引擎，具备完整的 JS 环境、Cookie 管理和指纹特征，可以绕过 WAF 检测。

### Q: 更新 Token 后需要重启服务吗？
不需要。`fetch_midday_data.py` 每次调用 `fetch_capital_flow()` 或 `fetch_capital_assort()` 时都会重新读取 `snowball_token.json`（通过 `_init_snowball()`），更新后立即生效，无需重启。
