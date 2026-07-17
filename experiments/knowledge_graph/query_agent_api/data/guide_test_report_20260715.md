# agent_guide 全量测试报告

**模型**: qwen2.5:7b
**日期**: 2026-07-15
**汇总**: 14/14

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
## 详细输出

### TC-01: 宁德时代今天的涨跌幅

```json
{
  "query_id": "Q_0f1a2b3c",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

### TC-02: 查询宁德时代今天的最高价和最低价

```json
{
  "query_id": "Q_3f9e",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "最高价",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "宁德时代"
      ],
      "var": "最低价",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

### TC-03: 我想知道比亚迪和宁德时代今天中午收盘的股价

```json
{
  "query_id": "Q_3e4f5g6h",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "比亚迪",
        "宁德时代"
      ],
      "var": "股价",
      "condition": [
        "今天中午收盘"
      ]
    }
  ],
  "chain": false
}
```

### TC-04: 给我查一下宁德时代在今天收盘和上周收盘的换手率

```json
{
  "query_id": "Q_3e4f5g6h",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "换手率",
      "condition": [
        "今天收盘"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "宁德时代"
      ],
      "var": "换手率",
      "condition": [
        "一周前收盘"
      ]
    }
  ],
  "chain": false
}
```

### TC-05: 宁德时代所在的版块今天的涨跌幅

```json
{
  "query_id": "Q_3e4f5g6h",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "板块",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "res0"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": true
}
```

### TC-06: 宁德时代所在的版块的涨跌幅和成交量

```json
{
  "query_id": "Q_9e4b",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "板块",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "res0"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "res0"
      ],
      "var": "成交量",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": true
}
```

### TC-07: 电池板块今天的涨跌幅

```json
{
  "query_id": "Q_9e3f4a5b",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "电池板块"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

### TC-08: 查一下上证指数今天的涨跌幅和成交量

```json
{
  "query_id": "Q_3e4f5g6h",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "上证指数"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "上证指数"
      ],
      "var": "成交量",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

### TC-09: 茅台和五粮液今天的股价谁高？

```json
{
  "query_id": "Q_3e4f5g6h",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "茅台",
        "五粮液"
      ],
      "var": "股价",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

### TC-10: 宁德时代的涨跌幅

```json
{
  "query_id": "Q_4e9a3bdf",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

### TC-11: 查一下宁德时代所在的板块的龙头股的涨跌幅

```json
{
  "query_id": "Q_4e5f6a7b",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "板块",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "res0"
      ],
      "var": "龙头股",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "res1"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": true
}
```

### TC-12: 最近一个月北向资金流向

```json
{
  "query_id": "Q_3f4e5f6a",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "北向资金"
      ],
      "var": "资金流向",
      "condition": [
        "最近一个月"
      ]
    }
  ],
  "chain": false
}
```

### TC-13: 宁德时代所在板块今天的涨跌幅和主力资金流入

```json
{
  "query_id": "Q_4e5f6a7b",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "板块",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "res0"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "宁德时代"
      ],
      "var": "主力资金流入",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": true
}
```

### TC-14: 新能源汽车板块最近5天的涨跌幅

```json
{
  "query_id": "Q_3f4e5f6e",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "新能源汽车"
      ],
      "var": "涨跌幅",
      "condition": [
        "最近5天"
      ]
    }
  ],
  "chain": false
}
```


---
## 盲测：Prompt 中未出现的股票/代码 (10条)

| # | ID | Query | 期望 chain | 期望 count | 结果 chain | 结果 count | 状态 |
|---|-----|-------|-----------|-----------|-----------|-----------|------|
| 1 | BT-01 | 查询300750.SZ今天的最新价 | False | 1 | False | 1 | ✅ |

**输出**:
```json
{
  "query_id": "Q_4e5f6a7b",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "300750.SZ"
      ],
      "var": "最新价",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

| 2 | BT-02 | 中国平安今天的市盈率是多少 | False | 1 | False | 1 | ✅ |

**输出**:
```json
{
  "query_id": "Q_3f4e5f6e",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "中国平安"
      ],
      "var": "市盈率",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

| 3 | BT-03 | 恒生指数今天的收盘价和涨跌幅 | False | 2 | False | 2 | ✅ |

**输出**:
```json
{
  "query_id": "Q_4e5f6a7b",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "恒生指数"
      ],
      "var": "收盘价",
      "condition": [
        "今天收盘"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "恒生指数"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

| 4 | BT-04 | 海康威视和大华股份今天的涨跌幅 | False | 1 | False | 1 | ✅ |

**输出**:
```json
{
  "query_id": "Q_9e4b3a5c",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "海康威视",
        "大华股份"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

| 5 | BT-05 | 科创50指数今天的成交额 | False | 1 | False | 1 | ✅ |

**输出**:
```json
{
  "query_id": "Q_4e5f6a7b",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "科创50指数"
      ],
      "var": "成交额",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

| 6 | BT-06 | 药明康德今日的成交量 | False | 1 | False | 1 | ✅ |

**输出**:
```json
{
  "query_id": "Q_3f4e5f6e",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "药明康德"
      ],
      "var": "成交量",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

| 7 | BT-07 | 中信证券所在行业的平均市盈率 | True | 2 | True | 2 | ✅ |

**输出**:
```json
{
  "query_id": "Q_4e9a3bdf",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "中信证券"
      ],
      "var": "行业",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "res0"
      ],
      "var": "平均市盈率",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": true
}
```

| 8 | BT-08 | 游戏板块今天的主力资金净流入 | False | 1 | False | 1 | ✅ |

**输出**:
```json
{
  "query_id": "Q_3f4e5d6c",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "游戏板块"
      ],
      "var": "主力资金净流入",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

| 9 | BT-09 | 长江电力和中国核电今天的涨跌幅对比 | False | 1 | False | 1 | ✅ |

**输出**:
```json
{
  "query_id": "Q_4e5f6a7b",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "长江电力",
        "中国核电"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

| 10 | BT-10 | 三一重工所属行业的龙头股的资金流向 | True | 3 | True | 3 | ✅ |

**输出**:
```json
{
  "query_id": "Q_4e5f6g7h",
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "三一重工"
      ],
      "var": "行业",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "res0"
      ],
      "var": "龙头股",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "res1"
      ],
      "var": "资金流向",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": true
}
```
