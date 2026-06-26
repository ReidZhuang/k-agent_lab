"""搜索后端 —— 使用扩展数据集进行大规模测试"""
import re
from expanded_datasets import (
    R1_CATL_FINANCIAL, R2_STORAGE_DEEP, R3_BYD_COMPARE,
    R4_INDUSTRY_LANDSCAPE, R5_TECH_ROADMAP, R6_POLICY_GEOPOLITICS,
)

MOCK_DB = {
    "宁德时代 2024 财报 营收 净利润": R1_CATL_FINANCIAL,
    "宁德时代 动力电池 装机量 市占率": R1_CATL_FINANCIAL,
    "宁德时代 研发 技术 固态 凝聚态": R1_CATL_FINANCIAL,
    "宁德时代 海外 欧洲 产能": R1_CATL_FINANCIAL,
    "宁德时代 储能 2024 毛利率 800亿": R2_STORAGE_DEEP,
    "宁德时代 天恒 储能 系统 技术": R2_STORAGE_DEEP,
    "宁德时代 比亚迪 对比 动力 储能": R3_BYD_COMPARE,
    "比亚迪 2024 电池 营收 对比": R3_BYD_COMPARE,
    "全球 动力电池 竞争 格局 2025": R4_INDUSTRY_LANDSCAPE,
    "行业 产能 过剩 集中度 电池": R4_INDUSTRY_LANDSCAPE,
    "固态电池 下一代 技术 路线": R5_TECH_ROADMAP,
    "钠离子电池 LMFP 锂硫 电池": R5_TECH_ROADMAP,
    "欧盟 电池法 碳关税 IRA 政策": R6_POLICY_GEOPOLITICS,
    "电池 地缘政治 供应链 风险": R6_POLICY_GEOPOLITICS,
}
DEFAULT_RESULT = R1_CATL_FINANCIAL

def web_search(query: str, **kwargs) -> str:
    for key, data in MOCK_DB.items():
        if key in query or query in key:
            return data
    keywords = ["宁德时代", "比亚迪", "储能", "动力电池", "财报", "竞争", "技术", "固态", "政策"]
    scores = {}
    for key, data in MOCK_DB.items():
        score = sum(1 for kw in keywords if kw in query and kw in key)
        if score > 0: scores[key] = score
    if scores:
        return MOCK_DB[max(scores, key=scores.get)]
    return DEFAULT_RESULT

def extract_sections(text: str) -> list[dict]: return []
def count_chars(text: str) -> int: return len(text)
