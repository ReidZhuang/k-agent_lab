# agent_guide 测试报告

**模型**: qwen2.5:7b
**日期**: 2026-07-15

## 原测试集 (14条)

| # | ID | Query | chain | Requests | 状态 |
|---|-----|-------|-------|----------|------|
| 1 | TC-01 | 宁德时代今天的涨跌幅 | false | 1 | ✅ |
| 2 | TC-02 | 查询宁德时代今天的最高价和最低价 | false | 2 | ✅ |
| 3 | TC-03 | 我想知道比亚迪和宁德时代今天中午收盘的股价 | false | 1 | ✅ |
| 4 | TC-04 | 给我查一下宁德时代在今天收盘和上周收盘的换手率 | false | 2 | ✅ |
| 5 | TC-05 | 宁德时代所在的版块今天的涨跌幅 | true | 2 | ✅ |
| 6 | TC-06 | 宁德时代所在的版块的涨跌幅和成交量 | true | 3 | ✅ |
| 7 | TC-07 | 电池板块今天的涨跌幅 | false | 1 | ✅ |
| 8 | TC-08 | 查一下上证指数今天的涨跌幅和成交量 | false | 2 | ✅ |
| 9 | TC-09 | 茅台和五粮液今天的股价谁高？ | false | 1 | ✅ |
| 10 | TC-10 | 宁德时代的涨跌幅 | false | 1 | ✅ |
| 11 | TC-11 | 查一下宁德时代所在的板块的龙头股的涨跌幅 | true | 3 | ✅ |
| 12 | TC-12 | 最近一个月北向资金流向 | false | 1 | ✅ |
| 13 | TC-13 | 宁德时代所在板块今天的涨跌幅和主力资金流入 | true | 3 | ✅ |
| 14 | TC-14 | 新能源汽车板块最近5天的涨跌幅 | false | 1 | ✅ |

---
## 条件盲测 (20条)

| # | ID | Query | 期望 chain | 期望 count | 结果 chain | 结果 count | 状态 |
|---|-----|-------|-----------|-----------|-----------|-----------|------|
| 1 | CT-01 | 贵州茅台昨天下午的收盘价 | False | 1 | False | 1 | ✅ |

**CT-01 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "贵州茅台"
      ],
      "var": "收盘价",
      "condition": [
        "昨天下午"
      ]
    }
  ],
  "chain": false
}
```

| 2 | CT-02 | 宁德时代年初至今的涨跌幅 | False | 1 | False | 1 | ✅ |

**CT-02 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "涨跌幅",
      "condition": [
        "年初至今"
      ]
    }
  ],
  "chain": false
}
```

| 3 | CT-03 | 比亚迪最近5日的北向资金净买入 | False | 1 | False | 1 | ✅ |

**CT-03 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "比亚迪"
      ],
      "var": "北向资金",
      "condition": [
        "最近5天",
        "净买入"
      ]
    }
  ],
  "chain": false
}
```

| 4 | CT-04 | 药明康德昨日的成交量 | False | 1 | False | 1 | ✅ |

**CT-04 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "药明康德"
      ],
      "var": "成交量",
      "condition": [
        "昨天"
      ]
    }
  ],
  "chain": false
}
```

| 5 | CT-05 | 汇川技术上周五的收盘价 | False | 1 | False | 1 | ✅ |

**CT-05 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "汇川技术"
      ],
      "var": "收盘价",
      "condition": [
        "上周五"
      ]
    }
  ],
  "chain": false
}
```

| 6 | CT-06 | 中国平安本周以来的涨跌幅 | False | 1 | False | 1 | ✅ |

**CT-06 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "中国平安"
      ],
      "var": "涨跌幅",
      "condition": [
        "本周以来"
      ]
    }
  ],
  "chain": false
}
```

| 7 | CT-07 | 五粮液去年同期的营业收入 | False | 1 | False | 1 | ✅ |

**CT-07 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "五粮液"
      ],
      "var": "营业收入",
      "condition": [
        "上年同期"
      ]
    }
  ],
  "chain": false
}
```

| 8 | CT-08 | 贵州茅台近3个交易日的资金流向 | False | 1 | False | 1 | ✅ |

**CT-08 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "贵州茅台"
      ],
      "var": "资金流向",
      "condition": [
        "最近3个交易日"
      ]
    }
  ],
  "chain": false
}
```

| 9 | CT-09 | 恒瑞医药盘中的实时股价 | False | 1 | False | 1 | ✅ |

**CT-09 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "恒瑞医药"
      ],
      "var": "盘中价",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

| 10 | CT-10 | 隆基绿能前复权的收盘价 | False | 1 | False | 1 | ✅ |

**CT-10 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "隆基绿能"
      ],
      "var": "收盘价",
      "condition": [
        "今天",
        "前复权"
      ]
    }
  ],
  "chain": false
}
```

| 11 | CT-11 | 招商银行今年一季度的净利润 | False | 1 | False | 1 | ✅ |

**CT-11 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "招商银行"
      ],
      "var": "净利润",
      "condition": [
        "最近一个季度"
      ]
    }
  ],
  "chain": false
}
```

| 12 | CT-12 | 长江电力近10日的涨跌幅 | False | 1 | False | 1 | ✅ |

**CT-12 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "长江电力"
      ],
      "var": "涨跌幅",
      "condition": [
        "最近10天"
      ]
    }
  ],
  "chain": false
}
```

| 13 | CT-13 | 格力电器当日开盘价和收盘价 | False | 2 | False | 2 | ✅ |

**CT-13 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "格力电器"
      ],
      "var": "开盘价",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "格力电器"
      ],
      "var": "收盘价",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

| 14 | CT-14 | 美的集团最近一周的北向资金 | False | 1 | False | 1 | ✅ |

**CT-14 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "美的集团"
      ],
      "var": "北向资金",
      "condition": [
        "最近一周"
      ]
    }
  ],
  "chain": false
}
```

| 15 | CT-15 | 工商银行过去30个交易日的股价走势 | False | 1 | False | 1 | ✅ |

**CT-15 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "工商银行"
      ],
      "var": "股价",
      "condition": [
        "最近30个交易日"
      ]
    }
  ],
  "chain": false
}
```

| 16 | CT-16 | 宁德时代今日最高涨幅超过5%了吗 | False | 1 | False | 1 | ✅ |

**CT-16 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "最高涨幅",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

| 17 | CT-17 | 上证指数今年以来的表现 | False | 1 | False | 1 | ✅ |

**CT-17 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "上证指数"
      ],
      "var": "涨跌幅",
      "condition": [
        "今年以来"
      ]
    }
  ],
  "chain": false
}
```

| 18 | CT-18 | 中芯国际昨日和前日的资金流向对比 | False | 2 | False | 2 | ✅ |

**CT-18 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "中芯国际"
      ],
      "var": "资金流向",
      "condition": [
        "昨天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "中芯国际"
      ],
      "var": "资金流向",
      "condition": [
        "前天"
      ]
    }
  ],
  "chain": false
}
```

| 19 | CT-19 | 工业富联三季度末的股东人数 | False | 1 | False | 1 | ✅ |

**CT-19 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "工业富联"
      ],
      "var": "股东人数",
      "condition": [
        "截至三季度末"
      ]
    }
  ],
  "chain": false
}
```

| 20 | CT-20 | 紫金矿业盘后的大单交易 | False | 1 | False | 1 | ✅ |

**CT-20 输出**:
```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "紫金矿业"
      ],
      "var": "大单交易",
      "condition": [
        "盘后"
      ]
    }
  ],
  "chain": false
}
```


**汇总**: 20/20 通过, 0 失败
