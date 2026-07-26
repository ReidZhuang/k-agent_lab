午间收盘信息文档 - 数据来源与加工设计文档（第二版）
版本：v2.0
核心设计原则：给 LLM 喂“素材”，而非“答案”。每个指标不仅要提供最终值，还要提供可供分析推理的上下文（如板块内排名列表、前 N 日资金趋势等）。
数据源优先级：稳定性 > 实时性 > 丰富性。优先使用 Tushare 基础表（稳），其次是腾讯/新浪（快），最后是雪球/levistock（精）。

第一部分：量化数据指标层
1. 上午涨跌幅
目标：计算截至上午收盘（11:30）的个股涨跌百分比。

主要来源：

API 类型：腾讯财经（REST API，近实时，延迟 3-5 秒）

接口地址：https://web.sqt.gtimg.cn/q={code}

涉及字段：price（当前价，索引3），prev_close（昨收，索引4）

调用时间：11:30:00

加工公式：(price - prev_close) / prev_close * 100

次要来源：

API 类型：新浪财经（15 分钟延迟，备胎）

接口地址：http://hq.sinajs.cn/list={code}

涉及字段：price（字段3），prev_close（字段2）

补充来源：Tushare daily（仅用于盘后核对，不用于盘中报告）

2. 上午换手率
目标：获取截至上午收盘的换手率。

主要来源：

API 类型：腾讯财经

接口地址：https://web.sqt.gtimg.cn/q={code}

涉及字段：turnover_rate（换手率%，索引38）

调用时间：11:30:00

3. 昨日换手率（新增）
目标：提供前一交易日的全天换手率，作为今日活跃度的对比基准。

主要来源：

API 类型：Tushare daily_basic

接口函数：pro.daily_basic(ts_code='000001.SZ', trade_date='T-1日')

涉及字段：turnover_rate（换手率%）

调用时间：上午 8:30 后（Tushare 已更新昨日数据）

加工公式：直接取值，与“上午换手率”并列展示，LLM 可自行比较判断“今日上午放量/缩量”。

4. 上午振幅
目标：计算上午股价波动的幅度。

主要来源：

API 类型：腾讯财经

接口地址：https://web.sqt.gtimg.cn/q={code}

涉及字段：amplitude（振幅%，索引43）

调用时间：11:30:00

次要来源（若自行计算）：

API 类型：新浪财经

涉及字段：high（字段4），low（字段5），prev_close（字段2）

加工公式：(high - low) / prev_close * 100

5. 上午成交额
主要来源：

API 类型：腾讯财经

接口地址：https://web.sqt.gtimg.cn/q={code}

涉及字段：amount（成交额，索引37），单位 万元

调用时间：11:30:00

次要来源：新浪财经 amount（字段9），单位 元（需换算）

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
额外输出排名前 5 的股票（领涨股） 和排名后 5 的股票（领跌股），以及该股前后各 2 只股票的代码、名称、涨幅。
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

8. 融资融券（前一日 + 变化率）
目标：获取前一日融资余额、融券余额，并计算较前两日的变化率。

主要来源：

API 类型：Tushare margin_detail

接口函数：pro.margin_detail(trade_date='T-1日', ts_code='000001.SZ')

涉及字段：rzye（融资余额，元），rqye（融券余额，元）

加工信息：同时查询 T-2 日数据，计算 融资余额变化率 (T-1 - T-2)/T-2*100%，供 LLM 判断杠杆资金态度（持续加杠杆/减杠杆）。

调用时间：上午 8:30 后

盘中两融说明：无任何公开源提供盘中实时两融数据，报告中需注明“数据截止前一交易日”。

9. 资金博弈（盘中实时方向 + 昨日细分）
目标：提供 今日上午资金净流向（实时）和 昨日大/中/小单拆解（盘后）。

主要来源（盘中方向）：

API 类型：pysnowball capital_flow（需 Token，逐分钟）

接口函数：ball.capital_flow('SZ300750')

涉及字段：net_amount（每分钟净流入，元）

加工公式：累加 9:30-11:30 所有 net_amount，得到上午总净流入（万元）。

主要来源（昨日细分）：

API 类型：pysnowball capital_assort

接口函数：from pysnowball.capital import capital_assort; capital_assort('SZ300750')

涉及字段：buy_large / sell_large（大单），buy_medium / sell_medium（中单），buy_small / sell_small（小单）

单位：元

加工公式：大单净额 = buy_large - sell_large

次要来源（昨日盘后，校验补充）：

API 类型：Tushare moneyflow_dc（东方财富资金流向）

接口函数：pro.moneyflow_dc(ts_code='000001.SZ', trade_date='T-1日')

涉及字段：net_amount（主力净额），buy_lg_amount（大单净额），buy_elg_amount（超大单净额）

第二部分：资讯与逻辑分析层（驱动 / 风险 / 公告）
10. 上午新驱动 & 此前驱动因素
目标：挖掘上午股价异动的直接诱因。

数据/信息来源（按可靠性排序）：

财联社快讯（接口）：lk.news_telegraph_cls(category='important')，时间范围 T 日 9:00-11:30。
热门板块原因（接口）：lk.get_sector_hot_plates() 的 up_reason 字段，直接给出板块上涨逻辑。
巨潮官方公告（接口）：ak.stock_zh_a_disclosure_report_cninfo(symbol='300750', start_date='T-1日', end_date='T日')，覆盖盘后公告。
搜索源（爬虫）：DuckDuckGo + site，目标站按优先级排列：
site:eastmoney.com（关键词："{股票代码}" "快讯"）
site:10jqka.com.cn（关键词："{股票代码}" "异动"）
site:finance.sina.com.cn（关键词："{股票名称}" "突发"）
site:cls.cn（财联社）
site:xueqiu.com（雪球，可能有前瞻讨论）
site:cnstock.com（中国证券网，官媒）
时间窗口：T-3 至 T 11:30，通过相关性排序（标题/正文包含股票代码的优先）过滤噪音。
11. 上午新增风险 & 公司基本面新增信息
风险搜索关键词："{股票代码}" "利空" OR "减持" OR "风险" OR "监管" OR "问询"

基本面关键词："{股票代码}" "中标" OR "合同" OR "业绩" OR "订单" OR "增持"

时间窗口：T-1 15:00 至 T 11:30（覆盖盘后及午间）

主要来源（接口）：

异动检测：lk.stock_changes_em()（近实时异动列表）

跌停监控：lk.stock_dt_pool_em(date='T日')（板块大面积跌停风险）

互动易：ak.stock_irm_cninfo(symbol='300750')（近 3 日问答，若有最新回复）

搜索源：同上（风险类关键词）

第三部分：速览摘要（新增章节）
12. 30 秒速览摘要
目标：为时间紧迫的用户提供一句话核心判断。

生成逻辑（基于上述所有数据）：

text
**今天上午**：{{company_name}} {{涨跌}}X.X%，[跑赢/跑输]板块，[有/无]新驱动（如“受XX快讯刺激”），[有/无]风险信号（如“板块内出现跌停股”）。
资金面[净流入/净流出]X万元（较昨日[改善/恶化]），换手率[放大/缩小]。
关键位置：[突破/未突破/贴近] MA{{N}}，[站上/跌破] 布林中轨。
预期：若午后量能配合，有望挑战 MA10 压力位（X.XX元）；反之则可能回踩 MA20 支撑（X.XX元）。
由 LLM 生成，基于前面所有“素材”综合提炼。

第四部分：交易日过滤逻辑
来源：Tushare trade_cal（交易日历）

接口函数：pro.trade_cal(start_date='T-5', end_date='T')

用途：判断 T-1、T-2 是否为交易日。若非交易日（如周末、节假日），在计算“前一日”数据时自动向前回溯至最近一个交易日，确保数据可用性。

文档总结
指标/分析项	核心数据源	关键改动 / 亮点
涨跌幅/换手率/振幅/成交额	腾讯财经	近实时，换手率独家
昨日换手率（新增）	Tushare daily_basic	提供对比基准
板块对比 + 排名	Tushare ths_member + 腾讯批量接口	暴露前后股票列表，让 LLM 做深度分析
技术面 MA/布林带	新浪 K 线 + 腾讯价格	盘中实时计算，含“上方/下方/贴近”判断
融资融券	Tushare margin_detail	含变化率，明确标注“截止前一日”
资金博弈（盘中方向）	雪球 capital_flow	分钟级累加，判断上午净流向
资金博弈（昨日细分）	雪球 capital_assort + Tushare moneyflow_dc	大/中/小单 + 主力净额双保险
新驱动 / 风险 / 公告	levistock + akshare + 多源搜索	时间窗口 T-3 至 T，多源容错
交易日过滤	Tushare trade_cal	自动回溯非交易日