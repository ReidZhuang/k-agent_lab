## 接口
lk.market_emotion_cls()

## 返回结构
返回 dict，直接索引访问：
- emotion['market_degree']  → 市场热度 int 0-100
- emotion['up_ratio']       → 上涨占比 %
- emotion['profit_ratio']   → 赚钱效应 %
- emotion['shsz_balance']   → 两市成交额
- emotion['limit_up_board'] → 涨停梯队 dict