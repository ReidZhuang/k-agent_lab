# agent_guide 复合型 Query 测试报告

**模型**: qwen2.5:7b
**日期**: 2026-07-15

**汇总**: ✅17 / ⚠️2 / ❌1

| # | ID | 类别 | Query | 期望 chain | 期望 count | 结果 chain | 结果 count | 状态 |
|---|-----|------|-------|-----------|-----------|-----------|-----------|------|
| 1 | CX-01 | 3-level chain | 宁德时代所在板块的龙头股的所属概念 | True | 3 | ? | ? | ❌ |
| 2 | CX-02 | chain | 茅台所在行业的平均市盈率排名 | True | 2 | True | 2 | ✅ |
| 3 | CX-03 | chain | 比亚迪所在的板块的龙头股的资金流向 | True | 3 | True | 3 | ✅ |
| 4 | CX-04 | chain | 药明康德所在行业的平均毛利率 | True | 2 | True | 2 | ✅ |
| 5 | CX-05 | chain | 三一重工所属行业的龙头股的最新收盘价 | True | 3 | True | 3 | ✅ |
| 6 | CX-06 | 4 parallel metrics | 宁德时代今天的成交量、换手率、振幅、成交额 | False | 4 | False | 4 | ✅ |
| 7 | CX-07 | 5 parallel metrics | 上证指数今天的开盘价、收盘价、最高价、最低价、成交量 | False | 5 | False | 5 | ✅ |
| 8 | CX-08 | 5 financial metrics | 茅台今天的PE、PB、PS、ROE、营收增长率 | False | 5 | False | 5 | ✅ |
| 9 | CX-09 | 3 indexes | 沪深300、上证50、中证500今天的涨跌幅 | False | 3 | False | 3 | ✅ |
| 10 | CX-10 | 4 financial | 招商银行今年的净利润、营业收入、ROE、不良率 | False | 4 | False | 4 | ✅ |
| 11 | CX-11 | 5 stocks, 1 metric | 宁德时代、比亚迪、长城汽车、上汽集团、广汽集团今天的涨跌幅 | False | 1 | False | 1 | ✅ |
| 12 | CX-12 | 5 baijiu stocks, 1 metric | 贵州茅台、五粮液、泸州老窖、山西汾酒、洋河股份今天的股价 | False | 1 | False | 1 | ✅ |
| 13 | CX-13 | 5 banks, 1 metric | 工商银行、建设银行、农业银行、中国银行、招商银行今天的涨跌幅 | False | 1 | False | 1 | ✅ |
| 14 | CX-14 | 5 solar stocks | 宁德时代、阳光电源、隆基绿能、通威股份、TCL中环今天的换手 | False | 1 | False | 5 | ⚠️ |
| 15 | CX-15 | 5 insurance | 中国平安、中国人寿、中国太保、新华保险、中国人保今天的涨跌幅 | False | 1 | False | 1 | ✅ |
| 16 | CX-16 | chain + parallel mixed | 宁德时代所属板块的龙头股以及比亚迪今天的涨跌幅 | True | 3 | True | 3 | ✅ |
| 17 | CX-17 | chain + independent | 查一下茅台所在行业的平均PE和五粮液的PE | True | 3 | True | 3 | ✅ |
| 18 | CX-18 | 3 indexes * 2 metrics | 沪深300、中证500、创业板指今天的涨跌幅和成交额 | False | 6 | False | 6 | ✅ |
| 19 | CX-19 | 3 entities each chain | 宁德时代、比亚迪、长城汽车所属行业的板块涨跌幅 | True | 6 | True | 2 | ⚠️ |
| 20 | CX-20 | 5 sectors | 白酒板块、医药板块、新能源板块、银行板块、半导体板块今天的涨 | False | 1 | False | 1 | ✅ |

---
## 详细输出

### CX-01: 宁德时代所在板块的龙头股的所属概念

**类别**: 3-level chain  
**状态**: ❌ [2] condition 为空

**原始回复**:
```
{
    "requests": [
        {"req_id": "R_001", "obj": ["宁德时代"], "var": "板块", "condition": ["今天"]},
        {"req_id": "R_002", "obj": ["res0"], "var": "龙头股", "condition": ["今天"]},
        {"req_id": "R_003", "obj": ["res1"], "var": "所属概念", "condition": []}
    ],
    "chain": true
}
```

### CX-02: 茅台所在行业的平均市盈率排名

**类别**: chain: 行业→平均市盈率排名  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "茅台"
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
      "var": "平均市盈率排名",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": true
}
```

### CX-03: 比亚迪所在的板块的龙头股的资金流向

**类别**: chain: 板块→龙头股→资金流向  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "比亚迪"
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
      "var": "资金流向",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": true
}
```

### CX-04: 药明康德所在行业的平均毛利率

**类别**: chain: 行业→毛利率  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "药明康德"
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
      "var": "平均毛利率",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": true
}
```

### CX-05: 三一重工所属行业的龙头股的最新收盘价

**类别**: chain: 行业→龙头股→收盘价  
**状态**: ✅

```json
{
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
      "var": "收盘价",
      "condition": [
        "最新"
      ]
    }
  ],
  "chain": true
}
```

### CX-06: 宁德时代今天的成交量、换手率、振幅、成交额

**类别**: 4 parallel metrics  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "成交量",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "宁德时代"
      ],
      "var": "换手率",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "宁德时代"
      ],
      "var": "振幅",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_004",
      "obj": [
        "宁德时代"
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

### CX-07: 上证指数今天的开盘价、收盘价、最高价、最低价、成交量

**类别**: 5 parallel metrics  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "上证指数"
      ],
      "var": "开盘价",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "上证指数"
      ],
      "var": "收盘价",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "上证指数"
      ],
      "var": "最高价",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_004",
      "obj": [
        "上证指数"
      ],
      "var": "最低价",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_005",
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

### CX-08: 茅台今天的PE、PB、PS、ROE、营收增长率

**类别**: 5 financial metrics  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "贵州茅台"
      ],
      "var": "PE",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "贵州茅台"
      ],
      "var": "PB",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "贵州茅台"
      ],
      "var": "PS",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_004",
      "obj": [
        "贵州茅台"
      ],
      "var": "ROE",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_005",
      "obj": [
        "贵州茅台"
      ],
      "var": "营收增长率",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

### CX-09: 沪深300、上证50、中证500今天的涨跌幅

**类别**: 3 indexes  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "沪深300"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "上证50"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "中证500"
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

### CX-10: 招商银行今年的净利润、营业收入、ROE、不良率

**类别**: 4 financial  
**状态**: ✅

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
        "今年以来"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "招商银行"
      ],
      "var": "营业收入",
      "condition": [
        "今年以来"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "招商银行"
      ],
      "var": "ROE",
      "condition": [
        "最近一个报告期"
      ]
    },
    {
      "req_id": "R_004",
      "obj": [
        "招商银行"
      ],
      "var": "不良率",
      "condition": [
        "最近一个报告期"
      ]
    }
  ],
  "chain": false
}
```

### CX-11: 宁德时代、比亚迪、长城汽车、上汽集团、广汽集团今天的涨跌幅

**类别**: 5 stocks, 1 metric  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代",
        "比亚迪",
        "长城汽车",
        "上汽集团",
        "广汽集团"
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

### CX-12: 贵州茅台、五粮液、泸州老窖、山西汾酒、洋河股份今天的股价

**类别**: 5 baijiu stocks, 1 metric  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "贵州茅台",
        "五粮液",
        "泸州老窖",
        "山西汾酒",
        "洋河股份"
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

### CX-13: 工商银行、建设银行、农业银行、中国银行、招商银行今天的涨跌幅

**类别**: 5 banks, 1 metric  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "工商银行",
        "建设银行",
        "农业银行",
        "中国银行",
        "招商银行"
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

### CX-14: 宁德时代、阳光电源、隆基绿能、通威股份、TCL中环今天的换手率

**类别**: 5 solar stocks  
**状态**: ⚠️ count/chain 不符

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代"
      ],
      "var": "换手率",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "阳光电源"
      ],
      "var": "换手率",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "隆基绿能"
      ],
      "var": "换手率",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_004",
      "obj": [
        "通威股份"
      ],
      "var": "换手率",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_005",
      "obj": [
        "TCL中环"
      ],
      "var": "换手率",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": false
}
```

### CX-15: 中国平安、中国人寿、中国太保、新华保险、中国人保今天的涨跌幅

**类别**: 5 insurance  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "中国平安",
        "中国人寿",
        "中国太保",
        "新华保险",
        "中国人保"
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

### CX-16: 宁德时代所属板块的龙头股以及比亚迪今天的涨跌幅

**类别**: chain + parallel mixed  
**状态**: ✅

```json
{
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
        "比亚迪"
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

### CX-17: 查一下茅台所在行业的平均PE和五粮液的PE

**类别**: chain + independent  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "茅台"
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
      "var": "平均PE",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "五粮液"
      ],
      "var": "PE",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": true
}
```

### CX-18: 沪深300、中证500、创业板指今天的涨跌幅和成交额

**类别**: 3 indexes * 2 metrics  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "沪深300"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_002",
      "obj": [
        "沪深300"
      ],
      "var": "成交额",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_003",
      "obj": [
        "中证500"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_004",
      "obj": [
        "中证500"
      ],
      "var": "成交额",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_005",
      "obj": [
        "创业板指"
      ],
      "var": "涨跌幅",
      "condition": [
        "今天"
      ]
    },
    {
      "req_id": "R_006",
      "obj": [
        "创业板指"
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

### CX-19: 宁德时代、比亚迪、长城汽车所属行业的板块涨跌幅

**类别**: 3 entities each chain  
**状态**: ⚠️ count/chain 不符

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "宁德时代",
        "比亚迪",
        "长城汽车"
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
      "var": "板块涨跌幅",
      "condition": [
        "今天"
      ]
    }
  ],
  "chain": true
}
```

### CX-20: 白酒板块、医药板块、新能源板块、银行板块、半导体板块今天的涨跌幅

**类别**: 5 sectors  
**状态**: ✅

```json
{
  "requests": [
    {
      "req_id": "R_001",
      "obj": [
        "白酒板块",
        "医药板块",
        "新能源板块",
        "银行板块",
        "半导体板块"
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
