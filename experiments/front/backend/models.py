"""
Pydantic 模型
"""
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: int
    username: str


class StockSearchResult(BaseModel):
    ts_code: str
    symbol: str
    name: str
    industry: str = ""


class StockPoolItem(BaseModel):
    ts_code: str
    stock_name: str
    created_at: str = ""


class AddStockRequest(BaseModel):
    stock_names: list[str]


class FavoriteItem(BaseModel):
    file_path: str
    file_name: str


class ExplorerItem(BaseModel):
    name: str
    path: str
    type: str  # file / dir
    is_favorite: bool = False


class DownloadRequest(BaseModel):
    paths: list[str]


class DailyDataItem(BaseModel):
    ts_code: str
    name: str = ""
    trade_date: str = ""
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    pre_close: float | None = None
    change: float | None = None
    pct_chg: float | None = None
    vol: float | None = None
    amount: float | None = None
    turnover_rate: float | None = None  # from daily_basic
    amplitude: float | None = None  # from daily_basic


# ── 股小神聊天 ──

class ChatCreateRequest(BaseModel):
    conv_id: str
    title: str = ""


class ChatMessageItem(BaseModel):
    role: str  # user / assistant
    content: str


class ChatAppendRequest(BaseModel):
    role: str
    content: str


class ChatCompletionsRequest(BaseModel):
    conv_id: str
    messages: list[ChatMessageItem]
