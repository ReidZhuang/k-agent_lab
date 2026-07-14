"""Embedding 检索模块（CPU 推理 + Faiss 搜索）"""
import numpy as np
import faiss
from pathlib import Path
from .config import config


class EmbeddingRetriever:
    """向量检索器：query embedding (CPU) + Faiss Top-K"""

    def __init__(self):
        self._model = None
        self._field_index: faiss.Index | None = None
        self._concept_index: faiss.Index | None = None
        self._field_ids: list[str] = []
        self._concept_ids: list[str] = []

    def load(self):
        """加载模型（首次调用时延迟加载）"""
        if self._field_index is not None:
            return
        # 加载 Faiss 索引
        self._field_index = faiss.read_index(config.FIELDS_INDEX)
        with open(config.FIELDS_IDS) as f:
            self._field_ids = [l.strip() for l in f]
        self._concept_index = faiss.read_index(config.CONCEPTS_INDEX)
        with open(config.CONCEPTS_IDS) as f:
            self._concept_ids = [l.strip() for l in f]
        print(f"  [Embedding] Faiss 索引已加载: "
              f"{len(self._field_ids)} fields, {len(self._concept_ids)} concepts")

    def load_model(self):
        """加载 Embedding 模型（CPU 推理）"""
        if self._model is not None:
            return
        from llama_cpp import Llama
        self._model = Llama(
            model_path=config.MODEL_PATH,
            n_gpu_layers=0,     # CPU 推理
            n_ctx=512,
            verbose=False,
            embedding=True,
        )
        print("  [Embedding] 模型已加载（CPU 模式）")

    def embed_query(self, text: str) -> np.ndarray:
        """将用户 query 转为向量（CPU 推理）"""
        self.load_model()
        vec = self._model.embed(text)
        arr = np.array([vec], dtype=np.float32)
        # 归一化
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr

    def search_fields(self, query_vec: np.ndarray, top_k: int = None) -> list[dict]:
        """搜索最相似的 DataField"""
        self.load()
        if top_k is None:
            top_k = config.FAISS_TOP_K
        scores, indices = self._field_index.search(query_vec, top_k)
        results = []
        for idx, score in zip(indices[0], scores[0]):
            results.append({
                "id": self._field_ids[idx],
                "score": float(score),
            })
        return results

    def search_concepts(self, query_vec: np.ndarray, top_k: int = 3) -> list[dict]:
        """搜索最相似的 IntentConcept"""
        self.load()
        scores, indices = self._concept_index.search(query_vec, top_k)
        results = []
        for idx, score in zip(indices[0], scores[0]):
            results.append({
                "id": self._concept_ids[idx],
                "score": float(score),
            })
        return results
