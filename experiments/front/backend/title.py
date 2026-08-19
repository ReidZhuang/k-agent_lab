"""
「保存成文档」文件名生成 — 轻量无 LLM 的 query 主题总结

用 jieba 的 TextRank 从用户 query 抽取核心关键词(无监督、通用、不绑定股票/板块),
拼成文件名。TextRank 抽不出(短句/无实义词)时回退到 query 原文截断。

依赖: jieba(已装入 conda stock_agent 环境, 清华源)
"""
import re

import jieba.analyse as ja

# 文件名里不允许出现的字符, 直接用空替换(与后端 explorer_write 清洗规则一致)
_ILLEGAL = re.compile(r"[\\/:*?\"<>|\n\r\t]+")
# 无意义的引导/语气词, TextRank 自身会去停用词, 这里兜底再做一次开头清洗
_LEAD_NOISE = re.compile(
    r"^(请|帮我|麻烦|你|能不能|能不能帮我|帮我一下|帮我看|看下|看一下|查一下|查查|"
    r"查一查|分析一下|分析下|简单聊聊|写一篇|梳理一下|讲讲|介绍一下|"
    r"今天|现在|最近|本周|近期|目前)"
)


def build_document_title(query: str, force_length: int = 24) -> str:
    """从用户 query 生成文档标题(不含日期前缀)。

    优先 TextRank 关键词拼接; 抽不出则 query 原文清洗+截断。
    返回的 title 可直接作为文件名主体(日期前缀由调用方拼)。
    """
    query = (query or "").strip()
    if not query:
        return "未命名互动"

    # 1) TextRank 抽取核心关键词
    keywords = ja.textrank(query, topK=4, withWeight=False)
    keywords = [k for k in keywords if k.strip()]

    # 2) 清理引导词开头, 提升纯 query 截断的质量
    clean = _LEAD_NOISE.sub("", query).strip()
    if not clean:
        clean = query

    if keywords:
        # 直接用 TextRank 关键词拼接(短而准: 如「贵州茅台财务数据」就是理想标题)
        body = "".join(keywords)[:force_length]
    else:
        # 完全抽不出关键词(短句/无实义)才回退到 query 原文清洗+截断
        body = clean[:force_length]

    # 3) 清洗非法字符
    body = _ILLEGAL.sub("", body).strip()
    return body or "未命名互动"
