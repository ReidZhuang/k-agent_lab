office的开发 —— report的形成的完整流程 
office是一个生成report系统，它由fetcher取数据并检查数据完整性，writer汇总数据和咨询组装完整的report context，reporter负责将上下文与LLM通过agent loop交互产出完美报告，middleman负责office成员与市场资讯服务之间的交互衔接。writer和reporter获取mail tower的资讯/公告服务通过middleman作为中间层提供方便。



fetcher
在/home/stockagent/project_space/research/experiments/report_machine/office这里开发一个api名字叫做fetcher
1. 接收到输入的股票列表，使用/home/stockagent/project_space/research/experiments/report_machine/snowball_token更新pysnowball的token，详细使用方法看readme
2. 调用/home/stockagent/project_space/research/experiments/report_machine/data_fetch/midday/fetch_midday_data.py，获得结果，获取完整度检查的warning记录异常到database
3. 调用/home/stockagent/project_space/research/experiments/report_machine/data_fetch/midday/fetch_midday_message.py，获得结果，获取完整度检查的warning记录异常到database
4. 跑完以上两个脚本之后，将获得的结果放在一个池子里，成为fetch_pool（这个数据最好保存在内存里），返回一个fetch_pool的id，供下面的sub writer能顺利找到fetch_pool。这个fetch pool怎么确定其使用结束销毁是需要额外设计的，我还没想清楚，用超时销毁也可以，但是不是最好的方案。接下来将会有固定数目（即上面输入的股票列表的股票个数的worker数会来调用，如果用调用次数计数的话，数目到了就销毁的话，会不会有问题？销毁的设计需要你考虑一下，做一个不妨碍正常使用需求又能尽快节省资源的设计）
5. 两个取数脚本的相关文档在这里/home/stockagent/project_space/research/experiments/report_machine/data_fetch/midday/intro/README.md

对于fetcher调用的两个脚本的输出的完整度检查机制
fetch midday data
我需要设计一个在取数获得数据整理好了输出文本之后的检查数据获取完整度的机制，目前所有的部分如下：必须有的部分：1.全市场情绪（8条）；2. 股票涉及行业关键词；3. 【今日11:30收盘数据】；4.【上一个交易日日终】；5. 【上一个交易日日终融资融券】；6.【今日午间收盘资金流向（逐分钟统计）】；7.【上一个交易日日终资金细分（元）】；8.【今日午间收盘板块排名（同花顺概念和行业板块）】；9. 【技术面关键位置】 。其中1、2、3、4四个部分获取的数据结果不能为空，比如1中返回的数据结果部分全都为空，那么就需要触发预警，需要重新取数（如果一个部分中只有一个或两个数据字段为空的话那么不要紧）。重新取数连续可以触发三次，如果三次后还为空那就直接返回，但是返回的结果要包含一个warning。将这个warning设计在返回的dict中，key=warning，value也是一个字典key=股票代码value=warning内容 。warning内容包括：1. 关键数据部分整版为空触发（1、2、3、4只要有一个整版为空就触发）；2.非关键数据部分整版为空触发（5、6、7、8只要有一个整版为空就触发）。数据正常的情况下，warning输出为空，如果所有股票均无warning输出什么方便下游使用你考虑一下。这个warning设计你可以提出自己的意见，要求就是方便下游使用。下游使用一般就是为了记录异常。  

fetch midday message
包括：1.今日快讯； 2. 热门板块上涨原因； 3. 盘中异动监测； 
这三个均非关键数据部分。但是如果三个全为空的话，需要给一个warning



writer
在/home/stockagent/project_space/research/experiments/report_machine/office这里开发一个api，名字叫writer。他的功能是：
1. 接受到输入（股票列表），不管是股票名称还是股票代码。用/home/stockagent/project_space/research/experiments/report_machine/data_fetch/midday/name_to_code.py中的转换方式，比如：
conda run -n stock_agent python name_to_code.py 宁德时代
name：宁德时代  ts_code: 300750.SZ   symbol: 300750  tencent: sz300750  xueqiu: SZ300750
将所有输入的股票名称经过开发转化成一个字典，key对应所有输入股票的名字的列表，接下来用哪一个拿哪一个
2. 调用fetcher传入股票名称（name）的列表，fetcher取数结束之后会返回fetch_pool id。
3. 启动多进程开始工作，为每一支股票启动一个worker->sub writer，每一个worker带着自己的股票名称（name - 用于在fetch pool中通过字典的key匹配股票中文名称获得数据）和代号（symbol - 用于在调用engine+mail tower服务的时候传入股票代码）去获取信息，worker工作内容如下：
  1）在刚刚获取的fetch_pool id中（实际上是个字典）通过name取到sub writer的股票信息
  2) 调用engine+mail tower服务，请求发给middleman，发送股票代号symbol，日期筛选和engine、mode等调用信息已经在middleman中配置好了，middleman按照配置的默认情况发请求。（默认调用五类engine：sinafin baidufin thsfin juchao qnainfo，除qnainfo调用过去5天的日期做筛选以外，其余engine取上一个交易日至今日的日期做筛选）
5. 每一个sub writer发出的请求需要带一个worker id，sub writer在middleman请求的返回信息能否直接发送回给每个sub writer？如果不能那就发送给主进程writer放在一个池子里，sub writer每隔1秒钟过去找一遍。一个sub writer手头上都有一个checklist，当它发现checklist上所有的部分都已经收到之后，它就编辑所有获得的报文整合成一个固定格式的报告内容，发送给reporter。发送之后这一个sub writer即worker的生命周期就结束了。
你需要考虑一下：
- sub writer发送出请求给middleman之后获得的返回结果该怎么接收？我的设计是worker请求给middelman，后由middleman并发5个请求然后等5个请求结果受到之后组装在一起发回给writer。发送出请求之后马上进行1）中所说的拉取信息工作，拉取结束之后再去看middleman是否回复了。这个过程是否可以如我所愿实现，设计上应该怎么做？
- middleman发回的请求结果应发到哪儿？sub writer应该怎么接收这些结果？这个过程该怎么设计？
- checklist的结构包括：fetch pool 数据部分（检查不能为空，就表示齐全了），mail tower文章部分（包括sinafin, baidufin, thsfin, juchao, qnainfo的文章列表反馈结果，结果可能为空，但也会有一个反馈，检查结果齐全这步由middleman完成，只要有反馈就表示收到了这部分的结果，这部分都拿到就表示齐全了）
- subwriter调用middleman服务的时候需要创建一个writer id发送请求，这样返回的内容就可以依靠writer id让sub writer能顺利拿到。这个writer id需要一个创建机制，让它不能出现重复，你考虑一下这个怎么实现，一定要保证不会出现重复。



middleman
在/home/stockagent/project_space/research/experiments/report_machine/office这里开发一个api，名字叫middleman。他的功能是：
- 作为writer和mail tower之间的中间层，将sub writer的请求组装成调用engine+mail tower服务的报文调用服务。sub writer发出一个股票代码请求，middleman按照配置发出5个engine的mail tower服务请求，并等待这5个请求的文章列表回复到手之后，将报文解析后组装成一个字典{'sinafin':内容, 'baidufin':内容。。。}，返回失败或结果为空的情况就直接将内容用空字符代替，将结果返回给subwriter。
- 汇总并发的服务，对单位时间内调用超过阈值的服务次数进行控制，内建有并发阈值控制机制
- 对调用后返回发生错误or异常的请求进行重试，内建调用错误/异常重试机制。
- 作为reporter和LLM之间的中间层，LLM call on tool需要调用某些文章的全文，reporter整理请求发送给middleman，middleman组装报文调用mail tower第二次调用正文的服务，并将返回的正文解析后返回给reporter。
- 难点：middleman处理writer给的请求是来一个发5个，等到5个的结果凑齐了，再整合在一起发还给writer。但对于reporter的请求是来一个马上发去给mail tower，返回一个马上发还给reporter。当时reporter其实也是并行的worker，它怎么与middleman沟通也是一个需要设计的问题，也许可以给reporter设计一个池子，让middleman把所有sub reporter的返回值(带有reporter id)都发到这个池子里去，sub reporter每隔一几秒钟就轮询一次，看到自己的report id就拿，并在池子里删除删除这个返回值。reporter拿到之后可以按照返回值上的engine确定它是哪一部份的正文，用其article id确定是哪一篇文章的正文，以此来组装返回给LLM的上下文。具体的设计需要你参与。
- 有关engine+mail tower的文档在这里：/home/stockagent/project_space/research/experiments/mail_tower/intro（这个比较重要）和/home/stockagent/project_space/research/experiments/search_engine/intro（这个可能用不太多）。返回类型和重试策略/home/stockagent/project_space/research/experiments/report_machine/office/middleman/demand
注意，调用的默认配置是：只调用五类engine：sinafin(15) baidufin(20) thsfin(20) juchao(10) qnainfo(20)，括号中是max_results的对应取值，除qnainfo调用过去5天的日期做筛选以外，其余engine取上一个交易日至今日的日期做筛选，所有调用都mode=list。

几个关键功能的细节：
1. 关于重试机制：
正常情况下，middleman向mail tower发出一个服务请求后会马上获得服务返回一个processing的提示，包括其seesion id。如果30秒后还没收到回应，就拿session id调用一下status即/poll，如果还是processing就再重试，此处重试最多6次，6次后还返回processing就对服务调用关闭session的请求，requests.post("http://localhost:8300/close/session_id")，放弃这个session。然后重新调用原请求。这个重试过程最多再执行1次，如果仍然卡住就往下游返回空（preview=null），并在database数据库记录异常。第二次调用时，调用发出后不会有返回processing'的提示，如果过了20秒没返回结果，那么可以把调用的原请求再发送一遍，如果返回processing且articles=[]那么表示还在处理，等20秒再调用一次，从共重试3次，3次后还返回processing就放弃这个session，关闭它。然后重新调用原请求，不返回结果仍然重复20秒调用一次总共调用3次。如果仍然是卡住的这个状态就给下游返回空（articles=[]），并在database数据库记录异常。对于其他调用服务返回的结果，情况如下：
这是第一次调用engine+mail tower返回的结果树状图
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
HTTP status不在 JSON body 里。它在 HTTP 协议层的 status line（第一行）上

第二次调用engine+mail tower获取目标文章正文的服务相应类型：
---
/article 所有返回结果一览

正常（HTTP 200）

┌─────┬─────────────┬────────────────────┬────────────────┬────────────────────────────────┐
│  #  │ 顶层 status │      articles      │ session_closed │              含义              │
├─────┼─────────────┼────────────────────┼────────────────┼────────────────────────────────┤
│  1  │ processing  │         []         │     false      │ 正文还没提取完，稍后重试       │
├─────┼─────────────┼────────────────────┼────────────────┼────────────────────────────────┤
│  2  │    ready    │     全部 ready     │     false      │ 全部成功                       │
├─────┼─────────────┼────────────────────┼────────────────┼────────────────────────────────┤
│  3  │    ready    │ 混合 ready + error │     false      │ 部分成功，部分永久失败         │
├─────┼─────────────┼────────────────────┼────────────────┼────────────────────────────────┤
│  4  │    error    │     全部 error     │     false      │ 全部提取失败（永久）           │
├─────┼─────────────┼────────────────────┼────────────────┼────────────────────────────────┤
│  5  │ ready/error │        正常        │      true      │ 前 4 种之一，但 session 已关闭 │
└─────┴─────────────┴────────────────────┴────────────────┴────────────────────────────────┘

异常（HTTP ≠ 200）

┌─────┬────────┬────────────────────────────────────┬───────────────────┐
│  #  │ 状态码 │               detail               │       含义        │
├─────┼────────┼────────────────────────────────────┼───────────────────┤
│  6  │  404   │ Session not found                  │ session 过期/已关 │
├─────┼────────┼────────────────────────────────────┼───────────────────┤
│  7  │  400   │ get_article 仅适用于 list 模式     │ mode 不对         │
├─────┼────────┼────────────────────────────────────┼───────────────────┤
│  8  │  400   │ 必须提供 article_id 或 article_ids │ 缺参数            │
├─────┼────────┼────────────────────────────────────┼───────────────────┤
│  9  │  500   │ 搜索失败: ...                      │ 服务器内部错误    │

以上所有的返回情况的重试策略可以参见以下文档中的设计：
/home/stockagent/project_space/research/experiments/report_machine/office/middleman/demand

第一次调用：/search 初始返回

  第一次调用：/poll/{session_id} 轮询

  响应模型相同（PollResponse），但不同 status 下的必有字段不同：

  ┌────────────────────┬────────────────┬──────────────────────┬────────────────┐
  │        字段        │   processing   │  list_ready / done   │     error      │
  ├────────────────────┼────────────────┼──────────────────────┼────────────────┤
  │ session_id         │       ✅       │          ✅          │       ✅       │
  ├────────────────────┼────────────────┼──────────────────────┼────────────────┤
  │ status             │       ✅       │          ✅          │       ✅       │
  ├────────────────────┼────────────────┼──────────────────────┼────────────────┤
  │ session_closed     │    ✅ false    │          ✅          │    ✅ true     │
  ├────────────────────┼────────────────┼──────────────────────┼────────────────┤
  │ empty              │      ✅        │         ✅           │      ✅        │
  │                    │  null（auto）  │  true/false（auto）  │  null（auto）  │
  ├────────────────────┼────────────────┼──────────────────────┼────────────────┤
  │ preview            │    ❌ null     │       ✅ 有值        │    ❌ null     │
  ├────────────────────┼────────────────┼──────────────────────┼────────────────┤
  │ error              │    ❌ null     │       ❌ null        │    ✅ 有值     │
  ├────────────────────┼────────────────┼──────────────────────┼────────────────┤
  │ engine             │  ❌ 可能 null  │       ✅ 有值        │    ✅ 有值     │
  ├────────────────────┼────────────────┼──────────────────────┼────────────────┤
  │ mode               │  ❌ 可能 null  │       ✅ 有值        │    ✅ 有值     │
  ├────────────────────┼────────────────┼──────────────────────┼────────────────┤
  │ elapsed            │    ❌ null     │       ✅ 有值        │    ❌ null     │
  ├────────────────────┼────────────────┼──────────────────────┼────────────────┤
  │ created_at         │    ❌ null     │       ✅ 有值        │    ❌ null     │
  ├────────────────────┼────────────────┼──────────────────────┼────────────────┤
  │ articles /         │    ❌ null     │ ❌ null（list 模式） │    ❌ null     │
  │ segments           │                │                      │                │
  └────────────────────┴────────────────┴──────────────────────┴────────────────┘



2. 调用机制中的信息传递设计，这只是大致的设计，你需要给我的方案做优化甚至重写（重点考虑一下middleman对各种id进行衔接的过程如何落地，是存在本地数据库还是内存中调用会比较好）：
1）sub writer 生成一个writer id向发出请求middleman，middleman获得writer id
2）middleman请求engine+mail tower服务，mail tower返回session id，middleman获得session id，将这个session id与writer id联系在一起
3）带有session id的mail tower回复（第一次请求的结果文章列表）返回给middleman，同一个writer id的返回值被放在一起，当一个writer id下的返回结果凑齐了sinafin baidufin thsfin juchao qnainfo这五个engine类之后，middleman将这个结果整理成字典携session id、writer id发送给writer
4）report向middleman发送请求文章正文，包含reporter id和session id和[文章id]，middleman组装报文输入。得到返回后整理结果
返回给reporter with reporter id, session id, 文章id和正文。

3. 关于报文组装：
a. 第一次服务请求，来自sub writer输入的内容包含writer id, 股票代码xxxxxx格式，其余的调用mail tower的配置需要使用middleman的默认配置，这里的默认配置是：调用五类engine：sinafin(15) baidufin(20) thsfin(20) juchao(10) qnainfo(20)，除qnainfo调用过去5天的日期做筛选以外，其余engine取上一个交易日至今日的日期做筛选，mode=list，max_results取值如（）中如下范例中所示配置：
  1) 调用sinafin+mail tower服务，取上一个交易日至今日的日期做筛选，调用的完整参数是（假设今日的日期是2026-07-24。注意，这里的上一个交易日要查交易日历来确定/home/stockagent/project_space/research/experiments/report_machine/data_fetch/midday/trade_calendar.py）
  # sinafin — 上一个交易日至今 （分钟级）
  curl -X POST http://localhost:8300/search \
    -H "Content-Type: application/json" \
    -d '{"query":"600031","engine":"sinafin","mode":"list","max_results":15,"start_date":"2026-07-23","end_date":"2026-07-24"}'
  2）调用baidufin+mail tower服务，取上一个交易日至今日的日期做筛选，调用的完整参数是
  # baidufin — 上一个交易日至今
  curl -X POST http://localhost:8300/search \
    -H "Content-Type: application/json" \
    -d '{"query":"600031","engine":"baidufin","mode":"list","max_results":20,"start_date":"2026-07-23","end_date":"2026-07-24"}'
  3）调用thsfin+mail tower服务，取上一个交易日至今日的日期做筛选，调用的完整参数是
    # thsfin — 上一个交易日至今
  curl -X POST http://localhost:8300/search \
    -H "Content-Type: application/json" \
    -d '{"query":"600031","engine":"thsfin","mode":"list","max_results":20,"start_date":"2026-07-23","end_date":"2026-07-24"}'
  4）调用juchao+mail tower服务，取上一个交易日至今日的日期做筛选，调用的完整参数是
  # juchao — 上一个交易日至今
  curl -X POST http://localhost:8300/search \
    -H "Content-Type: application/json" \
    -d '{"query":"600031","engine":"juchao","mode":"list","max_results":10,"start_date":"2026-07-23","end_date":"2026-07-24"}'
  5）调用qnainfo+mail tower服务，取上过去5天的日期做筛选，调用的完整参数是
  # qnainfo — 最近 5 天  （分钟级）
  curl -X POST http://localhost:8300/search \
    -H "Content-Type: application/json" \
    -d '{"query":"600031","engine":"qnainfo","mode":"list","max_results":20,"start_date":"2026-07-20","end_date":"2026-07-24"}'

b. 第一次服务返回结果，来自mail tower返回给writer
  middleman接受到的结果
 1. status: "list_ready" — 列表就绪，正文后台加载中（sinafin）

  {
    "session_id": "s_20260727_153509_123456_7890",
    "status": "list_ready",
    "mode": "list",
    "llm_mode": "none",
    "engine": "sinafin",
    "empty": false,
    "session_closed": false,
    "preview": {
      "articles": [
        {
          "id": "a_01",
          "title": "潍柴动力涨3.01%，成交额22.81亿元，后市是否有机会？",
          "body_avail": "有",
          "date": "2026-07-27 15:00",
          "date_source": "sinafin",
          "date_confidence": "high",
          "snippet": "",
          "_category": "资讯"
        }
      ],
      "total": 4
    },
    "elapsed": 3.1,
    "created_at": "2026-07-27T15:35:12"
  }

  2. status: "done" — 全部完成（qnainfo，正文已随 search 返回）

  {
    "session_id": "s_20260727_153509_654321_0987",
    "status": "done",
    "mode": "list",
    "llm_mode": "none",
    "engine": "qnainfo",
    "empty": false,
    "session_closed": false,
    "preview": {
      "articles": [
        {
          "id": "a_01",
          "title": "上市公司相关互动问答",
          "body_avail": "无",
          "date": "2026-07-23 17:11:03",
          "snippet": "【问题】港股中兴通讯上周五已经完成除权派息，请问为什么A股...",
          "_category": "互动易问答"
        }
      ],
      "total": 3
    },
    "elapsed": 3.8,
    "created_at": "2026-07-27T15:35:11"
  }

  3. status: "error" — 搜索失败

  {
    "session_id": "s_20260727_153509_111222_3333",
    "status": "error",
    "mode": "list",
    "llm_mode": "none",
    "engine": "baidufin",
    "empty": null,
    "session_closed": true,
    "preview": null,
    "error": "搜索超时 (90s)"
  }
结果整理：
- 如果status=error则只返回session_id，engine，preview=null
- 如果status=done/list_ready，那么取session_id，engine，preview（preview中的articles中只取id title body_avail date snippet _category这些变量，preview中的total也留下，结构保持原样）
- 等到五个engine的结果都获得之后，返回值处理成一个大字典，其中每个engine值对应一个字典包含session id和preview，如：{engine:{session_id:xxx, preview:xxx}, ...}将这个结果携writer id返回给writer

c. 第二次服务请求，来自reporter，发送给mail tower
- 来自reporter的请求带样式如下：
{report_id:xxx,
content: [
{
  engine: xxxx
  session_id: xxx
  article_id: [xx, xx, xx]
},
{
  engine: xxxx
  session_id: xxx
  article_id: [xx, xx, xx]
}
]
}
article_ids内容如['a_01', 'a_02']。其中engine不用输入mail tower。需提炼其中content中的每一个字典，转化成输入mail tower的报文（不含engine）：{"session_id": "s_20260727_153509_xxx", "article_ids": ["a_01", "a_02"]}并发送
- 对于每个mail tower返回的结果，需要匹配其来自reporter时的engine，可以通过其session_id和reporter发送的请求来匹配，当然如果你有更好的办法那就更好了。总之，需要知道返回结果对应的engine，因为发送给服务的输入和输出都没有engine，所以在接收到其返回后需搭配上其原来的engine，才能作为最终的返回结果。
- 将reporter的报文中的content中每一个请求发出去后，要等到其每一个返回后组装在一起返回给reporter

d. 第二次服务返回结果，来自mail tower，发给reporter
  标准 /article 响应

  {
    "session_id": "s_20260727_153509_123456_7890",
    "status": "ready",
    "articles": [                                                   
      {
        "article_id": "a_01",
        "status": "ready",
        "title": "标题内容",
        "url": "https://...",
        "date": "2026-07-27",
        "body_text": "正文内容...",
        "truncated": false,
        "fetch_error": ""
      }
    ],
    "session_closed": false
  }
- 当第一层的status是error的时候，返回session_id，articles=[]，session_closed
- 当第一层的status是ready的时候，返回session_id，articles（其中只需要包括article_id、body_text、truncated），session_closed
- 当第一层的status=ready的时候，在处理articles中的内容时，先看每一个成员中的status，如果是error，那么body_text：""。status=ready，则body_text正常输出。
- 每一个engine的输出结构: {engine: {session_id:xxx, session_closed:xxx, articles:{}}} 携带reporter_id送回reporter，注意这里的engine来自reporter请求时的发送内容。
- 最终返回给reporter的返回值结构：
[reporter_id, {engine1: {session_id:xxx, session_closed:xxx, articles:{}}, engine2:{...}}]


c和d这两个过程在一个请求上不止发生一次，同一个reporter可能反复调用。



reporter
这是最靠近agent loop的一层，当writer组装好数据+新闻资讯的上下文之后，writer把context打包发送给reporter。reporter会启动一个worker称为sub reporter来处理这个context。reporter是一个api，它接收writer发送的context并开启一个子进程来并行的处理，它先给这个sub reporter一个reporter id，然后reporter拿着这个context去组装agent的prompt并进入agent loop。要注意，agent loop其实就是reporter内的一个代码循环，agent其实就是reporter去了事先写好的一些可组装的prompt（包括agent.md, preference.md, soul.md和skills），其中的skills中需要新建一个文件夹作为tool在其中写一个skill.md是对这个工具的使用的介绍。
这个工具的具体功能是，在固定区域内列出的文章信息是其标题和部分摘要、分类信息，这些文章旁会有一个标签叫做body_avail，如果body_avail=有，代表其标题含有正文可以通过tool call来调用。如果LLM通过对这个文章的标题和摘要的了解认为其正文内容可能对生成报告有帮助，可以通过tool call反馈文章的article_id来获取文章正文。
reporter在agent loop中如果遇到tool call就解析LLM返回的article id，需要先通过body_avail判断其是否有正文（验证一下LLM申请是否有效），如果没有正文的article id需要删除（如果删除之后没有内容可以调用了，那就直接不调用返回错误提示和原上下文给LLM），将其分为不同engine，将article id搭配其对应的session_id发给middleman，发送示例如：
{report_id:xxx,
content: [
{
  engine: xxxx
  session_id: xxx
  article_id: [xx, xx, xx]
},
{
  engine: xxxx
  session_id: xxx
  article_id: [xx, xx, xx]
}
]
}
请求之后sub reporter需要每隔n秒到返回池中寻找标记自己report id的返回值，直到得到返回值，解析报文组装上下文传给LLM，answer tool call完成。（这个在池中寻找自己返回值的过程设计方案可优化）
当LLM叫停agent loop后，reporter得到一篇完整的分析报告，将其调整格式输出为md文档，在指定位置新建文件夹并保存。
注意，构建的agent prompt必须单独存储，可以单独修改，其构成可以参考/home/stockagent/project_space/research/experiments/exp02/agent，尤其是skill的tool部分，但是不要抄起内容，因为这是两个功能完全不同的agent。prompt的实际内容可以不写，可以写最必要的不会出错的内容，后期由我填充完整。但agent loop和tool call的基本功能实现的内容要写上去。loop也要建立上去。











好的，现在我提一个测试方案的要求，你给我做一个完整的测试方案 
测试方案要求（以下所说的主体包括：fetcher, writer, middleman, reporter。测试两个主体之间的通信情况时需要测与mail tower的通信，但不需要测mail tower的功能）
1. 首先检查每一部分的语法，尤其是报文的语法结构，检查需要沟通的两个主体之间的报文在各种情况下是否能顺利对接。单独测试需要通信的所有的两个主体之间的在所有的情况下的通信情况，比如测试正常通信、超时状态（包括一方超时或另一方超时）、失败状态等等，请按照开发文档穷举所有状态的组合。测试通信是否按照需求实现了功能。
2. 使用一个测试案例，比如['淮北矿业', '博瑞医药', '凯莱英', '广生堂']，作为输入单独测试每个主体在齐自己的功能范围内部的功能是否正常，测试每个主体的所有功能和所有应用场景。
3. 使用实例，比如['淮北矿业', '博瑞医药', '凯莱英', '广生堂']测试两个主体包含通信功能的主体的所有功能包含通信是否正常。
4. 在以上测试都测通的情况下，对有负载要求的主体（比如middleman， reporter）进行单独的高并发压力测试，比如测试30-50只股票并发的情况，记录一些压力测试产生的问题。测通后可以进行两个含有通信功能的主体之间的交互高并发压力测试，记录测试消耗时间和异常情况，推断异常与高并发的关系。
5. 在以上测试都没问题的情况下，进行reporter内的agent loop与LLM deepseek的测试，丰富以下prompt，拿出一个context模板来输入prompt看deepseek是否可以正常call on tool是否能正常使用信息返回结果。
6. 以上都测通后，进行端到端测试。使用['淮北矿业', '博瑞医药', '凯莱英', '广生堂']进行测试。测通之后进行端到端压力测试，与上面压力测试要求一样，最好能测出几个档次，体现出在不同压力下系统的表现和异常。
7. 以上测试均一遍测一边问一边改代码debug，测试完即修完，形成一个系统的测试报告。
8. 每次测试都先写测试脚本到/home/stockagent/project_space/research/experiments/report_machine/office/test_drive中新建相应的文件夹，然后写一个解析结果的脚本用于生成结果可读性较强的md文档，在测试文件夹下新建results保存测试结果。每次重测复用脚本即可，测试方案要写完整的文档。注意在测试过程中更新文档





我觉得我的设计没有被你正确理解：
我需要64个worker可以再reporter中进行无阻塞的并行服务，也就是说如果我调用了50只股票，假设进度都一样快，到时候50个sub writer一起发出请求那么也必须有足够的reporter每个都独立的接受请求独立run agent loop调LLM，这一点你明白吗？你觉得有什么障碍吗？
另外一个问题，你说sub writer 超时从 30s 改到了 180s，我不记得我设置了这个超时？这个超时是什么时候设置的？超时是从sub writer什么时候开始计时的？你如果在测试时觉得应该修改超时机制的话一定要先征求我的意见。



md转带个是ms word的工具已经下载好了，你把这个功能也做一下吧
写测试文档，内容要全面，包括测试要求，设计，流程，测试结果等
把office开发和使用文档进行更新，最近更新的内容记录进去



输入改成
{
  "stock_names": ["淮北矿业", "博瑞医药", "凯莱英"],
  "query": "生成该股票的午间收盘分析报告"
}
这个query直接放到writer发给reporter的json下，最底层的一个变量就好了
reporter拿到json后还是按照之前的要求解析报文，query的值放到上下文的最后，单独一行，前面是 "需求：" + query value
