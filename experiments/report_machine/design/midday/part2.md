6. 与板块表现对比 & 板块内排名（优化后） --etl
目标：判断个股跑赢/跑输板块，并提供板块内排名的完整上下文列表供 LLM 分析。

第一步：获取板块成分股名单

主要来源（稳）：Tushare ths_member（同花顺概念板块成分）

接口函数：pro.ths_member(ts_code='板块指数代码')

返回字段：con_code（成分股代码），con_name（名称）

补充信息：T-1 日数据在今日上午不会变化，调用稳定。

备选：levistock lk.sector_stocks_em(板块代码)

第二步：获取板块内所有成分股的上午涨幅

主要来源：腾讯财经批量接口

接口地址：https://web.sqt.gtimg.cn/q={code1},{code2},...（一次最多约 50 只，分批调）

涉及字段：price，prev_close

加工公式：计算每只成分股的 (price - prev_close)/prev_close*100

第三步：生成“素材列表”供 LLM 分析（关键改动）

加工逻辑：

将所有成分股按涨幅降序排序。
输出该股排名（如“第 15/220 位”）。
额外输出排名前 5 的股票（领涨股） 和排名后 5 的股票（领跌股），以及该股前后各 4 只股票的代码、名称、涨幅。板块内个股总数不足20只的话直接全量拉出。列出的内容需包括股票名称、股票代码、当日涨跌幅。
LLM 用途：LLM 可以据此判断“该股涨幅在板块内处于中上游，但跟风力度弱于龙头XX，且板块内出现明显的两极分化，后排已有X只股票翻绿”。

第四步：板块涨跌幅基准

主要来源：akshare 同花顺板块指数（ak.stock_board_concept_index_ths）或 Tushare ths_daily（T-1 日板块全天涨跌幅，用作补充背景）


7. 技术面关键位置（实时版，优化后）  --etl
目标：提供 MA5、MA10、布林带（中/上/下轨）的今日盘中估算值，并判断当前价相对均线的位置。

第一步：获取历史日线数据（用于计算均线）

主要来源：新浪 K 线接口（scale=240，datalen=30）

接口地址：/CN_MarketData.getKLineData?symbol={code}&scale=240&datalen=30

返回字段：day，close

过滤逻辑：取最近 20 个完整交易日的收盘价（排除今日，若今日日线已生成，则取昨日及之前的 20 条）

第二步：计算均线 & 布林带

加工公式（Python / pandas）：

python
closes = [float(k['close']) for k in kline_data[-20:]]  # 最近20个交易日收盘价
ma5 = sum(closes[-5:]) / 5
ma10 = sum(closes[-10:]) / 10
ma20 = sum(closes[-20:]) / 20  # 即布林中轨
std20 = np.std(closes[-20:])   # 标准差
boll_upper = ma20 + 2 * std20
boll_lower = ma20 - 2 * std20
第三步：获取当前价并判断位置

当前价来源：腾讯财经实时 price（11:30 调用）

判断逻辑：

计算 偏离度 = (price - maN) / maN * 100

若偏离度在 ±1% 内，描述为“贴近 MA{N}”

若 > +1%，描述为“位于上方 X.X%”

若 < -1%，描述为“位于下方 X.X%”

输出格式：

MA5（估算）：约 X.XX 元，当前价格 上方/下方/贴近 X.X%

MA10（估算）：约 X.XX 元

MA20（估算 / 布林中轨）：约 X.XX 元

关键支撑/压力参考：上方压力位 [MA10/前高]，下方支撑位 [MA20/前低]

