"""entity_resolver — 实体名称 → 金融代码 映射

支持三种实体类型：
- stock_code: "宁德时代" → "300750.SZ"（从 Tushare stock_basic 查询并缓存）
- index_code: "上证指数" → "000001.SH"（预定义 + Neo4j 补充）
- sector_name: "电池板块" → "电池"（去掉"板块"后缀即可）

使用方式:
    resolver = EntityResolver()
    value, etype = resolver.resolve("宁德时代")
    # → ("300750.SZ", "stock_code")
"""
import json, os, sys, time, re
from pathlib import Path

_QA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KG_DIR = os.path.dirname(_QA_DIR)

# ── 缓存路径 ──
_CACHE_DIR = Path(_QA_DIR) / "data"
_CACHE_FILE = _CACHE_DIR / "entity_cache.json"
os.makedirs(_CACHE_DIR, exist_ok=True)

# ── 默认股票代码映射（第一次查询前的兜底） ──
# 格式: {中文名: TS代码}
_FALLBACK_STOCK_MAP: dict[str, str] = {
    "宁德时代": "300750.SZ",
    "贵州茅台": "600519.SH",
    "比亚迪": "002594.SZ",
    "中国平安": "601318.SH",
    "招商银行": "600036.SH",
    "五粮液": "000858.SZ",
    "海康威视": "002415.SZ",
    "格力电器": "000651.SZ",
    "美的集团": "000333.SZ",
    "恒瑞医药": "600276.SH",
    "迈瑞医疗": "300760.SZ",
    "药明康德": "603259.SH",
    "中兴通讯": "000063.SZ",
    "科大讯飞": "002230.SZ",
    "顺丰控股": "002352.SZ",
    "伊利股份": "600887.SH",
    "泸州老窖": "000568.SZ",
    "山西汾酒": "600809.SH",
    "洋河股份": "002304.SZ",
    "长春高新": "000661.SZ",
    "万科A": "000002.SZ",
    "东方财富": "300059.SZ",
    "中信证券": "600030.SH",
    "保利发展": "600048.SH",
    "隆基绿能": "601012.SH",
    "通威股份": "600438.SH",
    "中芯国际": "688981.SH",
    "北方华创": "002371.SZ",
    "兆易创新": "603986.SH",
    "金山办公": "688111.SH",
    "云南白药": "000538.SZ",
    "中国核电": "601985.SH",
    "海尔智家": "600690.SH",
    "中国太保": "601601.SH",
    "青岛啤酒": "600600.SH",
    "海螺水泥": "600585.SH",
    "中微公司": "688012.SH",
    "华大基因": "300676.SZ",
    "复星医药": "600196.SH",
    "中国人寿": "601628.SH",
    "中航光电": "002179.SZ",
    "中国联通": "600941.SH",
    "TCL科技": "000100.SZ",
    "宝钢股份": "600019.SH",
    "长江电力": "600900.SH",
    "平安银行": "000001.SZ",
    "工商银行": "601398.SH",
    "中国建筑": "601668.SH",
    "三一重工": "600031.SH",
    "紫金矿业": "601899.SH",
    "万华化学": "600309.SH",
    "立讯精密": "002475.SZ",
    "海天味业": "603288.SH",
    "牧原股份": "002714.SZ",
    "京东方A": "000725.SZ",
    "中国中免": "601888.SH",
    "双汇发展": "000895.SZ",
    "中国神华": "601088.SH",
    "大秦铁路": "601006.SH",
    "交通银行": "601328.SH",
    "恒生电子": "600570.SH",
    "用友网络": "600588.SH",
    "上海机场": "600009.SH",
    "上汽集团": "600104.SH",
    "兴业银行": "601166.SH",
    "浦发银行": "600000.SH",
    "民生银行": "600016.SH",
    "农业银行": "601288.SH",
    "建设银行": "601939.SH",
    "中国银行": "601988.SH",
    "中国石油": "601857.SH",
    "中国石化": "600028.SH",
    "中国移动": "600941.SH",
    "腾讯控股": "00700.HK",
    "茅台": "600519.SH",
    "中石油": "601857.SH",
    "中石化": "600028.SH",
}

# ── 指数映射 ──
_INDEX_MAP: dict[str, str] = {
    "上证指数": "000001.SH",
    "深证成指": "399001.SZ",
    "创业板指": "399006.SZ",
    "科创50": "000688.SH",
    "沪深300": "000300.SH",
    "中证500": "000905.SH",
    "中证1000": "000852.SH",
    "上证50": "000016.SH",
    "恒生指数": "HSI.HK",
    "标普500": ".SPX",
    "纳斯达克": ".IXIC",
    "纳指": ".IXIC",
    "道琼斯": ".DJI",
    "日经225": "N225.JP",
}

# ── 板块/概念后缀 ──
_SECTOR_SUFFIXES = ["板块", "概念", "行业"]


class EntityResolver:
    """实体名称 → 金融代码 解析器"""

    def __init__(self, force_rebuild: bool = False):
        self._stock_map: dict[str, str] = dict(_FALLBACK_STOCK_MAP)
        self._index_map: dict[str, str] = dict(_INDEX_MAP)
        self._loaded = False
        if _CACHE_FILE.exists() and not force_rebuild:
            self._load_cache()

    # ── 公开接口 ──

    def resolve(self, name: str) -> tuple[str, str]:
        """解析实体名 → (entity_value, entity_type)

        Returns:
            (value, type) — type 为 stock_code / index_code / sector_name
        """
        name = name.strip()

        # 1. 已经是代码格式（纯数字.后缀 或 SH/SZ前缀+数字）
        code = self._try_parse_code(name)
        if code:
            return code, "stock_code"

        # 2. 指数
        if name in self._index_map:
            return self._index_map[name], "index_code"

        # 3. 板块/概念（末尾带"板块/概念/行业"字样）
        for suffix in _SECTOR_SUFFIXES:
            if name.endswith(suffix) or name.endswith(suffix):
                # 去掉后缀作为 sector name
                sector_name = name[:-len(suffix)] if name.endswith(suffix) else name
                return sector_name, "sector_name"

        # 4. 特定概念（北向资金、市场热度等）
        concept_type = self._detect_concept_type(name)
        if concept_type:
            return name, concept_type

        # 5. 先查缓存，再尝试 Tushare
        if name in self._stock_map:
            return self._stock_map[name], "stock_code"

        # 6. 动态查询 Tushare（懒加载 + 缓存）
        ts_code = self._query_tushare(name)
        if ts_code:
            self._stock_map[name] = ts_code
            self._save_cache()
            return ts_code, "stock_code"

        # 7. 兜底：用原名称当 sector
        return name, "sector_name"

    def resolve_obj_list(self, objs: list[str]) -> list[dict]:
        """批量解析 obj 列表

        Returns:
            [{"name": "宁德时代", "value": "300750.SZ", "type": "stock_code"}, ...]
        """
        results = []
        for obj in objs:
            value, etype = self.resolve(obj)
            results.append({"name": obj, "value": value, "type": etype})
        return results

    # ── 内部方法 ──

    @staticmethod
    def _try_parse_code(name: str) -> str | None:
        """尝试解析已有代码格式"""
        # 300750.SZ / 600519.SH
        m = re.match(r'^(\d{6})\.(SH|SZ|HK|BJ)$', name.upper())
        if m:
            return m.group(0).upper()

        # SH600519 / sz300750
        m = re.match(r'^(SH|SZ|BJ|HK)(\d{6})$', name.upper())
        if m:
            return f"{m.group(2)}.{m.group(1)}"

        # 纯数字（6位）
        m = re.match(r'^(\d{6})$', name)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _detect_concept_type(name: str) -> str | None:
        """识别特定概念类型"""
        concept_keywords = {
            "北向资金": "concept",
            "南向资金": "concept",
            "市场热度": "concept",
            "大盘资金": "concept",
            "融资余额": "concept",
            "融券余额": "concept",
            "全市场": "concept",
            "中国": "macro",
            "美国": "macro",
        }
        for key, _ in concept_keywords.items():
            if key in name:
                return "concept"  # 无代码，需要进一步判断 data_source
        return None

    def _query_tushare(self, name: str) -> str | None:
        """查询 Tushare stock_basic 获取中文名 → TS 代码"""
        try:
            import tushare as ts
            import os as _os
            token = _os.getenv("TUSHARE_TOKEN", "")
            if token:
                ts.set_token(token)
            pro = ts.pro_api()
            df = pro.stock_basic(name=name)
            if df is not None and not df.empty:
                return df.iloc[0]["ts_code"]
            # 模糊查询
            df_all = pro.stock_basic()
            if df_all is not None and not df_all.empty:
                match = df_all[df_all["name"].str.contains(name, na=False)]
                if not match.empty:
                    return match.iloc[0]["ts_code"]
        except Exception:
            pass
        return None

    # ── 缓存 ──

    def _load_cache(self):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._stock_map.update(data.get("stock_map", {}))
            self._index_map.update(data.get("index_map", {}))
            self._loaded = True
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    def _save_cache(self):
        try:
            data = {
                "stock_map": self._stock_map,
                "index_map": self._index_map,
                "updated_at": time.strftime("%Y%m%d_%H%M%S"),
            }
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ── 单例 ──
_resolver: EntityResolver | None = None


def get_resolver(force_rebuild: bool = False) -> EntityResolver:
    global _resolver
    if _resolver is None or force_rebuild:
        _resolver = EntityResolver(force_rebuild=force_rebuild)
    return _resolver
