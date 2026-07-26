# 财联社市场情绪 + 行业分类 — 接口测试

> 日期: 2026-07-21

---
## 1. 市场情绪（market_emotion_cls）

**返回键**: ['market_degree', 'shsz_balance', 'shsz_balance_change_px', 'preview_balance', 'preview_balance_change_px', 'up_ratio', 'up_ratio_num', 'up_open_num', 'performance', 'up_open_ratio', 'profit_ratio', 'up_down_dis', 'limit_up_board']

- **market_degree**: 20
- **shsz_balance**: 1.31万亿
- **shsz_balance_change_px**: +401亿
- **preview_balance**: 2.85万亿
- **preview_balance_change_px**: +1503亿
- **up_ratio**: 80.00%
- **up_ratio_num**: 16
- **up_open_num**: 4
- **performance**: -0.60%
- **up_open_ratio**: 60%
- **profit_ratio**: 42%
### up_down_dis
- status: True
- suspend_num: 4
- up_num: 16
- down_num: 105
- rise_num: 1225
- fall_num: 4234
- flat_num: 70
- down_10: 380
- down_8: 533
- down_6: 1038
- down_4: 1201
- down_2: 1082
- up_2: 808
- up_4: 274
- up_6: 83
- up_8: 29
- up_10: 31
### limit_up_board
- 一板:
  - count: 12
  - continuous_rate: 7%
- 二板:
  - count: 3
  - continuous_rate: 0%
- 三板:
  - count: 0
  - continuous_rate: 100%
- 高度板:
  - count: 1
  - continuous_rate: -

---
## 2. 开盘红情绪（market_emotion_kph）

**返回键**: ['zt', 'dt', 'sjzt', 'sjdt', 'stzt', 'stdt', 'rise_num', 'fall_num', 'sign', 'flat', 'rise_dist', 'fall_dist', 'szln', 'qscln', 's_zrcs', 'q_zrcs']

- **zt**: 16
- **dt**: 105
- **sjzt**: 16
- **sjdt**: 91
- **stzt**: 0
- **stdt**: 14
- **rise_num**: 1239
- **fall_num**: 3891
- **sign**: 市场人气低迷
- **flat**: 68
- **rise_dist**: {1: 453, 2: 371, 3: 180, 4: 96, 5: 50, 6: 28, 7: 19, 8: 13, 9: 5, 10: 8}
- **fall_dist**: {-1: 510, -2: 580, -3: 578, -4: 549, -5: 500, -6: 385, -7: 275, -8: 160, -9: 126, -10: 123}
- **szln**: 60871831
- **qscln**: 130971203
- **s_zrcs**: 59264255
- **q_zrcs**: 126932624

---
## 3. 财联社行业分类（sector_industry_cls）

返回类型: list

共 54 个行业

### 行业 #1
字段: ['secu_name', 'secu_code', 'change', 'main_fund_diff', 'limit_up', 'limit_down', 'limit_up_num', 'limit_down_num', 'trade_status', 'first_stock']

- **secu_name**: 贵金属
- **secu_code**: cls80114
- **change**: 0.0245
- **main_fund_diff**: -7826041
- **limit_up**: 14
- **limit_down**: 0
- **limit_up_num**: 0
- **limit_down_num**: 0
- **trade_status**: TRADE
- **first_stock**: {'last_px': 33.94, 'secu_code': 'sh600988', 'secu_name': '赤峰黄金', 'trade_status': 'TRADE', 'change': 0.0524, 'tr': 0.0159}

### 行业 #2
字段: ['secu_name', 'secu_code', 'change', 'main_fund_diff', 'limit_up', 'limit_down', 'limit_up_num', 'limit_down_num', 'trade_status', 'first_stock']

- **secu_name**: 能源金属
- **secu_code**: cls82013
- **change**: 0.0179
- **main_fund_diff**: 31958886
- **limit_up**: 10
- **limit_down**: 3
- **limit_up_num**: 0
- **limit_down_num**: 0
- **trade_status**: TRADE
- **first_stock**: {'last_px': 39.06, 'secu_code': 'sh603799', 'secu_name': '华友钴业', 'trade_status': 'TRADE', 'change': 0.0787, 'tr': 0.0352}

### 行业 #3
字段: ['secu_name', 'secu_code', 'change', 'main_fund_diff', 'limit_up', 'limit_down', 'limit_up_num', 'limit_down_num', 'trade_status', 'first_stock']

- **secu_name**: 机场
- **secu_code**: cls80137
- **change**: 0.0111
- **main_fund_diff**: -28311461
- **limit_up**: 5
- **limit_down**: 0
- **limit_up_num**: 0
- **limit_down_num**: 0
- **trade_status**: TRADE
- **first_stock**: {'last_px': 8.11, 'secu_code': 'sh600004', 'secu_name': '白云机场', 'trade_status': 'TRADE', 'change': 0.0201, 'tr': 0.0065}

---
### 成分股字段检查
相关字段: ['secu_name', 'secu_code', 'first_stock']
全部字段: ['secu_name', 'secu_code', 'change', 'main_fund_diff', 'limit_up', 'limit_down', 'limit_up_num', 'limit_down_num', 'trade_status', 'first_stock']

---
*生成时间: 2026-07-21*