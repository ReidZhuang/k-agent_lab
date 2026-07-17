#!/usr/bin/env python3
"""重生成 Embedding：从 Neo4j 读取，修复 alias 拼接 bug，GPU 生成

Bug 修复前：alias 拼接的是 dict 的 key（"simple qualified..."）
Bug 修复后：alias 拼接的是所有级别的实际值（"收盘价 K线收盘价 历史收盘..."）
"""
import json, time, os
import numpy as np
from neo4j import GraphDatabase
from llama_cpp import Llama

MODEL_PATH = "/home/stockagent/models/Qwen3-Embedding-4B-Q4_K_M.gguf"
FAISS_DIR = os.path.join(os.path.dirname(__file__), "..", "faiss_index")
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "kg_route_2026"
BATCH_SIZE = 50

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
driver.verify_connectivity()


def get_all_fields():
    """从 Neo4j 读取所有 DataField"""
    with driver.session() as s:
        result = s.run("MATCH (f:DataField) RETURN f.id as id, f.standard_name as name, "
                       "f.alias as alias, f.description as desc ORDER BY f.id")
        return [{"id": r["id"], "name": r["name"] or "",
                 "alias": json.loads(r["alias"]) if isinstance(r["alias"], str) else (r["alias"] or {}),
                 "desc": r["desc"] or ""} for r in result]


def get_all_concepts():
    """从 Neo4j 读取所有 IntentConcept"""
    with driver.session() as s:
        result = s.run("MATCH (c:IntentConcept) RETURN c.id as id, "
                       "c.name as name, c.description as desc ORDER BY c.id")
        return [{"id": r["id"], "name": r["name"] or "", "desc": r["desc"] or ""} for r in result]


def build_field_text(field: dict) -> str:
    """修复后的 embedding 拼接文本：使用 alias 的 VALUE 而非 KEY"""
    alias_data = field.get("alias", {}) or {}
    # 提取所有级别的别名值
    all_values = []
    for level, values in alias_data.items():
        if isinstance(values, list):
            all_values.extend(values)
    alias_str = " ".join(all_values)
    return f"{field['name']} {alias_str} {field['desc']}".strip()


def build_concept_text(concept: dict) -> str:
    return f"{concept['name']} {concept['desc']}".strip()


def main():
    print("=" * 60)
    print("重生成 Embedding（从 Neo4j 读取）")
    print("=" * 60)

    # 1. 从 Neo4j 读取数据
    print("\n[1] 从 Neo4j 读取数据...")
    fields = get_all_fields()
    concepts = get_all_concepts()
    print(f"    DataField: {len(fields)} 个")
    print(f"    IntentConcept: {len(concepts)} 个")

    # 2. 加载模型
    print(f"\n[2] 加载模型: {MODEL_PATH}")
    t0 = time.time()
    model = Llama(
        model_path=MODEL_PATH,
        n_gpu_layers=-1,
        n_ctx=512,
        verbose=False,
        embedding=True,
    )
    print(f"    加载完成（{time.time()-t0:.1f}s）")

    # 3. 生成 DataField Embedding
    print(f"\n[3] 生成 DataField Embedding...")
    field_embs = {}
    t0 = time.time()
    for i, field in enumerate(fields):
        text = build_field_text(field)
        result = model.embed(text)
        field_embs[field["id"]] = result
        if (i + 1) % 50 == 0:
            print(f"    进度: {i+1}/{len(fields)} ({time.time()-t0:.0f}s)")
    print(f"    完成: {len(fields)} 个 ({time.time()-t0:.0f}s)")

    # 验证：打印几条修复前后的文本对比
    print("\n    修复检查：")
    for fid in ['FIELD_KLINE_CLOSE', 'FIELD_QUOTE_PCT_CHG', 'FIELD_QUOTE_CODE']:
        f = next((x for x in fields if x["id"] == fid), None)
        if f:
            print(f"    [{fid}] text: {build_field_text(f)[:100]}...")

    # 4. 生成 IntentConcept Embedding
    print(f"\n[4] 生成 IntentConcept Embedding...")
    concept_embs = {}
    t0 = time.time()
    for i, concept in enumerate(concepts):
        text = build_concept_text(concept)
        result = model.embed(text)
        concept_embs[concept["id"]] = result
    print(f"    完成: {len(concepts)} 个 ({time.time()-t0:.1f}s)")

    # 5. 写入 Neo4j
    print(f"\n[5] 写入 Neo4j...")
    with driver.session() as session:
        # DataField
        t0 = time.time()
        batch = []
        for fid, emb in field_embs.items():
            batch.append({"id": fid, "embedding": emb})
            if len(batch) >= BATCH_SIZE:
                session.run("UNWIND $rows AS row MATCH (f:DataField {id: row.id}) SET f.embedding = row.embedding", rows=batch)
                batch = []
        if batch:
            session.run("UNWIND $rows AS row MATCH (f:DataField {id: row.id}) SET f.embedding = row.embedding", rows=batch)
        print(f"    DataField 写入完成（{time.time()-t0:.1f}s）")

        # IntentConcept
        t0 = time.time()
        batch = []
        for cid, emb in concept_embs.items():
            batch.append({"id": cid, "embedding": emb})
            if len(batch) >= BATCH_SIZE:
                session.run("UNWIND $rows AS row MATCH (c:IntentConcept {id: row.id}) SET c.embedding = row.embedding", rows=batch)
                batch = []
        if batch:
            session.run("UNWIND $rows AS row MATCH (c:IntentConcept {id: row.id}) SET c.embedding = row.embedding", rows=batch)
        print(f"    IntentConcept 写入完成（{time.time()-t0:.1f}s）")

    driver.close()

    # 6. 建 Faiss 索引
    print(f"\n[6] 建立 Faiss 索引...")
    import faiss

    dim = 2560
    t0 = time.time()

    # DataField
    fids_sorted = sorted(field_embs.keys())
    matrix = np.array([field_embs[fid] for fid in fids_sorted]).astype(np.float32)
    index = faiss.IndexFlatIP(dim)
    index.add(matrix)
    faiss.write_index(index, f"{FAISS_DIR}/fields.index")
    with open(f"{FAISS_DIR}/fields_ids.txt", "w") as f:
        for fid in fids_sorted:
            f.write(f"{fid}\n")
    print(f"    DataField 索引: {len(fids_sorted)} 条 ({time.time()-t0:.1f}s)")

    # IntentConcept
    t0 = time.time()
    cids_sorted = sorted(concept_embs.keys())
    matrix_c = np.array([concept_embs[cid] for cid in cids_sorted]).astype(np.float32)
    index_c = faiss.IndexFlatIP(dim)
    index_c.add(matrix_c)
    faiss.write_index(index_c, f"{FAISS_DIR}/concepts.index")
    with open(f"{FAISS_DIR}/concepts_ids.txt", "w") as f:
        for cid in cids_sorted:
            f.write(f"{cid}\n")
    print(f"    IntentConcept 索引: {len(cids_sorted)} 条 ({time.time()-t0:.1f}s)")

    print(f"\n{'=' * 60}")
    print("Embedding 重生成完成！")
    print(f"  DataField: {len(field_embs)} 个")
    print(f"  IntentConcept: {len(concept_embs)} 个")
    print(f"  Faiss 索引更新到: {FAISS_DIR}/")


if __name__ == "__main__":
    main()
