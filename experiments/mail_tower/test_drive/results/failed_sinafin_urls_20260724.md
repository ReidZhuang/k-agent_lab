# sinafin 提取失败的 7 篇文章 URL

来源: 2026-07-24 综合并发测试 v3（测试时间 ~13:58）
引擎: sinafin / 凯莱英(002821)
失败原因: `_fetch_single` 返回空响应（empty response）
单独测试结果: 7 个 URL 均能正常返回 200 + trafilatura 正文

| # | 标题 | URL |
|:-:|:-----|:----|
| 1 | 医药板块暴力反弹：两位"医药女神"左手减持，右手加仓 | https://cj.sina.cn/articles/view/1644114654/61ff32de020027c86 |
| 2 | 凯莱英：7月23日获融资买入1.01亿元 | https://finance.sina.com.cn/stock/aiassist/lr/2026-07-24/doc-iniiwenn4471165.shtml |
| 3 | 上银医疗健康混合季报解读 | https://finance.sina.com.cn/stock/aigc/fundfs/2026-07-23/doc-iniivihw4552446.shtml |
| 4 | 凯莱英(06821.HK)获南方基金增持10.97万股 | https://finance.sina.com.cn/stock/bxjj/2026-07-23/doc-iniiviic1985254.shtml |
| 5 | 南方基金增持凯莱英(06821) | https://finance.sina.com.cn/stock/hkstock/marketalerts/2026-07-23/doc-iniiuwtf5375908.shtml |
| 6 | 华源证券：维持药明康德"买入"评级 | https://finance.sina.com.cn/7x24/2026-07-23/doc-iniiunch4658447.shtml |
| 7 | 机构：订单饱满锁定2026~2027年增长 | https://finance.sina.com.cn/stock/relnews/hk/2026-07-22/doc-iniispne4742597.shtml |

## 单独测试结果（全部成功）

| URL | HTTP | 正文长度 | 耗时 |
|:----|:----:|:--------:|:----:|
| cj.sina.cn | 200 | 2565 chars | 0.6s |
| finance.sina.com.cn 融资买入 | 200 | 2962 chars | 0.4s |
| finance.sina.com.cn 季报 | 200 | 5514 chars | 0.1s |
| finance.sina.com.cn 增持 | 200 | 483 chars | 0.3s |
| finance.sina.com.cn 英文 | 200 | 395 chars | 0.3s |
| finance.sina.com.cn 7x24 | 200 | 317 chars | 0.2s |
| finance.sina.com.cn 机构 | 200 | 1266 chars | 0.2s |
