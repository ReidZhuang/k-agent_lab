# 巨潮调研记录爬取 — 实验

输入股票代码或名称 → 拉取巨潮"调研"页签(投资者关系活动记录)列表 → 下载 PDF → 提取正文。

## 用法

```bash
conda run -n stock_agent python fetch_diaoyan.py 002821          # 全部调研记录+正文
conda run -n stock_agent python fetch_diaoyan.py 凯莱英           # 按名称
conda run -n stock_agent python fetch_diaoyan.py 002821 --max 5   # 只取最新5条
conda run -n stock_agent python fetch_diaoyan.py 002821 --no-pdf  # 只要列表
conda run -n stock_agent python fetch_diaoyan.py 002821 --start 2026-01-01 --end 2026-06-30
```

## 输出

`office/output/juchao_diaoyan/<code>_<名称>/`:
- `list.json` — 调研列表(标题/日期/PDF链接/正文文件路径)
- `pdfs/` — 原始 PDF
- `texts/` — 提取正文 txt

## 关键技术点(2026-08 实测)

| 步骤 | 接口 | 说明 |
|---|---|---|
| orgId 解析 | `POST /new/information/topSearch/query` | `plate` 必须**留空**,带值返回空列表 |
| 调研列表 | `POST /new/hisAnnouncement/query` | 调研页签 = `tabName:"relation"`(不是 category 参数);`stock:"<code>,<orgId>"`;column 按代码段推断(sse/szse/bj) |
| PDF 直链 | `http://static.cninfo.com.cn/<adjunctUrl>` | 列表返回的 adjunctUrl 直接拼接 |
| 正文 | pypdf | 记录表为文本型 PDF,提取质量高 |

## 已知边界

- 调研页签(`tabName=relation`)即巨潮搜索页 `#dy` 页签,含调研记录表、演示资料、业绩说明会记录
- 请求间隔 0.3s,单线程,未做重试
- 北交所(column=bj)未实测,逻辑按代码段推断
- 演示类 PDF(ppt转pdf)提取可能不完整,正文以"调研记录表"类为准
