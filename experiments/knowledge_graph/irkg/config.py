"""配置管理"""
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent

class Config:
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASS = os.getenv("NEO4J_PASS", "kg_route_2026")

    FAISS_DIR = str(ROOT / "faiss_index")
    FIELDS_INDEX = f"{FAISS_DIR}/fields.index"
    FIELDS_IDS = f"{FAISS_DIR}/fields_ids.txt"
    CONCEPTS_INDEX = f"{FAISS_DIR}/concepts.index"
    CONCEPTS_IDS = f"{FAISS_DIR}/concepts_ids.txt"

    MODEL_PATH = os.getenv("EMBED_MODEL",
        "/home/stockagent/models/Qwen3-Embedding-4B-Q4_K_M.gguf")

    # 路由参数
    FAISS_TOP_K = 5              # Faiss 检索 Top-K
    SIMILAR_LEVELS = {           # SEMANTIC_SIMILAR_TO 级别
        "fact": ["high"],
        "analysis": ["high", "medium"],
        "explore": ["high", "medium", "low"],
    }

config = Config()
