"""IRKG v3 路由核心类型定义"""
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class RouteCondition:
    """路由条件"""
    entity_type: str = ""       # stock_code, sector_name, etc.
    entity_value: str = ""
    time_range_start: str = ""  # YYYYMMDD
    time_range_end: str = ""
    extra: dict = field(default_factory=dict)

@dataclass
class FieldInfo:
    """路由找到的字段信息"""
    id: str
    standard_name: str
    description: str = ""
    data_type: str = ""
    unit: str = ""
    api_column: str = ""         # API 返回时的列名
    has_backup: bool = False     # 是否有备用数据源
    granularity: str = ""        # 数据粒度，格式 "{时间粒度},{范围粒度}"
    refresh_time: str = ""       # 数据刷新时间，如 "realtime"、"daily_17:00"
    similarity: float = 1.0
    match_type: str = "exact"
    authority_level: str = ""        # 权威评级 S/A/B（用于同概念多数据源时优选）

@dataclass
class DataSourceInfo:
    """数据源信息"""
    id: str
    name: str
    protocol: str
    prompt_dir: str = ""
    execution_meta: dict = field(default_factory=dict)

@dataclass
class RouteResult:
    """路由输出"""
    concept_id: str = ""
    concept_name: str = ""
    fields: list[FieldInfo] = field(default_factory=list)
    datasource: Optional[DataSourceInfo] = None
    conditions: RouteCondition = field(default_factory=RouteCondition)
    intent_type: str = "fact"      # fact / analysis / explore
    expanded_fields: list[FieldInfo] = field(default_factory=list)
    web_search_sites: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "concept": self.concept_id,
            "fields": [{"id": f.id, "name": f.standard_name} for f in self.fields],
            "datasource": {
                "id": self.datasource.id if self.datasource else "",
                "name": self.datasource.name if self.datasource else "",
                "protocol": self.datasource.protocol if self.datasource else "",
                "prompt_dir": self.datasource.prompt_dir if self.datasource else "",
            },
            "conditions": {
                "entity": {"type": self.conditions.entity_type, "value": self.conditions.entity_value},
                "time_range": {"start": self.conditions.time_range_start, "end": self.conditions.time_range_end}
            },
            "intent_type": self.intent_type,
            "expanded_fields": [{"id": f.id, "name": f.standard_name} for f in self.expanded_fields],
            "web_search_sites": self.web_search_sites,
        }
