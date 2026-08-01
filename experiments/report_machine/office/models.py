"""
共享 Pydantic 模型 — Office 系统各组件之间通信的数据结构
"""
from pydantic import BaseModel


# ========================
# Middleman Type A
# ========================

class TypeARequest(BaseModel):
    writer_id: str          # writer 生成的唯一 ID
    stock_code: str          # 纯数字股票代码（如 "300750"）


class TypeAResponse(BaseModel):
    writer_id: str
    results: dict            # {engine: {session_id, preview, empty, error}}


# ========================
# Middleman Type B
# ========================

class TypeBRequest(BaseModel):
    report_id: str           # reporter id
    engine: str              # 引擎名称（sinafin / baidufin / ...）
    session_id: str          # mail_tower session id
    article_ids: list[str]   # 要获取正文的文章 ID 列表


class TypeBResponse(BaseModel):
    report_id: str
    engine: str
    session_id: str
    session_closed: bool
    articles: list[dict]     # [{article_id, body_text, truncated}]
    status: str              # ready / error / timeout
    http_status: int = 0     # mail_tower 返回的真实 HTTP 状态码，0 表示网络/超时


# ========================
# Writer 入口
# ========================

class ReportRequest(BaseModel):
    stock_names: list[str]   # 股票名称列表
    query: str = ""           # 用户需求描述，如"生成该股票的日终收盘分析报告"
    report_type: str = "noon" # 报告类型: "noon"(午间) | "endday"(日终)


class SubWorkerResult(BaseModel):
    stock_name: str
    success: bool
    error: str = ""


class ReportResponse(BaseModel):
    report_id: str
    total: int
    success: int
    failed: list[str]
    results: list[SubWorkerResult]


# ========================
# Reporter 内部
# ========================

class ReportContext(BaseModel):
    """Sub writer → Reporter 传递的 context"""
    stock_name: str
    ts_code: str
    fetch_data: str               # 数据脚本 fetch_all 返回的格式化文本
    fetch_message: str            # 消息脚本 fetch_all 返回的格式化文本
    fetch_warnings: dict          # fetch 完整度检查警告
    articles: dict                # {engine: {session_id, preview, ...}}
    middleman_warnings: list[str] # engine 层的异常信息
    query: str = ""               # 用户需求描述
    report_type: str = "noon"     # "noon"(午间) | "endday"(日终)


class ReporterResponse(BaseModel):
    report_id: str
    status: str
    output_path: str = ""
    rounds: int = 0
    error: str = ""
