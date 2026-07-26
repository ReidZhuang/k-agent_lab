# test_drive 测试脚本使用说明

## 环境要求

```bash
# API 服务必须正在运行
conda run -n stock_agent uvicorn api:app --port 8300
```

## 脚本一览

### 1. test_baidufin_list.py — 百度股市通资讯测试

```bash
# 查广生堂 2026-07-21 全天资讯（最多 10 条）
python3 test_baidufin_list.py -q 300436 --start 2026-07-21 --end 2026-07-21

# 查凯莱英 3 天资讯，精确到分钟
python3 test_baidufin_list.py -q 002821 --start "2026-07-20 09:00" --end "2026-07-22 15:00" -n 20

# 查完后提取特定文章的正文
python3 test_baidufin_list.py -q 300436 --start 2026-07-21 --end 2026-07-21 -e a_01,a_02
```

输出 MD 包含：情绪(利好/中性/利空)、来源(证券之星等)、摘要。

---

### 2. test_ddg_list.py — DDG 通用搜索测试

```bash
# 基本搜索
python3 test_ddg_list.py -q "广生堂"

# 站内搜索 + 时间限制 + 日期过滤
python3 test_ddg_list.py -q "博瑞医药" -n 30 --site "news.10jqka.com.cn" --timelimit m --filter_days 7

# 提取指定 ID 的正文
python3 test_ddg_list.py -q "广生堂" -n 5 --timelimit m -e a_01,a_03
```

输出 MD 包含：字数(word_count)、来源域名、摘要。

> DDG 引擎自动处理 PDF 公告页面（如同花顺公告页）——Phase 1 跳过 PDF，后台异步提取（15s 超时）。列表返回时正常 HTML 正文立即可取；PDF 页 `/article` 首次返回 `processing`（后台加载中），稍后重试即可。
>
> **日期过滤**：`filter_days` 上下界包夹，超过今天日期的文章自动剔除，带 `HH:MM` 的日期精确到分钟。
>
> **会话生命周期**：每次搜索创建 session，最多调用 3 次（含搜索），第 3 次 `/article` 返回后自动关闭。`-e` 提取时 PDF 页若未加载完成返回 `processing`（不计入调用次数），重试即可。

---

### 3. test_sinafin_list.py — 新浪财经个股新闻测试

```bash
# 需要先启动 sinafin_artical_tool（端口 8000）
# 查宁德时代
python3 test_sinafin_list.py -q 宁德时代 -n 3 --start 2026-07-20

# 按股票代码查
python3 test_sinafin_list.py -q 300750 -n 3 --start 2026-07-20 --end 2026-07-21

# 手动提取正文（sinafin 需先 /extract）
python3 test_sinafin_list.py -q 300750 -n 3 --start 2026-07-20 -e a_01,a_03
```

> 注意：sinafin 列表 **不包含正文**，需通过 `-e` 提交 ID 后自动调 `/extract` 提取。

---

## 通用参数

| 参数 | 缩写 | 说明 |
|------|------|------|
| `--url` | `-u` | API 地址，默认 `http://localhost:8300` |
| `--extract` | `-e` | 需要正文的文章 ID，逗号分隔 |

## 输出目录

每次运行在 `results/` 下创建以 `查询内容_引擎_日期` 命名的文件夹：

```
results/
├── 300436_baidufin_2026-07-21/
│   ├── raw.json        # API 原始响应
│   ├── report.md       # 格式化报告
│   └── a_01_正文.md     # 提取的正文（-e 指定时）
├── 广生堂_ddg_2026-07-22/
│   ├── raw.json
│   ├── report.md
│   └── a_03_正文.md
└── 300750_sinafin_2026-07-20/
    ├── raw.json
    └── report.md
```

## 三个引擎的输出差异

| | baidufin | ddg | sinafin |
|--|----------|-----|---------|
| 情绪/来源 | ✅ 有 | ❌ | ❌ |
| 字数 | 后台提取后 | ✅ 搜索即得 | 手动 /extract 后 |
| 正文就绪时机 | 后台自动提取后 | 正常 HTML 立即可取 / PDF 页后台异步后 | 需 /extract |
| 时间精度 | 支持到分钟 | 仅 filter_days | 仅日期 |
| PDF 公告提取 | ✅ 自动回退 | ✅ 异步后台（15s 超时）| ❌ |
