"""alias 多级匹配模块

支持 4 级 alias，按优先级匹配：
  1. qualified   最高  带限定词的全称，通常唯一
  2. simple      高    最简中文名，可能有冲突
  3. business_tag 中   业务意义标签
  4. synonym     低    近义词变体兜底
"""
import csv


class AliasMatcher:
    """4 级 alias 匹配器"""

    def __init__(self):
        self._indices: dict[str, dict[str, list[str]]] = {
            "qualified": {},
            "simple": {},
            "business_tag": {},
            "synonym": {},
        }
        self._field_info: dict[str, dict] = {}

    def build_from_csv(self, csv_path: str):
        """从 alias CSV 文件构建索引"""
        with open(csv_path, newline="") as f:
            self.build(list(csv.DictReader(f)))

    def build(self, rows: list[dict]):
        """从 alias 数据行构建索引"""
        self._indices = {k: {} for k in self._indices}
        self._field_info = {}

        for row in rows:
            fid = row["field_id"]
            self._field_info[fid] = {
                "standard_name": row["standard_name"],
                "concept_id": row["concept_id"],
                "simple": row["simple"],
                "qualified": row["qualified"],
                "business_tag": row["business_tag"],
                "synonyms": row["synonyms"],
            }

            # simple
            self._add_to_index("simple", row["simple"], fid)

            # qualified (| 分隔多个)
            for q in row["qualified"].split("|"):
                self._add_to_index("qualified", q.strip(), fid)

            # business_tag (| 分隔多个)
            for t in row["business_tag"].split("|"):
                self._add_to_index("business_tag", t.strip(), fid)

            # synonyms (| 分隔多个)
            for s in row["synonyms"].split("|"):
                self._add_to_index("synonym", s.strip(), fid)

    def _add_to_index(self, level: str, term: str, field_id: str):
        term = term.strip()
        if not term:
            return
        if term not in self._indices[level]:
            self._indices[level][term] = []
        if field_id not in self._indices[level][term]:
            self._indices[level][term].append(field_id)

    def match_qualified(self, term: str) -> list[str]:
        """qualified 精确匹配（最高优先级）"""
        return self._indices["qualified"].get(term, [])

    def match_simple(self, term: str) -> list[str]:
        """simple 精确匹配"""
        return self._indices["simple"].get(term, [])

    def match_business_tag(self, term: str) -> list[str]:
        """business_tag 精确匹配"""
        return self._indices["business_tag"].get(term, [])

    def match_synonym(self, term: str) -> list[str]:
        """synonym 精确匹配（最低优先级）"""
        return self._indices["synonym"].get(term, [])

    def match_all(self, term: str) -> dict[str, list[str]]:
        """在所有级别搜索, 返回 {level: [field_ids]}"""
        return {
            "qualified": self.match_qualified(term),
            "simple": self.match_simple(term),
            "business_tag": self.match_business_tag(term),
            "synonym": self.match_synonym(term),
        }

    def match_multi(self, keywords: list[str]) -> list[tuple[str, str]]:
        """批量关键词搜索，按优先级排序返回 [(field_id, match_type), ...]

        Args:
            keywords: LLM 提取的关键词列表

        Returns:
            去重的 (field_id, match_type) 列表，
            优先返回 qualified 匹配，其次 simple，依次类推
        """
        seen = set()
        results = []

        # 按优先级搜索
        for level in ["qualified", "simple", "business_tag", "synonym"]:
            for kw in keywords:
                for fid in self._indices[level].get(kw, []):
                    if fid not in seen:
                        seen.add(fid)
                        results.append((fid, level))

        return results

    def get_info(self, field_id: str) -> dict | None:
        return self._field_info.get(field_id)

    @property
    def size(self):
        return sum(len(v) for v in self._indices["simple"].items())

    def index_stats(self) -> dict:
        return {level: len(idx) for level, idx in self._indices.items()}
