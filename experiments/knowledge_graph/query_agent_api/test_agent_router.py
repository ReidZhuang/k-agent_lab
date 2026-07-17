#!/usr/bin/env python3
"""
test_agent_router v3 — 双检索 + LLM 一次筛选

Python 用关键字+embedding 双路由得到候选 → LLM 根据属性一次选出正确 field_id
"""
import json, os, sys, re, time
from openai import OpenAI

_QA_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _QA_DIR)

from core import build_prompt
from core.route_tool import get_route_tool

RESULTS_DIR = os.path.join(_QA_DIR, "data")
os.makedirs(RESULTS_DIR, exist_ok=True)

_client = OpenAI(
    base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1",
    api_key="ollama",
)
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

route_tool = get_route_tool()

TEST_CASES = [
    {"id": "RR-01", "req": {"obj": ["宁德时代"], "var": "涨跌幅", "condition": ["今天"]}, "expect_id": "FIELD_QUOTE_PCT_CHG"},
    {"id": "RR-02", "req": {"obj": ["贵州茅台"], "var": "成交量", "condition": ["今天"]}, "expect_id": "FIELD_QUOTE_VOL"},
    {"id": "RR-03", "req": {"obj": ["上证指数"], "var": "涨跌幅", "condition": ["今天"]}, "expect_id": "FIELD_INDEX_PCT_CHG"},
    {"id": "RR-04", "req": {"obj": ["电池板块"], "var": "板块涨跌幅", "condition": ["今天"]}, "expect_id": "FIELD_SECTOR_PCT_CHG"},
    {"id": "RR-05", "req": {"obj": ["宁德时代"], "var": "最高价", "condition": ["今天"]}, "expect_id": "FIELD_QUOTE_HIGH"},
    {"id": "RR-06", "req": {"obj": ["宁德时代"], "var": "换手率", "condition": ["最近5天"]}, "expect_id": "FIELD_TURNOVER_RATE"},
    {"id": "RR-07", "req": {"obj": ["中国平安"], "var": "市盈率", "condition": ["今天"]}, "expect_id": "FIELD_PE_TTM"},
    {"id": "RR-08", "req": {"obj": ["宁德时代"], "var": "板块", "condition": ["今天"]}, "expect_id": "FIELD_DC_DAILY_CATEGORY"},
    {"id": "RR-09", "req": {"obj": ["宁德时代", "比亚迪"], "var": "涨跌幅", "condition": ["今天"]}, "expect_id": "FIELD_QUOTE_PCT_CHG"},
    {"id": "RR-10", "req": {"obj": ["北向资金"], "var": "资金流向", "condition": ["最近一个月"]}, "expect_id": "FIELD_NORTH_NET"},
    {"id": "RR-11", "req": {"obj": ["恒生指数"], "var": "收盘价", "condition": ["昨天"]}, "expect_id": "FIELD_INDEX_PRICE"},
    {"id": "RR-12", "req": {"obj": ["宁德时代"], "var": "股价", "condition": ["今天"]}, "expect_id": ""},
    # ── 20 个全新测试（不重复已有实体+变量组合）──
    {"id": "RR-13", "req": {"obj": ["万科A"], "var": "最低价", "condition": ["今天"]}, "expect_id": "FIELD_QUOTE_LOW"},
    {"id": "RR-14", "req": {"obj": ["格力电器"], "var": "开盘价", "condition": ["今天"]}, "expect_id": "FIELD_QUOTE_OPEN"},
    {"id": "RR-15", "req": {"obj": ["东方财富"], "var": "成交额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-16", "req": {"obj": ["中国平安"], "var": "涨跌额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-17", "req": {"obj": ["招商银行"], "var": "每股净资产", "condition": ["今天"]}, "expect_id": "FIELD_FIN_BPS"},
    {"id": "RR-18", "req": {"obj": ["海康威视"], "var": "市净率", "condition": ["今天"]}, "expect_id": "FIELD_PB"},
    {"id": "RR-19", "req": {"obj": ["大秦铁路"], "var": "股息率", "condition": ["今天"]}, "expect_id": "FIELD_DIVIDEND_YIELD"},
    {"id": "RR-20", "req": {"obj": ["半导体板块"], "var": "板块成交额", "condition": ["今天"]}, "expect_id": "FIELD_SECTOR_AMOUNT"},
    {"id": "RR-21", "req": {"obj": ["银行板块"], "var": "板块振幅", "condition": ["今天"]}, "expect_id": "FIELD_SECTOR_AMPLITUDE"},
    {"id": "RR-22", "req": {"obj": ["银行板块"], "var": "行业平均PE", "condition": ["今天"]}, "expect_id": "FIELD_VAL_IND_PE"},
    {"id": "RR-23", "req": {"obj": ["白酒板块"], "var": "行业平均ROE", "condition": ["今天"]}, "expect_id": "FIELD_VAL_IND_ROE"},
    {"id": "RR-24", "req": {"obj": ["中国"], "var": "综合PMI", "condition": ["最新"]}, "expect_id": "FIELD_MACRO_COMPOSITE_PMI"},
    {"id": "RR-25", "req": {"obj": ["中国"], "var": "CPI环比", "condition": ["最新"]}, "expect_id": "FIELD_MACRO_CPI_MOM"},
    {"id": "RR-26", "req": {"obj": ["贵州茅台"], "var": "北向资金净流入", "condition": ["最近一个月"]}, "expect_id": "FIELD_NORTH_NET"},
    {"id": "RR-27", "req": {"obj": ["创业板指"], "var": "指数成交量", "condition": ["今天"]}, "expect_id": "FIELD_INDEX_VOL"},
    {"id": "RR-28", "req": {"obj": ["科创50"], "var": "指数涨跌幅", "condition": ["今天"]}, "expect_id": "FIELD_INDEX_PCT_CHG"},
    {"id": "RR-29", "req": {"obj": ["五粮液"], "var": "K线收盘价", "condition": ["今天"]}, "expect_id": "FIELD_KLINE_CLOSE"},
    {"id": "RR-30", "req": {"obj": ["海康威视"], "var": "应收账款周转率", "condition": ["最近一个季度"]}, "expect_id": "FIELD_FIN_AR_TURN"},
    {"id": "RR-31", "req": {"obj": ["比亚迪"], "var": "涨跌额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-32", "req": {"obj": ["交通银行"], "var": "每股收益", "condition": ["最近一个季度"]}, "expect_id": ""},
    # ── 40 个新测试 ──
    {"id": "RR-33", "req": {"obj": ["恒瑞医药"], "var": "涨跌幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-34", "req": {"obj": ["迈瑞医疗"], "var": "成交量", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-35", "req": {"obj": ["药明康德"], "var": "最高价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-36", "req": {"obj": ["中兴通讯"], "var": "最低价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-37", "req": {"obj": ["京东方A"], "var": "成交额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-38", "req": {"obj": ["科大讯飞"], "var": "涨跌额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-39", "req": {"obj": ["顺丰控股"], "var": "换手率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-40", "req": {"obj": ["伊利股份"], "var": "市盈率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-41", "req": {"obj": ["贵州茅台"], "var": "毛利率", "condition": ["最近一个季度"]}, "expect_id": "FIELD_FIN_GROSS_MARGIN"},
    {"id": "RR-42", "req": {"obj": ["海康威视"], "var": "存货周转率", "condition": ["最近一个季度"]}, "expect_id": "FIELD_FIN_INV_TURN"},
    {"id": "RR-43", "req": {"obj": ["招商银行"], "var": "总资产周转率", "condition": ["最近一个季度"]}, "expect_id": "FIELD_FIN_ASSETS_TURN"},
    {"id": "RR-44", "req": {"obj": ["万科A"], "var": "资产负债率", "condition": ["最近一个季度"]}, "expect_id": "FIELD_FIN_DEBT_RATIO"},
    {"id": "RR-45", "req": {"obj": ["中国平安"], "var": "ROIC", "condition": ["最近一个季度"]}, "expect_id": "FIELD_FIN_ROIC"},
    {"id": "RR-46", "req": {"obj": ["泸州老窖"], "var": "K线最高价", "condition": ["昨天"]}, "expect_id": "FIELD_KLINE_HIGH"},
    {"id": "RR-47", "req": {"obj": ["山西汾酒"], "var": "K线最低价", "condition": ["昨天"]}, "expect_id": "FIELD_KLINE_LOW"},
    {"id": "RR-48", "req": {"obj": ["洋河股份"], "var": "K线成交量", "condition": ["昨天"]}, "expect_id": "FIELD_KLINE_VOL"},
    {"id": "RR-49", "req": {"obj": ["长春高新"], "var": "K线成交额", "condition": ["昨天"]}, "expect_id": "FIELD_KLINE_AMOUNT"},
    {"id": "RR-50", "req": {"obj": ["医疗器械板块"], "var": "板块涨跌幅", "condition": ["今天"]}, "expect_id": "FIELD_SECTOR_PCT_CHG"},
    {"id": "RR-51", "req": {"obj": ["芯片板块"], "var": "板块换手率", "condition": ["今天"]}, "expect_id": "FIELD_THS_DAILY_TURNOVER_RATE"},
    {"id": "RR-52", "req": {"obj": ["人工智能板块"], "var": "板块振幅", "condition": ["今天"]}, "expect_id": "FIELD_SECTOR_AMPLITUDE"},
    {"id": "RR-53", "req": {"obj": ["沪深300"], "var": "涨跌幅", "condition": ["今天"]}, "expect_id": "FIELD_INDEX_PCT_CHG"},
    {"id": "RR-54", "req": {"obj": ["中证500"], "var": "成交量", "condition": ["今天"]}, "expect_id": "FIELD_INDEX_VOL"},
    {"id": "RR-55", "req": {"obj": ["深证成指"], "var": "收盘价", "condition": ["昨天"]}, "expect_id": "FIELD_INDEX_PRICE"},
    {"id": "RR-56", "req": {"obj": ["沪深300"], "var": "指数开盘价", "condition": ["今天"]}, "expect_id": "FIELD_INDEX_OPEN"},
    {"id": "RR-57", "req": {"obj": ["宁德时代"], "var": "龙虎榜净买入", "condition": ["最近5天"]}, "expect_id": "FIELD_LHB_NET"},
    {"id": "RR-58", "req": {"obj": ["宁德时代"], "var": "龙虎榜买入额", "condition": ["最近5天"]}, "expect_id": "FIELD_LHB_BUY"},
    {"id": "RR-59", "req": {"obj": ["中国平安"], "var": "港股通(沪)", "condition": ["今天"]}, "expect_id": "FIELD_NORTH_GGT_SS"},
    {"id": "RR-60", "req": {"obj": ["比亚迪"], "var": "港股通(深)", "condition": ["今天"]}, "expect_id": "FIELD_NORTH_GGT_SZ"},
    {"id": "RR-61", "req": {"obj": ["中国中免"], "var": "股价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-62", "req": {"obj": ["双汇发展"], "var": "市净率", "condition": ["今天"]}, "expect_id": "FIELD_PB"},
    {"id": "RR-63", "req": {"obj": ["中国神华"], "var": "股息率", "condition": ["今天"]}, "expect_id": "FIELD_DIVIDEND_YIELD"},
    {"id": "RR-64", "req": {"obj": ["中国建筑"], "var": "涨跌幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-65", "req": {"obj": ["三一重工"], "var": "换手率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-66", "req": {"obj": ["紫金矿业"], "var": "最高价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-67", "req": {"obj": ["万华化学"], "var": "成交额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-68", "req": {"obj": ["立讯精密"], "var": "涨跌额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-69", "req": {"obj": ["海天味业"], "var": "市盈率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-70", "req": {"obj": ["牧原股份"], "var": "成交量", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-71", "req": {"obj": ["中信证券"], "var": "涨停价", "condition": ["今天"]}, "expect_id": "FIELD_LIMIT_UP_PRICE"},
    {"id": "RR-72", "req": {"obj": ["保利发展"], "var": "跌停价", "condition": ["今天"]}, "expect_id": "FIELD_LIMIT_DOWN_PRICE"},

    # ── 40 个最终轮测试（全新实体+变量组合）──
    {"id": "RR-73", "req": {"obj": ["隆基绿能"], "var": "涨跌幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-74", "req": {"obj": ["通威股份"], "var": "换手率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-75", "req": {"obj": ["中芯国际"], "var": "成交额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-76", "req": {"obj": ["北方华创"], "var": "最高价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-77", "req": {"obj": ["兆易创新"], "var": "最低价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-78", "req": {"obj": ["金山办公"], "var": "市盈率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-79", "req": {"obj": ["云南白药"], "var": "市净率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-80", "req": {"obj": ["中国核电"], "var": "成交量", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-81", "req": {"obj": ["海尔智家"], "var": "收盘价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-82", "req": {"obj": ["中国太保"], "var": "涨跌幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-83", "req": {"obj": ["青岛啤酒"], "var": "市盈率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-84", "req": {"obj": ["海螺水泥"], "var": "成交额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-85", "req": {"obj": ["中微公司"], "var": "涨跌额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-86", "req": {"obj": ["华大基因"], "var": "换手率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-87", "req": {"obj": ["复星医药"], "var": "最高价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-88", "req": {"obj": ["中国人寿"], "var": "成交量", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-89", "req": {"obj": ["中航光电"], "var": "最低价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-90", "req": {"obj": ["中国联通"], "var": "涨跌幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-91", "req": {"obj": ["TCL科技"], "var": "成交额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-92", "req": {"obj": ["宝钢股份"], "var": "换手率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-93", "req": {"obj": ["宁德时代"], "var": "昨收价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-94", "req": {"obj": ["贵州茅台"], "var": "市销率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-95", "req": {"obj": ["招商银行"], "var": "每股资本公积", "condition": ["最近一个季度"]}, "expect_id": ""},
    {"id": "RR-96", "req": {"obj": ["恒瑞医药"], "var": "毛利率", "condition": ["最近一个季度"]}, "expect_id": ""},
    {"id": "RR-97", "req": {"obj": ["长江电力"], "var": "股息率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-98", "req": {"obj": ["创业板指"], "var": "指数开盘价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-99", "req": {"obj": ["沪深300"], "var": "指数成交量", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-100", "req": {"obj": ["北向资金"], "var": "北向资金净流入", "condition": ["最近一个月"]}, "expect_id": ""},
    {"id": "RR-101", "req": {"obj": ["半导体板块"], "var": "板块换手率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-102", "req": {"obj": ["宁德时代"], "var": "K线涨跌幅", "condition": ["昨天"]}, "expect_id": ""},
    {"id": "RR-103", "req": {"obj": ["中国建筑"], "var": "涨幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-104", "req": {"obj": ["中国神华"], "var": "跌幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-105", "req": {"obj": ["长江电力"], "var": "每股现金流", "condition": ["最近一个季度"]}, "expect_id": ""},
    {"id": "RR-106", "req": {"obj": ["比亚迪"], "var": "涨幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-107", "req": {"obj": ["五粮液"], "var": "跌幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-108", "req": {"obj": ["贵州茅台"], "var": "营业利润", "condition": ["最近一个季度"]}, "expect_id": ""},
    {"id": "RR-109", "req": {"obj": ["中国平安"], "var": "利润总额", "condition": ["最近一个季度"]}, "expect_id": ""},
    {"id": "RR-110", "req": {"obj": ["宁德时代"], "var": "研发费用", "condition": ["最近一个季度"]}, "expect_id": ""},
    {"id": "RR-111", "req": {"obj": ["五粮液"], "var": "销售费用", "condition": ["最近一个季度"]}, "expect_id": ""},
    {"id": "RR-112", "req": {"obj": ["海康威视"], "var": "管理费用", "condition": ["最近一个季度"]}, "expect_id": ""},
    {"id": "RR-113", "req": {"obj": ["中国"], "var": "GDP增速", "condition": ["最新"]}, "expect_id": ""},
    {"id": "RR-114", "req": {"obj": ["中国"], "var": "CPI同比", "condition": ["最新"]}, "expect_id": ""},
    {"id": "RR-115", "req": {"obj": ["中国"], "var": "制造业PMI", "condition": ["最新"]}, "expect_id": ""},
    {"id": "RR-116", "req": {"obj": ["中国"], "var": "社会融资规模", "condition": ["最新"]}, "expect_id": ""},
    {"id": "RR-117", "req": {"obj": ["300750.SZ"], "var": "神奇九转", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-118", "req": {"obj": ["宁德时代"], "var": "股票代码", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-119", "req": {"obj": ["宁德时代"], "var": "上市日期", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-120", "req": {"obj": ["平安银行"], "var": "所属行业", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-121", "req": {"obj": ["宁德时代"], "var": "龙虎榜卖出额", "condition": ["最近5天"]}, "expect_id": ""},
    {"id": "RR-122", "req": {"obj": ["上证指数"], "var": "指数成分股", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-123", "req": {"obj": ["工商银行"], "var": "股东户数", "condition": ["最近一个季度"]}, "expect_id": ""},
    {"id": "RR-124", "req": {"obj": ["格力电器"], "var": "限售股解禁", "condition": ["最近一个月"]}, "expect_id": ""},
    {"id": "RR-125", "req": {"obj": ["银行板块"], "var": "万申板块涨跌幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-126", "req": {"obj": ["半导体板块"], "var": "中信板块涨跌幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-127", "req": {"obj": ["新能源板块"], "var": "同花顺板块涨跌幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-128", "req": {"obj": ["宁德时代"], "var": "散户净流入", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-129", "req": {"obj": ["隆基绿能"], "var": "超大单净流入", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-130", "req": {"obj": ["全市场"], "var": "大盘资金流向", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-131", "req": {"obj": ["宁德时代"], "var": "复权因子", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-132", "req": {"obj": ["贵州茅台"], "var": "技术因子涨跌幅", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-133", "req": {"obj": ["中国平安"], "var": "市盈率TTM", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-134", "req": {"obj": ["全市场"], "var": "融资余额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-135", "req": {"obj": ["全市场"], "var": "融券余额", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-136", "req": {"obj": ["宁德时代"], "var": "融资融券标的", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-137", "req": {"obj": ["贵州茅台"], "var": "前十大股东", "condition": ["最近一个季度"]}, "expect_id": ""},
    {"id": "RR-138", "req": {"obj": ["招商银行"], "var": "机构调研记录", "condition": ["最近一个月"]}, "expect_id": ""},
    {"id": "RR-139", "req": {"obj": ["腾讯控股"], "var": "港股通持股", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-140", "req": {"obj": ["浦发转债"], "var": "转债收盘价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-141", "req": {"obj": ["浦发转债"], "var": "转股溢价率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-142", "req": {"obj": ["浦发转债"], "var": "纯债价值", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-143", "req": {"obj": ["螺纹钢"], "var": "期货收盘价", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-144", "req": {"obj": ["黄金"], "var": "期货持仓量", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-145", "req": {"obj": ["美国"], "var": "国债收益率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-146", "req": {"obj": ["美国"], "var": "长期国债利率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-147", "req": {"obj": ["浦发转债"], "var": "强赎条款", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-148", "req": {"obj": ["浦发转债"], "var": "回售条款", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-149", "req": {"obj": ["招商银行"], "var": "股息率", "condition": ["今天"]}, "expect_id": ""},
    {"id": "RR-150", "req": {"obj": ["中国平安"], "var": "每股股利", "condition": ["最近一年"]}, "expect_id": ""},
    {"id": "RR-151", "req": {"obj": ["宁德时代"], "var": "大股东持股比例", "condition": ["最近一个季度"]}, "expect_id": ""},
    {"id": "RR-152", "req": {"obj": ["沪深300"], "var": "指数权重", "condition": ["今天"]}, "expect_id": ""},
]


def run_test(tc: dict) -> dict:
    req = tc["req"]
    var = req["var"]
    keywords = [var]

    t0 = time.time()

    # Python 双检索
    candidates = route_tool.hybrid_query(keywords)

    # 构造 LLM 输入
    system_prompt = build_prompt("agent_router", {"route_expert"})
    user_prompt = (
        f"## 取数请求\n"
        f"```json\n{json.dumps(req, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 路由候选字段\n"
        f"```json\n{json.dumps(candidates, ensure_ascii=False, indent=2)}\n```\n\n"
        f"请从以上候选字段中选出一个最匹配的，只输出字段 ID。"
    )

    try:
        resp = _client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.1,
            max_tokens=256,
        )
        raw = resp.choices[0].message.content or ""
    except Exception as e:
        return {"success": False, "error": str(e), "time": time.time() - t0}

    elapsed = time.time() - t0
    field_ids = re.findall(r'FIELD_[A-Z_]+', raw)
    chosen = field_ids[0] if field_ids else ""

    return {
        "success": bool(chosen),
        "chosen_id": chosen,
        "candidates_count": len(candidates),
        "time": round(elapsed, 1),
        "raw": raw.strip()[:200],
    }


if __name__ == "__main__":
    print(f"{'='*70}")
    print(f"  🧪 agent_router v3 — 双检索 + LLM 筛选")
    print(f"  模型: {MODEL}")
    print(f"{'='*70}")

    pass_count = 0
    fail_count = 0
    results = []

    for tc in TEST_CASES:
        req = tc["req"]
        print(f"\n{'─'*50}")
        print(f"  [{tc['id']}] var={req['var']}, obj={req['obj']}")

        r = run_test(tc)

        expect = tc["expect_id"]
        if r["success"] and (expect == "" or r["chosen_id"] == expect):
            print(f"  ✅ 通过: {r['chosen_id']} ({r['time']}s, 候选{r['candidates_count']}个)")
            pass_count += 1
        else:
            exp_str = expect if expect else "(灵活)"
            print(f"  ❌ 失败: 期望 {exp_str}, 实际 {r.get('chosen_id', '(空)')} ({r['time']}s, 候选{r['candidates_count']}个)")
            print(f"     回复: {r.get('raw', '')}")
            fail_count += 1

        results.append({"id": tc["id"], "req": req, "result": r, "expect": expect})

    print(f"\n{'='*70}")
    print(f"  汇总: {pass_count}/{len(TEST_CASES)} 通过, {fail_count} 失败")
    print(f"{'='*70}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESULTS_DIR, f"router_v3_test_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"model": MODEL, "cases": results}, f, ensure_ascii=False, indent=2, default=str)
    print(f"  已保存: {path}")
