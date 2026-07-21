"""
知识图谱配置中心
"""
from pathlib import Path

# ===== Neo4j =====
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "kg_route_2026"

# ===== SQLite =====
DB_PATH = Path("/home/stockagent/project_space/database/report_market.db")
KEYWORD_FILE = Path("/home/stockagent/project_space/demand/final/data/keyword_tree_final_v2.md")
