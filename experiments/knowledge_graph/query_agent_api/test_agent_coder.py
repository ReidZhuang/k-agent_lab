#!/usr/bin/env python3
"""test_agent_coder — 全协议取数代码生成测试"""
import json, os, sys, time
_QA_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _QA_DIR)
from core.coder import codegen_loop

RESULTS_DIR = os.path.join(_QA_DIR, "data")
os.makedirs(RESULTS_DIR, exist_ok=True)

TEST_CASES = [
    {
        "id": "CG-01",
        "desc": "Tushare日线-涨跌幅",
        "route_result": {
            "req_id": "R_001", "query_id": "Q_test",
            "request": {"obj": ["宁德时代"], "var": "涨跌幅", "condition": ["今天"]},
            "route": {
                "field_id": "FIELD_QUOTE_PCT_CHG", "field_name": "个股涨跌幅",
                "api_column": "pct_chg", "data_type": "float", "unit": "%",
                "entity_type": "stock_code", "entity_value": "300750.SZ",
                "time_start": "20260715", "time_end": "20260715",
                "condition_text": "股票: 300750.SZ\n  指标: pct_chg\n  时间: 20260715 ~ 20260715",
            },
            "datasource": {"id": "DS_TUSHARE_DAILY", "protocol": "tushare"},
        },
    },
    {
        "id": "CG-02",
        "desc": "Tushare换手率",
        "route_result": {
            "req_id": "R_002", "query_id": "Q_test",
            "request": {"obj": ["宁德时代"], "var": "换手率", "condition": ["最近5天"]},
            "route": {
                "field_id": "FIELD_TURNOVER_RATE", "field_name": "换手率",
                "api_column": "turnover_rate", "data_type": "float", "unit": "%",
                "entity_type": "stock_code", "entity_value": "300750.SZ",
                "time_start": "20260711", "time_end": "20260715",
                "condition_text": "股票: 300750.SZ\n  指标: turnover_rate\n  时间: 20260711 ~ 20260715",
            },
            "datasource": {"id": "DS_TUSHARE_DAILY_BASIC", "protocol": "tushare"},
        },
    },
    {
        "id": "CG-03",
        "desc": "Akshare板块涨跌幅",
        "route_result": {
            "req_id": "R_003", "query_id": "Q_test",
            "request": {"obj": ["电池板块"], "var": "板块涨跌幅", "condition": ["今天"]},
            "route": {
                "field_id": "FIELD_SECTOR_PCT_CHG", "field_name": "板块涨跌幅",
                "api_column": "涨跌幅", "data_type": "float", "unit": "%",
                "entity_type": "sector_name", "entity_value": "电池",
                "time_start": "20260715", "time_end": "20260715",
                "condition_text": "板块: 电池\n  指标: 涨跌幅\n  时间: 今天",
            },
            "datasource": {"id": "DS_AKSHARE_SECTOR_THS", "protocol": "akshare"},
        },
    },
    {
        "id": "CG-04",
        "desc": "Tencent实时行情-涨跌幅",
        "route_result": {
            "req_id": "R_004", "query_id": "Q_test",
            "request": {"obj": ["宁德时代"], "var": "涨跌幅", "condition": ["今天"]},
            "route": {
                "field_id": "FIELD_QUOTE_PCT_CHG", "field_name": "个股涨跌幅",
                "api_column": "pct_chg", "data_type": "float", "unit": "%",
                "entity_type": "stock_code", "entity_value": "sz300750",
                "time_start": "", "time_end": "",
                "condition_text": "股票: sz300750\n  指标: pct_chg (索引32)\n  协议: Tencent HTTP GET",
            },
            "datasource": {"id": "DS_TENCENT_QUOTE", "protocol": "tencent"},
        },
    },
    {
        "id": "CG-05",
        "desc": "Levistock市场热度",
        "route_result": {
            "req_id": "R_005", "query_id": "Q_test",
            "request": {"obj": ["市场"], "var": "市场热度", "condition": ["今天"]},
            "route": {
                "field_id": "FIELD_LEVISTOCK_EMOTION", "field_name": "市场热度",
                "api_column": "market_degree", "data_type": "int", "unit": "0-100",
                "entity_type": "", "entity_value": "",
                "time_start": "", "time_end": "",
                "condition_text": "指标: market_degree",
            },
            "datasource": {"id": "DS_LEVISTOCK_EMOTION", "protocol": "levistock"},
        },
    },
    {
        "id": "CG-06",
        "desc": "Sina HTML利润表-营业收入",
        "route_result": {
            "req_id": "R_006", "query_id": "Q_test",
            "request": {"obj": ["宁德时代"], "var": "营业收入", "condition": ["最近一个季度"]},
            "route": {
                "field_id": "FIELD_INC_REVENUE", "field_name": "营业收入",
                "api_column": "revenue", "data_type": "float", "unit": "万元",
                "entity_type": "stock_code", "entity_value": "300750",
                "time_start": "", "time_end": "",
                "condition_text": "股票: 300750\n  指标: revenue\n  说明: HTML 行标签为'营业收入'",
            },
            "datasource": {"id": "DS_SINA_INCOME", "protocol": "html_scrape"},
        },
    },
    # ── 更多Tushare (A类) ──
    {
        "id": "CG-07",
        "desc": "Tushare利润表-净利润",
        "route_result": {
            "req_id": "R_007", "query_id": "Q_test",
            "request": {"obj": ["贵州茅台"], "var": "净利润", "condition": ["最近一个季度"]},
            "route": {
                "field_id": "FIELD_FS_NET_PROFIT", "field_name": "净利润",
                "api_column": "n_income", "data_type": "float", "unit": "亿元",
                "entity_type": "stock_code", "entity_value": "600519.SH",
                "time_start": "20260401", "time_end": "20260630",
                "condition_text": "股票: 600519.SH\n  指标: n_income\n  时间: 20260401 ~ 20260630",
            },
            "datasource": {"id": "DS_TUSHARE_INCOME", "protocol": "tushare"},
        },
    },
    {
        "id": "CG-08",
        "desc": "Tushare财务指标-ROE",
        "route_result": {
            "req_id": "R_008", "query_id": "Q_test",
            "request": {"obj": ["招商银行"], "var": "ROE", "condition": ["最近一个季度"]},
            "route": {
                "field_id": "FIELD_FIN_ROE_DILUTED", "field_name": "ROE(摊薄)",
                "api_column": "roe_dt", "data_type": "float", "unit": "%",
                "entity_type": "stock_code", "entity_value": "600036.SH",
                "time_start": "20260101", "time_end": "20260331",
                "condition_text": "股票: 600036.SH\n  指标: roe_dt\n  时间: 20260101 ~ 20260331 (Q1)",
            },
            "datasource": {"id": "DS_TUSHARE_FINA_IND", "protocol": "tushare"},
        },
    },
    {
        "id": "CG-09",
        "desc": "Tushare资金流向-大单净买入",
        "route_result": {
            "req_id": "R_009", "query_id": "Q_test",
            "request": {"obj": ["宁德时代"], "var": "大单净买入", "condition": ["今天"]},
            "route": {
                "field_id": "FIELD_MF_BUY_LG_VOL", "field_name": "大单买入量",
                "api_column": "buy_lg_vol", "data_type": "float", "unit": "手",
                "entity_type": "stock_code", "entity_value": "300750.SZ",
                "time_start": "20260715", "time_end": "20260715",
                "condition_text": "股票: 300750.SZ\n  指标: buy_lg_vol\n  时间: 20260715",
            },
            "datasource": {"id": "DS_TUSHARE_MONEYFLOW", "protocol": "tushare"},
        },
    },
    {
        "id": "CG-10",
        "desc": "Tushare涨跌停价",
        "route_result": {
            "req_id": "R_010", "query_id": "Q_test",
            "request": {"obj": ["中国平安"], "var": "涨停价", "condition": ["今天"]},
            "route": {
                "field_id": "FIELD_LIMIT_UP_PRICE", "field_name": "涨停价",
                "api_column": "up_limit", "data_type": "float", "unit": "元",
                "entity_type": "stock_code", "entity_value": "601318.SH",
                "time_start": "20260715", "time_end": "20260715",
                "condition_text": "股票: 601318.SH\n  指标: up_limit\n  时间: 20260715",
            },
            "datasource": {"id": "DS_TUSHARE_STK_LIMIT", "protocol": "tushare"},
        },
    },
    # ── 更多Akshare (B类) ──
    {
        "id": "CG-11",
        "desc": "Akshare板块成分股",
        "route_result": {
            "req_id": "R_011", "query_id": "Q_test",
            "request": {"obj": ["电池板块"], "var": "板块成分股", "condition": ["今天"]},
            "route": {
                "field_id": "FIELD_SECTOR_CONS", "field_name": "板块成分股",
                "api_column": "股票代码", "data_type": "string", "unit": "",
                "entity_type": "sector_name", "entity_value": "电池",
                "time_start": "", "time_end": "",
                "condition_text": "板块: 电池\n  指标: 股票代码",
            },
            "datasource": {"id": "DS_AKSHARE_SECTOR_CONS", "protocol": "akshare"},
        },
    },
    # ── 更多Levistock (C类) ──
    {
        "id": "CG-12",
        "desc": "Levistock板块行情",
        "route_result": {
            "req_id": "R_012", "query_id": "Q_test",
            "request": {"obj": ["板块"], "var": "涨跌幅", "condition": ["今天"]},
            "route": {
                "field_id": "FIELD_LK_SECTOR_PCT", "field_name": "板块涨跌幅",
                "api_column": "change_pct", "data_type": "float", "unit": "%",
                "entity_type": "", "entity_value": "",
                "time_start": "", "time_end": "",
                "condition_text": "指标: change_pct",
            },
            "datasource": {"id": "DS_LEVISTOCK_SECTOR", "protocol": "levistock"},
        },
    },
    # ── 更多HTTP (E类) ──
    {
        "id": "CG-13",
        "desc": "新浪实时行情-最新价",
        "route_result": {
            "req_id": "R_013", "query_id": "Q_test",
            "request": {"obj": ["宁德时代"], "var": "最新价", "condition": ["今天"]},
            "route": {
                "field_id": "FIELD_SINA_PRICE", "field_name": "最新价",
                "api_column": "price(索引3)", "data_type": "float", "unit": "元",
                "entity_type": "stock_code", "entity_value": "sz300750",
                "time_start": "", "time_end": "",
                "condition_text": "股票: sz300750\n  指标: price (索引3)\n  协议: Sina HTTP GET",
            },
            "datasource": {"id": "DS_SINA_QUOTE", "protocol": "sina"},
        },
    },
    # ── 更多HTML Scrape (F类) ──
    {
        "id": "CG-14",
        "desc": "Sina HTML资产负债表-总资产",
        "route_result": {
            "req_id": "R_014", "query_id": "Q_test",
            "request": {"obj": ["宁德时代"], "var": "总资产", "condition": ["最近一个季度"]},
            "route": {
                "field_id": "FIELD_BS_TOTAL_ASSETS", "field_name": "资产总计",
                "api_column": "total_assets", "data_type": "float", "unit": "万元",
                "entity_type": "stock_code", "entity_value": "300750",
                "time_start": "", "time_end": "",
                "condition_text": "股票: 300750\n  指标: total_assets\n  说明: HTML 行标签为'资产总计'",
            },
            "datasource": {"id": "DS_SINA_BALANCE", "protocol": "html_scrape"},
        },
    },
    {
        "id": "CG-15",
        "desc": "Sina HTML现金流-经营现金流",
        "route_result": {
            "req_id": "R_015", "query_id": "Q_test",
            "request": {"obj": ["宁德时代"], "var": "经营现金流", "condition": ["最近一个季度"]},
            "route": {
                "field_id": "FIELD_CF_OPER_FLOW", "field_name": "经营活动现金流净额",
                "api_column": "op_cash_flow", "data_type": "float", "unit": "万元",
                "entity_type": "stock_code", "entity_value": "300750",
                "time_start": "", "time_end": "",
                "condition_text": "股票: 300750\n  指标: op_cash_flow\n  说明: HTML 行标签为'经营活动产生的现金流量净额'",
            },
            "datasource": {"id": "DS_SINA_CASHFLOW", "protocol": "html_scrape"},
        },
    },

    {
        "id": "CG-16",
        "desc": "交易日历",
        "route_result": {
            "req_id": "R_016", "query_id": "Q_test",
            "request": {"obj": ["上交所"], "var": "交易日", "condition": ["今天"]},
            "route": {"field_id": "FIELD_TRADE_CAL_IS_OPEN", "field_name": "是否交易日",
                      "api_column": "is_open", "data_type": "int", "unit": "",
                      "entity_value": "", "time_start": "20260715", "time_end": "20260715",
                      "condition_text": "接口: trade_cal"},
            "datasource": {"id": "DS_TUSHARE_TRADE_CAL", "protocol": "tushare"}
        }
    },
    {
        "id": "CG-17",
        "desc": "股东户数",
        "route_result": {
            "req_id": "R_017", "query_id": "Q_test",
            "request": {"obj": ["工商银行"], "var": "股东户数", "condition": ["最新"]},
            "route": {"field_id": "FIELD_STK_HOLDERNUMBER_HOLDER_NUM", "field_name": "股东户数",
                      "api_column": "holder_num", "data_type": "int", "unit": "户",
                      "entity_value": "601398.SH", "time_start": "20260401", "time_end": "20260630",
                      "condition_text": "股票: 601398.SH"},
            "datasource": {"id": "DS_TUSHARE_STK_HOLDERNUMBER", "protocol": "tushare"}
        }
    },
    {
        "id": "CG-18",
        "desc": "限售股解禁",
        "route_result": {
            "req_id": "R_018", "query_id": "Q_test",
            "request": {"obj": ["格力电器"], "var": "解禁数量", "condition": ["最近一个月"]},
            "route": {"field_id": "FIELD_SHARE_FLOAT_FLOAT_SHARE", "field_name": "解禁数量",
                      "api_column": "float_share", "data_type": "float", "unit": "股",
                      "entity_value": "000651.SZ", "time_start": "", "time_end": "",
                      "condition_text": "股票: 000651.SZ\n  指标: float_share"},
            "datasource": {"id": "DS_TUSHARE_SHARE_FLOAT", "protocol": "tushare"}
        }
    },
    {
        "id": "CG-19",
        "desc": "指数权重",
        "route_result": {
            "req_id": "R_019", "query_id": "Q_test",
            "request": {"obj": ["沪深300"], "var": "成分股权重", "condition": ["最新"]},
            "route": {"field_id": "FIELD_INDEX_WEIGHT_WEIGHT", "field_name": "权重",
                      "api_column": "weight", "data_type": "float", "unit": "%",
                      "entity_value": "399300.SZ", "time_start": "20260601", "time_end": "20260630",
                      "condition_text": "指数: 399300.SZ\n  指标: weight\n  时间: 20260601 ~ 20260630"},
            "datasource": {"id": "DS_TUSHARE_INDEX_WEIGHT", "protocol": "tushare"}
        }
    },
    {
        "id": "CG-20",
        "desc": "国际指数收盘",
        "route_result": {
            "req_id": "R_020", "query_id": "Q_test",
            "request": {"obj": ["标普500"], "var": "指数收盘价", "condition": ["昨天"]},
            "route": {"field_id": "FIELD_INDEX_GLOBAL_CLOSE", "field_name": "收盘价",
                      "api_column": "close", "data_type": "float", "unit": "",
                      "entity_value": ".SPX", "time_start": "20260714", "time_end": "20260714",
                      "condition_text": "指数: .SPX"},
            "datasource": {"id": "DS_TUSHARE_INDEX_GLOBAL", "protocol": "tushare"}
        }
    },

]

def main():

    print("=" * 70)
    print("  agent_coder 取数代码生成测试（全协议）")
    print(f"  模型: {os.environ.get('OLLAMA_MODEL', 'qwen2.5:7b')}")
    print("=" * 70)

    pass_count = 0
    fail_count = 0
    results = []

    for tc in TEST_CASES:
        print(f"\n{'─'*50}")
        print(f"  [{tc['id']}] {tc['desc']}")
        print(f"{'─'*50}")

        t0 = time.time()
        result = codegen_loop(tc["route_result"])
        elapsed = time.time() - t0

        if result["success"]:
            print(f"\n  ✅ 取数成功: _result = {result['result']} ({elapsed:.1f}s)")
            pass_count += 1
        else:
            print(f"\n  ❌ 取数失败: {result.get('error', '')[:200]} ({elapsed:.1f}s)")
            fail_count += 1

        results.append({
            "id": tc["id"], "desc": tc["desc"],
            "success": result["success"],
            "result": result.get("result"),
            "error": result.get("error", ""),
            "time": round(elapsed, 1),
        })

    print(f"\n{'='*70}")
    print(f"  汇总: {pass_count}/{len(TEST_CASES)} 通过, {fail_count} 失败")
    print(f"{'='*70}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"coder_test_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"cases": results}, f, ensure_ascii=False, indent=2, default=str)
    print(f"  已保存: {path}")


if __name__ == "__main__":
    main()
