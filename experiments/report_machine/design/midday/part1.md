1. 上午涨跌幅
目标：计算截至上午收盘（11:30）的个股涨跌百分比。
主要来源：

API 类型：腾讯财经（REST API，近实时，延迟 3-5 秒）

接口地址：https://web.sqt.gtimg.cn/q={code}

涉及字段：price（当前价，索引3），prev_close（昨收，索引4）

调用时间：11:30:00

加工公式：(price - prev_close) / prev_close * 100


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




















