# iwencai 研报搜索接口调研（report-search skill）

> 2026-08-07 调研。结论：SkillHub 的 `report-search` skill 本质是一个包装好的 HTTP 客户端，
> 底层就一个 POST 接口，可以直接用脚本调用，无需依赖 skill 运行时。

## 1. Skill 来源与安装位置

- 安装命令（SkillHub CLI，仅 CLI）：
  ```bash
  curl -s https://www.iwencai.com/skillhub/static/0.0.4/download_and_install.sh | bash
  ```
- 本机安装位置：
  - CLI: `~/.iwencai-skillhub/aime_skillhub_cli.py`，入口 `~/.local/bin/iwencai-skillhub-cli`
  - skill 本体: `~/stock_research_agent/skills/report-search/`（OpenClaw workspace 软链）
- SkillHub 下载地址模板（metadata.json）：
  `http://ms.10jqka.com.cn/gateway/market/api/v1/skills/square/download?name={slug}`

## 2. 接口契约（核心）

| 项 | 值 |
| --- | --- |
| URL | `POST https://openapi.iwencai.com/v1/comprehensive/search` |
| Auth | `Authorization: Bearer <IWENCAI_API_KEY>`（环境变量，SkillHub 页面领取） |
| Body | `{"query": "...", "channels": ["report"], "app_id": "AIME_SKILL", "size": 10}` |
| 头 | `X-Claw-Skill-Id: report-search`、`X-Claw-Skill-Version: 1.0.0`、`X-Claw-Trace-Id: <64位hex>`（每次请求新生成）等 |

curl 直调示例：

```bash
TRACE_ID="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
curl -X POST "https://openapi.iwencai.com/v1/comprehensive/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${IWENCAI_API_KEY}" \
  -H "X-Claw-Call-Type: normal" \
  -H "X-Claw-Skill-Id: report-search" \
  -H "X-Claw-Skill-Version: 1.0.0" \
  -H "X-Claw-Plugin-Id: none" \
  -H "X-Claw-Plugin-Version: none" \
  -H "X-Claw-Trace-Id: ${TRACE_ID}" \
  -d '{"query":"贵州茅台 研报","channels":["report"],"app_id":"AIME_SKILL","size":10}'
```

## 3. 本机脚本

```bash
python search_report.py "贵州茅台 研报" --size 5          # 原始响应打 stdout
python search_report.py "贵州茅台 研报" --size 5 --output raw.json   # 写文件
```

- 纯标准库（urllib），conda stock_agent 环境可直接跑，无额外依赖
- API key 读取：优先 `IWENCAI_API_KEY` 环境变量；未设置时自动从 `~/.bashrc` 提取
  （注意：bashrc 第 19-23 行有"非交互 shell 直接 return"保护，`source ~/.bashrc` 在脚本里无效，
  key 实际是写死在文件里的，本脚本直接解析文件）

## 4. 详情接口（研报正文 + PDF 路径）—— 本机实测发现

搜索接口返回的是**段落片段**，完整正文和 PDF 信息通过第二个接口拿：

| 项 | 值 |
| --- | --- |
| URL | `POST https://ms.10jqka.com.cn/gateway/unified-wap/v1/information/notice-detail` |
| Content-Type | `application/x-www-form-urlencoded` |
| Body | `type=report&duid=<uid>&query_source=guide&query=*:*`（uid 取搜索结果的 `uid`） |
| Referer | 需带研报页 referer |

返回 `data.wordData` 关键字段：

| 字段 | 说明 |
| --- | --- |
| `content` | 研报完整正文（全文） |
| `path` | PDF 文件相对路径，如 `download_tmp/cde23b4b9e9c313d.pdf` |
| `ext` | `pdf`（确认研报格式为 PDF） |
| `organize` / `researcher` | 机构 / 作者 |
| `pubtime` | 发布日期（YYYY-MM-DD） |

PDF 直链拼接：`https://ms.10jqka.com.cn/<path>`。
⚠️ 实测坑：该路径 HEAD/GET 均返回 `200 application/pdf` 但 **body 为空**（2026-05 的旧研报，download_tmp 为临时目录，文件已被清理）。推测新发布研报立即下载可行，旧研报只能通过 url 页面阅读文本。

## 5. 搜索行为实测（2026-08-07，query="广生堂 研报"）

- **每次调用固定只返回 3 个片段**（size=3/10/50/100 结果一样），最多覆盖 2 篇研报
- `total` 是命中片段总数（60），但**无法翻页**：offset/page/start/from/page_num 等参数全部被忽略（实测 6 种写法均无效）
- 同一 uid 多条记录 = 同一篇研报的不同段落（para_index 区分），去重按 uid
- **时间过滤**：query 加自然语言时间词有效，如 `"广生堂 研报 2026"` 把 total 从 60 降到 8
- 官方 skill 对"结果不够"的解法就是换 query 多次调用（SKILL.md Workflow 第 4 步），没有分页机制

## 6. 实际验证（2026-08-07）

`"贵州茅台 研报" size=3` 调用成功：`{"status_msg":"OK","status_code":0,"data":[...]}`

返回 `data[]` 每条记录关键字段：

| 字段 | 说明 | 示例 |
| --- | --- | --- |
| `title` | 研报标题 | 贵州茅台（600519）：促进供需适配… |
| `summary` | 摘要 | 观点聚焦…（中金公司全文摘要） |
| `url` | 研报页面链接 | `https://ms.10jqka.com.cn/businesspage-outer/research-report/index.html?duid=...` |
| `publish_time` / `publish_date` | 发布时间（epoch 秒 / 文本） | `1748102400` / `2025-05-25 00:00:00` |
| `extra.organization` | 机构 | 中金公司 |
| `extra.author` | 作者 | 王文丹 |
| `extra.rating` | 评级 | 跑赢行业 |
| `extra.cat_names` | 研报分类 | ["个股评级","公司深度研究"] |
| `extra.industries` | 行业代码 | ["S340501"] |
| `stock_infos` | 关联股票 | [{"name":"贵州茅台","code":"600519"}] |
| `source_original` | 研报原文全文 | 含报头/正文 |
| `score` | 相关度分数 | 192.15 |
| `index` | 检索索引 | iwc_index_report_v5_vector |
| `data_source` | 数据源 | REPORT_BLOCK_VECTOR |

## 7. 本目录脚本与产物

| 文件 | 说明 |
| --- | --- |
| `search_report.py` | 搜索接口直接调用（纯标准库，key 自动从 bashrc 提取） |
| `transform_reports.py` | 原始响应 → 结构化研报列表：按 uid 去重合并段落、调详情接口补全文+PDF、输出 `reports_list.json`/`reports_list.csv`。用法：`python transform_reports.py <raw响应.json>` |
| `probe_pagination.py` | 分页参数探查脚本（结论：全部无效） |
| `probe_pdf_domains.py` | PDF 域名探查脚本（结论：仅 ms.10jqka.com.cn 可用） |
| `raw_guangshengtang.json` 等 | 广生堂各 query 原始响应存档 |
| `report_detail.json` | notice-detail 详情接口样例响应 |
| `reports_list.json` / `.csv` | 结构化研报列表（含全文/正文 url/pdf_url） |

## 8. 坑位

- 401 `{"status":401,"error":{"message":"no auth","code":"not_found_apikey"}}` =
  key 没传对/为空。注意 bashrc 非交互 return 陷阱（见第 3 节）。
- 响应体必须原样透传，不要过滤字段（skill 契约要求；解析逻辑应在拿到原始体之后做）。
- `query` 用自然语言即可，建议带"研报"或公司名；一个 query 一条记录，多公司分多次调用。
- 单次调用最多 3 片段（约 2 篇研报），要覆盖某公司半年研报需多个 query 变体（加年份/机构/评级词），无翻页。
- PDF 直链对旧研报返回 200 但空 body（临时目录已清理），正文以 notice-detail 的 `content` 字段为准。
- 数据来源应标注：同花顺问财。
