10. 上午新驱动 & 此前驱动因素
目标：挖掘上午股价异动的直接诱因。

数据/信息来源（按可靠性排序）：

财联社快讯（接口）：lk.news_telegraph_cls(category='important')

- 时间范围改成上一个交易日到当日的消息，一般调用的时间为11：30-11：35之间，所以是上一个交易日至今天11：30中盘之间的所有消息。
- 调用获得消息之后在其中搜索今日所有取数的股票，搜索其文本是否包含每一个股票中文名or股票代码（注意这个接口的代码格式是xxxxxx.sz或xxxxxx.sh），包含则把这一个消息对应这一支股票保存在其输出
）


热门板块原因（接口）：lk.get_sector_hot_plates() 的 up_reason 字段，直接给出板块上涨逻辑。
巨潮官方公告（接口）：ak.stock_zh_a_disclosure_report_cninfo(symbol='300750', start_date='T-1日', end_date='T日')，覆盖盘后公告。

财联社接口调用信息详见/home/stockagent/project_space/research/experiments/web_search_base/knowledge/levistock中的文档
akshare的接口文档在这/home/stockagent/project_space/research/experiments/web_search_base/knowledge/akshare

先测一下 菲利华 按照上面的接口都能返回什么，保存成md给我看看










api的输出内容需要包括两部分：
第一部分是今天A股市场的整体情况，

给这个脚本增加两个查数内容：
首先使用财联社的两个接口查今日日期的数据，下面是接口和返回范例:
  1. market_emotion_cls() — 财联社市场情绪 ✅
  范例
  - 市场热度: 20（低）
  - 成交额: 1.31 万亿（+401亿）
  - 上涨占比: 80% | 赚钱效应: 42%
  - 涨停梯队: 一板12只(晋级率7%) / 二板3只 / 高度板1只
  - 涨跌分布: 上涨1225 / 下跌4234 / 涨停16 / 跌停105

  2. market_emotion_kph() — 开盘红情绪 ✅
  范例
  - 涨停16 / 跌停105 / 上涨1239 / 下跌3891
  - 信号: 市场人气低迷
  - 涨跌幅分布：涨幅集中在 1%~4%，跌幅集中在 -1%~-10%

看一下输出是否是范例的格式，整理成范例格式，作为输出结果。
以上两条只查一次，在个股返回结果的最前面均返回这两条。
然后将这两条输出为输出字典的一项，key是'all'。即{'all'：输出文本}


第二部分是今天要查的个股（股票的列表由用户调用时提供）的信息，其取数逻辑均包含在/home/stockagent/project_space/research/experiments/report_machine/data_fetch/midday中的py脚本中，这一部分查询了个股的很多指标数据。用了很多数据接口，个股统一输入并查出结果。（这是一个 由总到分的工作流） -done


第三部分 
以下的返回内容也是只查一次，但在个股的结果只只挑选其中有用的条目

在/home/stockagent/project_space/research/experiments/report_machine/data_fetch/midday中新建一个fetch_midday_message.py的脚本做一下开发，开发形成的函数可以输入一个股票名称或代号的列表（多支股票），输出字典（方式与fetch_midday_data.py一样）： 
3. 今日快讯： -done
财联社快讯（接口）：lk.news_telegraph_cls(category='important')

- 时间范围：一般调用的时间为11：30-11：35之间，所以是上一个交易日至今天11：30中盘之间的所有消息。
- 调用获得消息之后在其中逐条（注意是按条目搜索，这里要确认快讯每一条之间是否有分隔）搜索今日所有取数的股票，搜索其文本是否包含每一个股票中文名or股票代码（注意这个接口的代码格式是xxxxxx.sz或xxxxxx.sh），包含则把这一条快讯对应这一支股票保存在其输出中；除了搜索股票名称和代码以外，使用关键词知识图谱路由（知识图谱在/home/stockagent/project_space/research/experiments/report_machine/knowledge_graph中，先读目录下的kg_development_guide.md文件再读py文件，没必要读results文件夹）股票代码获得股票的关键词，这里使用的关键词获取算法和匹配度计算算法即刚刚开发的知识图谱中配套的算法一模一样，并匹配快讯中的文字，计算匹配程度。原则上文章的匹配度大于0.3才放入输出的结果中，并且要在标题出标注匹配程度。（这是一个 由总到分的工作流）

4. 热门板块原因（接口）：lk.get_sector_hot_plates() 的 up_reason 字段，直接给出板块上涨逻辑。使用单日的日期获取结果。交易日11：30-11：35之间调用。在结果中用个股的关键词（注意：此处使用的关键词来自知识图谱个股的所有关键词，不分种类，所有关键词都去匹配且不计算匹配度。）去匹配返回的热门板块的板块名称，比如返回： -done
### 电力 (+3.98%)

**上涨原因**: 江苏电网最高用电负荷达1.5759亿千瓦，再度刷新历史纪录。这是江苏电网最高用电负荷自2016年首破1亿千瓦后，连续第十年站上“亿级台阶”。

- 立新能源 | 涨幅:+10.04% | 标签:[电力]
- 湖南发展 | 涨幅:+9.98% | 标签:[业绩,电力]
- 华银电力 | 涨幅:+10.07% | 标签:[电力]
- 乐山电力 | 涨幅:+9.99% | 标签:[电力]
- 桂冠电力 | 涨幅:+9.98% | 标签:[绿电]

### 煤炭 (+4.64%)

**上涨原因**: 数据显示，截至7月17日秦港动力煤价格升至821元/吨，环比上涨29元/吨。本周煤炭指数上涨2.79%。6月全国原煤产量同比骤降9.7%，创近十年最大降幅，晋陕蒙样本煤矿产量同比降幅也扩大至4.4%。

- 大有能源 | 涨幅:+10.00% | 标签:[煤炭]
- 郑州煤电 | 涨幅:+9.94% | 标签:[煤炭]
- 淮北矿业 | 涨幅:+10.00% | 标签:[煤炭]
- 兖矿能源 | 涨幅:+10.00% | 标签:[煤炭]
- 中煤能源 | 涨幅:+9.97% | 标签:[煤炭]
需要用个股去匹配“电力”、“煤炭”（确保你能精准的拿到板块的文字用于匹配），如果匹配到就直接将这个板块的内容放入对应个股的输出中。另外，还需要用个股名称去匹配每个板块的原文，如果匹配到，就将整个板块内容返回。这里我假设你会写一个循环，用每一个股票关键字去匹配每一个板块标题，匹配到就放入输出pass，匹配不到就再用股票名称匹配所有板块全文，匹配到哪一个或多个板块就放入输出。但是我这里考虑的是我们是否可以使用多进程来完成这个任务，多进程更高效，详见最末尾。（这是一个 由总到分的工作流）

5. 跌停监控 **接口**: `lk.stock_dt_pool_em()`只接受时间输入，默认当天。交易日11：30-11：35之间调用。输出跌停列表格式如下： -done
跌停列表:

| 股票名称 | 股票代码 | 板块 |
|:---------|:---------|:-----|
| 贵绳股份 | 600992 | 通用设备 |
| 得邦照明 | 603303 | 照明设备 |
| 小崧股份 | 002723 | 照明设备 |
| 肯特催化 | 603120 | 化学制品 |
| 贤丰控股 | 002141 | 元件 |
| 宿迁联盛 | 603065 | 化学制品 |
需要在其输出的文字中查询是否有我们关注的股票代码（注意搜代码的格式必须是xxxxxx，纯数字没有字幕）

6. 异动检测： -done
**接口**: `lk.stock_changes_em()`，不接受股票代码名字不接受时间，只返回当天盘内的异动情况，返回全量个股的异动，调用时需全量循环所有异动类型获得全量数据并去重，之后在其中用股票名称或代码筛选条目，个股可以在条目拉取完毕后多进程来池里取个股的异动条目然后排序组装，条目包含：
股票代码: 300395
股票名称: 菲利华
市场: 0
时间: 09:37:40
涨幅/价格: +3.85%, 78.26
异动类型: 火箭发射
组装好后将可以丰富的呈现其早市的走势。

7. 补充信息（昨日信息） --done
给这个取数功能增加一些内容
这些内容增加在一个补充信息的部分中，查每支普票的这些信息，然后输出查到的表的全量字段内容，如果某只股票查询没有内容的话留空就好。
以下数据来自tushare的接口，可在/home/stockagent/project_space/demand/final/api_intro/tushare_basic_data_description.md和/home/stockagent/project_space/demand/final/api_intro/tushare_advanced_data_description.md中找接口调用数据的说明。以下的每部分都展示接口名称和取数日期变量，取数的股票代码变量都是ts_code，取数日期都用上一个交易日日期。
昨日公告部分：
财务审计意见 ann_date
财务指标数据 ann_date
分红送股 ann_date
业绩快报 ann_date
业绩预告 ann_date
现金流量表 ann_date
资产负债表 ann_date
利润表 ann_date

昨日波动：
个股异常波动 trade_date
个股严重异常波动 trade_date
股东增减持 ann_date

注意把取出的数据的列名换成文档中的输出参数对应的中文名然后再输出给用户。查询时可多个股票一起查询得到结果。（这是一个 由总到分的工作流）


并行流程设计如下：
(1). 将所有可以一起调用的接口数据调用下来
(2). 剩下的任务只有每只股票单独调用数据的任何和在已经调用的数据或信息中pick个股自己需要的信息了，这时候开始多进程，每一只股票一个worker开始工作，调用自己需要的数据，在文本或数据中过滤自己需要的内容，每获得一点就组装一点，最后形成一个自己的完整输出，直接对接到agent去调用云端LLM发送请求。
(3). 如果这样设计，你需要去/home/stockagent/project_space/research/experiments/report_machine/data_fetch/midday中看一下代码，看看哪些是整体调用的哪些是独立调用的，其是否有必须固定的先后顺序，如果有怎么处理，是否允许我们这样的多进程设计。
接下来我还需要增加几个数据获取过程，都是逐个股的数据获取，可以单独在个股的worker中单独跑。跑完把结果加入输出中。
这就是这个api整体的设计，你看一下是否合理，给出一个最终的设计方案，需要结合目前开发的脚本和实际情况来做。
对于3. 今日快讯 和 4. 热门板块原因（接口）和5. 跌停监控 和 6. 异动检测 的工作流程我都标注了（这是一个 由总到分的工作流），其工作流都包括获取非细分的信息然后由个股的并发流程去分别采集信息中需要的内容，这个工作流包含了非并发和并发两个工作部分，我希望我能把这两个工作流程在开发设计时封装成可独立运作的工具，未来可以复用，但是由于包含了总分两步，我不知道这是否可行？可否设计封装时在输入上给worker流出入口，让总体的工作能进行，worker的工作也能进行？如果可以分离，那么这一部分的模块名称成为pool_fetch


独立的每只股票的信息收集过程（从下面这些信息中我希望为：
- 上午新驱动 & 此前驱动因素。目标：挖掘上午股价异动的直接诱因。
- 上午新增风险 & 公司基本面新增信息
- 上午盘面30 秒速览摘要
提供事实和分析语料）：
1. /home/stockagent/project_space/research/experiments/report_machine/Juchao_report_fetch使用其中的工具获取上市公司的公告，输入股票代码和日期，获得公告string用列表形式传出，单片最长输出3000字。工具的使用详见文档。时间筛选的范围是上一个交易日日期到当天日期。上一个交易日日期使用/home/stockagent/project_space/research/experiments/report_machine/design/midday脚本中的工具获得。 - done（已融入search engine）
2. 互动易问答  **接口**: `ak.stock_irm_cninfo(symbol='300395')` 这个接口不支持在接口输入筛选时间，只能选择个股，注意输入的股票代号格式。但是返回的结果中每一条问答都有一个更新时间，我们需要使用更新时间来筛选只取最近三天的文旦条目，然后判断其回答内容是否为None。如果没有值那么丢弃。如果有值，则处理保留该条目并整理内容成：
- 问题：
- 回答者：
- 回答内容：
- 提问时间：
- 更新时间：
并输出。
3. sinafin+web_bot_agent_v3, 上一个交易日 11：30 至 当日11：30 的公司资讯/公告列表，可展开为全文
4. baidufin+web_bot_agent_v3, 上一个交易日 11：30 至 当日11：30 的公司资讯列表，可展开为全文
5. thsfin+web_bot_agent_v3, 上一个交易日 11：30 至 当日11：30 的公司资讯/公告列表，可展开为全文
6. juchao+web_bot_agent_v3, 上一个交易日 11：30 至 当日11：30 的公司资讯/公告列表，可展开为全文
7. qnainfo+web_bot_agent_v3,上一个交易日至今日，可展开全文

注意：3-6的过程都靠已经封装好的服务/home/stockagent/project_space/research/experiments/search_engine和/home/stockagent/project_space/research/experiments/web_bot_agent/version_3.0，你可以阅读其中的intro文件夹的文档来获得服务的使用方法和调用参数。3-6返回的上市公司资讯列表都是文章的标题，带有id返回，输入给LLM后会在tool/skill中说明这些文章内容是可以展开的，如果需要可以返回文章id。然后将返回的文章id配session id送入服务端，就可以获得选中的文章全文。这里需要开发一个中间层，中间层获得股票代码或股票名称之后向v3发起请求，得到结果之后将json组装成可以输入LLM的文本送给文本组织层，由文本层组织内容发送给LLM。当LLM call on tool要求某些文章的全文时，agent loop拿到这个请求会调用中间层完成向服务端提取全文。具体来说是中间层得到需要的信息，包括调用LLM的id（这个用于反馈时让agent知道是哪个loop）、v3服务的session id和文章id，中间层组装json传入v3服务，服务反馈json后中间层解析成agent可以用的形式反馈回去。agent拿到后将内容打包再次发送给LLM等待结果。
所以现在考虑整体的构架是：
1. 要有一个文本组织层，简单的取数任务可以放在其中，它主要负责将取来的数据进行清理并组成一个有结构的文本，方便下一步与prompt组装输入LLM进行agent loop；
2. 要有一个中间层，其主要工作就是与复杂的（并非简单取数的）服务对接，比如返回json的文章列表且还可以进一步交互的数据/信息服务。它可以接受服务的反馈、解析整合内容格式，输出给文本组织层编译好的文本。也可以接受再次调用的请求，将简单的请求编译成可以输出服务的格式，并request获得反馈再送出去给发送方。
3. 要有一个agent，它包括prompt和loop。loop主要是为了让agent看一下资讯标题考虑是否需要正文。agent与LLM交互最后获得成型的报告。
4. 要有一个修饰层，报告结果最终经过修饰层的处理达到可以输出的格式。简介美观结构明细内容丰富，保存成doc格式。

我目前的设计思路就是这样，整体的架构还不是非常成型



巨潮官方公告（接口）：ak.stock_zh_a_disclosure_report_cninfo(symbol='300750', start_date='T-1日', end_date='T日')，覆盖盘后公告。
这个接口的结果会有一个url其中可能包含一个pdf你能取




完整度检查机制
fetch midday data
我需要设计一个在取数获得数据整理好了输出文本之后的检查数据获取完整度的机制，目前所有的部分如下：必须有的部分：1.全市场情绪（8条）；2. 股票涉及行业关键词；3. 【今日11:30收盘数据】；4.【上一个交易日日终】；5. 【上一个交易日日终融资融券】；6.【今日午间收盘资金流向（逐分钟统计）】；7.【上一个交易日日终资金细分（元）】；8.【今日午间收盘板块排名（同花顺概念和行业板块）】；9. 【技术面关键位置】 。其中1、2、3、4四个部分获取的数据结果不能为空，比如1中返回的数据结果部分全都为空，那么就需要触发预警，需要重新取数（如果一个部分中只有一个或两个数据字段为空的话那么不要紧）。重新取数连续可以触发三次，如果三次后还为空那就直接返回，但是返回的结果要包含一个warning。将这个warning设计在返回的dict中，key=warning，value也是一个字典key=股票代码value=warning内容 。warning内容包括：1. 关键数据部分整版为空触发（1、2、3、4只要有一个整版为空就触发）；2.非关键数据部分整版为空触发（5、6、7、8只要有一个整版为空就触发）。数据正常的情况下，warning输出为空，如果所有股票均无warning输出什么方便下游使用你考虑一下。这个warning设计你可以提出自己的意见，要求就是方便下游使用。下游使用一般就是为了记录异常。  

fetch midday message
包括：1.今日快讯； 2. 热门板块上涨原因； 3. 盘中异动监测； 
这三个均非关键数据部分。但是如果三个全为空的话，需要给一个warning



fetcher
在/home/stockagent/project_space/research/experiments/report_machine/office这里开发一个api名字叫做fetcher
1. 接收到输入的股票列表，使用/home/stockagent/project_space/research/experiments/report_machine/snowball_token更新pysnowball的token，详细使用方法看readme
2. 调用/home/stockagent/project_space/research/experiments/report_machine/data_fetch/midday/fetch_midday_data.py，获得结果，获取完整度检查的warning记录异常到database
3. 调用/home/stockagent/project_space/research/experiments/report_machine/data_fetch/midday/fetch_midday_message.py，获得结果，获取完整度检查的warning记录异常到database
4. 跑完以上两个脚本之后，将获得的结果放在一个池子里，成为fetch_pool（这个数据最好保存在内存里），返回一个fetch_pool的id，供下面的sub writer能顺利找到fetch_pool。这个fetch pool怎么确定其使用结束销毁是需要额外设计的，我还没想清楚，用超时销毁也可以，但是不是最好的方案。接下来将会有固定数目（即上面输入的股票列表的股票个数的worker数会来调用，如果用调用次数计数的话，数目到了就销毁的话，会不会有问题？销毁的设计需要你考虑一下，做一个不妨碍正常使用需求又能尽快节省资源的设计）




writer
在/home/stockagent/project_space/research/experiments/report_machine/office这里开发一个api，名字叫writer。他的功能是：
1. 接受到输入（股票列表），不管是股票名称还是股票代码。用/home/stockagent/project_space/research/experiments/report_machine/data_fetch/midday/name_to_code.py中的转换方式，比如：
conda run -n stock_agent python name_to_code.py 宁德时代
name：宁德时代  ts_code: 300750.SZ   symbol: 300750  tencent: sz300750  xueqiu: SZ300750
将所有输入的股票名称经过开发转化成一个字典，key对应所有输入股票的名字的列表，接下来用哪一个拿哪一个
2. 调用fetcher传入股票名称（name）的列表，fetcher取数结束之后会返回fetch_pool id。
3. 启动多进程开始工作，为每一支股票启动一个worker->sub writer，每一个worker带着自己的股票名称（name - 用于在fetch pool中通过字典的key匹配股票中文名称获得数据）和代号（symbol - 用于在调用engine+mail tower服务的时候传入股票代码）去获取信息，worker工作内容如下：
  1）在刚刚获取的fetch_pool id中（实际上是个字典）通过name取到sub writer的股票信息
  2) 调用sinafin+mail tower服务，请求发给middleman，发送股票代号symbol，取上一个交易日至今日的日期做筛选
  3）调用baidufin+mail tower服务，请求发给middleman，发送股票代号symbol，取上一个交易日至今日的日期做筛选
  4）调用thsfin+mail tower服务，请求发给middleman，发送股票代号symbol，取上一个交易日至今日的日期做筛选
  5）调用juchao+mail tower服务，请求发给middleman，发送股票代号symbol，取上一个交易日至今日的日期做筛选
  6）调用qnainfo+mail tower服务，请求发给middleman，发送股票代号symbol，取上过去5天的日期做筛选
5. 每一个sub writer发出的请求需要带一个worker id，sub writer在middleman请求的返回信息能否直接发送回给每个sub writer？如果不能那就发送给主进程writer放在一个池子里，sub writer每隔1秒钟过去找一遍。一个sub writer手头上都有一个checklist，当它发现checklist上所有的部分都已经收到之后，它就编辑所有获得的报文整合成一个固定格式的报告内容，发送给reporter。发送之后这一个sub writer即worker的生命周期就结束了。
你需要考虑一下：
- sub writer发送出请求给middleman之后获得的返回结果该怎么接收？我的设计是worker要一口气发出所有的5个请求给middelman而不是发一个等一个的结果，发送出请求之后马上进行1）中所说的拉取信息工作，拉取结束之后再去看middleman是否回复了。这个过程是否可以如我所愿实现，设计上应该怎么做？
- middleman发回的请求结果应发到哪儿？sub writer应该怎么接收这些结果？这个过程该怎么设计？
- checklist的结构包括：fetch pool 数据部分（检查不能为空，就表示齐全了），mail tower文章部分（包括sinafin, baidufin, thsfin, juchao, qnainfo的文章列表反馈结果，结果可能为空，但也会有一个反馈，只要有反馈就表示收到了这部分的结果，一共5部分都拿到就表示齐全了）


middleman
在/home/stockagent/project_space/research/experiments/report_machine/office这里开发一个api，名字叫middleman。他的功能是：
- 作为writer和mail tower之间的中间层，将sub writer的请求组装成调用engine+mail tower服务的报文调用服务，同时汇总并发的服务，对单位时间内调用超过阈值的服务次数进行控制，对调用后返回发生错误的请求进行重试。

收到 /search 响应
  │
  ├─ HTTP status ≠ 200
  │   ├─ 503 → detail 含 "服务繁忙"        → WORKER_BUSY，稍后重试
  │   ├─ 504 → detail 含 "搜索超时"        → ENGINE_TIMEOUT，服务压力大
  │   └─ 500 → detail 以 "搜索失败:" 开头  → ENGINE_ERROR，查看 detail 内容定位原因
  │
  └─ HTTP status = 200
      ├─ status = "list_ready"
      │   ├─ empty = true  + total = 0  → 正常空结果（当天无文章）
      │   └─ empty = false + total > 0  → 正常有文章列表
      │
      └─ status = "done"
          ├─ empty = true  + total = 0  → 正常空结果
          └─ empty = false + total > 0  → 正文已就绪，可直接取 body_avail 为 "有" 的文章
你按照每个返回类型来给出重试的策略
HTTP status不在 JSON body 里。它在 HTTP 协议层的 status line（第一行）上

middleman
  2) 调用sinafin+mail tower服务，取上一个交易日至今日的日期做筛选，调用的完整参数是
  # sinafin — 上一个交易日至今 （分钟级）
  curl -X POST http://localhost:8300/search \
    -H "Content-Type: application/json" \
    -d '{"query":"600031","engine":"sinafin","mode":"list","max_results":15,"start_date":"2026-07-24","end_date":"2026-07-24"}'
  3）调用baidufin+mail tower服务，取上一个交易日至今日的日期做筛选，调用的完整参数是
  # baidufin — 上一个交易日至今
  curl -X POST http://localhost:8300/search \
    -H "Content-Type: application/json" \
    -d '{"query":"600031","engine":"baidufin","mode":"list","max_results":20,"start_date":"2026-07-24","end_date":"2026-07-24"}'
  4）调用thsfin+mail tower服务，取上一个交易日至今日的日期做筛选，调用的完整参数是
    # thsfin — 上一个交易日至今
  curl -X POST http://localhost:8300/search \
    -H "Content-Type: application/json" \
    -d '{"query":"600031","engine":"thsfin","mode":"list","max_results":20,"start_date":"2026-07-24","end_date":"2026-07-24"}'
  5）调用juchao+mail tower服务，取上一个交易日至今日的日期做筛选，调用的完整参数是
  # juchao — 上一个交易日至今
  curl -X POST http://localhost:8300/search \
    -H "Content-Type: application/json" \
    -d '{"query":"600031","engine":"juchao","mode":"list","max_results":10,"start_date":"2026-07-24","end_date":"2026-07-24"}'
  6）调用qnainfo+mail tower服务，取上过去5天的日期做筛选，调用的完整参数是
  # qnainfo — 最近 5 天  （分钟级）
  curl -X POST http://localhost:8300/search \
    -H "Content-Type: application/json" \
    -d '{"query":"600031","engine":"qnainfo","mode":"list","max_results":20,"start_date":"2026-07-20","end_date":"2026-07-24"}'


































