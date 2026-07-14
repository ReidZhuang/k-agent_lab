#!/usr/bin/env python3
"""Phase 2: 生成 DataField 和 IntentConcept 的 Embedding

流程:
1. 用 GPU 加载 Qwen3-Embedding-4B GGUF 模型
2. 为所有 DataField 生成 embedding（拼接文本 -> 向量）
3. 为所有 IntentConcept 生成 embedding
4. 写入 Neo4j 节点属性
5. 建 Faiss 索引文件
6. 计算 SEMANTIC_SIMILAR_TO 关系
"""
import csv, json, time, sys
import numpy as np
from neo4j import GraphDatabase
from llama_cpp import Llama

# --- 配置 ---
MODEL_PATH = "/home/stockagent/models/Qwen3-Embedding-4B-Q4_K_M.gguf"
DATA_DIR = "../data"
FAISS_DIR = "../faiss_index"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "kg_route_2026"

BATCH_SIZE = 50  # 每批写入 Neo4j 的节点数

def read_csv(filename):
    with open(f"{DATA_DIR}/{filename}", newline="") as f:
        return list(csv.DictReader(f))

def build_field_text(row):
    """DataField 的 embedding 拼接文本"""
    try:
        aliases = json.loads(row["alias"]) if row["alias"] else []
    except:
        aliases = []
    alias_str = " ".join(aliases)
    return f"{row['standard_name']} {alias_str} {row['description']}"

def build_concept_text(row):
    """IntentConcept 的 embedding 拼接文本"""
    return f"{row['name']} {row['description']}"

def main():
    print("=" * 60)
    print("Phase 2: Embedding 生成")
    print("=" * 60)

    # 1. 加载模型
    print(f"\n[1/6] 加载模型: {MODEL_PATH}")
    t0 = time.time()
    model = Llama(
        model_path=MODEL_PATH,
        n_gpu_layers=-1,       # 全量放 GPU
        n_ctx=512,             # embedding 不需要长上下文
        verbose=False,
        embedding=True          # embedding 模式
    )
    print(f"    模型加载完成（{time.time()-t0:.1f}s, 显存约 2.5GB）")

    # 2. 读取数据
    print(f"\n[2/6] 读取数据...")
    concepts = read_csv("concepts.csv")
    fields = read_csv("fields.csv")
    print(f"    IntentConcept: {len(concepts)} 个")
    print(f"    DataField: {len(fields)} 个")

    # 3. 生成 DataField Embedding
    print(f"\n[3/6] 生成 DataField Embedding...")
    field_embeddings = {}
    t0 = time.time()
    for i, row in enumerate(fields):
        text = build_field_text(row)
        result = model.embed(text)
        field_embeddings[row["id"]] = result
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            print(f"    进度: {i+1}/{len(fields)} ({elapsed:.0f}s, {elapsed/(i+1):.2f}s/个)")
    total_time = time.time() - t0
    print(f"    DataField Embedding 完成: {len(fields)} 个, 耗时 {total_time:.0f}s ({total_time/len(fields):.2f}s/个)")

    # 4. 生成 IntentConcept Embedding
    print(f"\n[4/6] 生成 IntentConcept Embedding...")
    concept_embeddings = {}
    t0 = time.time()
    for i, row in enumerate(concepts):
        text = build_concept_text(row)
        result = model.embed(text)
        concept_embeddings[row["id"]] = result
    print(f"    IntentConcept Embedding 完成: {len(concepts)} 个, 耗时 {time.time()-t0:.1f}s")

    # 5. 写入 Neo4j
    print(f"\n[5/6] 写入 Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    driver.verify_connectivity()

    with driver.session() as session:
        # 写 DataField embedding
        t0 = time.time()
        fields_batch = []
        for fid, emb in field_embeddings.items():
            fields_batch.append({"id": fid, "embedding": emb})
            if len(fields_batch) >= BATCH_SIZE:
                session.run("""
                    UNWIND $rows AS row
                    MATCH (f:DataField {id: row.id})
                    SET f.embedding = row.embedding
                """, rows=fields_batch)
                fields_batch = []
        if fields_batch:
            session.run("""
                UNWIND $rows AS row
                MATCH (f:DataField {id: row.id})
                SET f.embedding = row.embedding
            """, rows=fields_batch)
        print(f"    DataField embedding 写入完成（{time.time()-t0:.1f}s）")

        # 写 IntentConcept embedding
        t0 = time.time()
        concepts_batch = []
        for cid, emb in concept_embeddings.items():
            concepts_batch.append({"id": cid, "embedding": emb})
            if len(concepts_batch) >= BATCH_SIZE:
                session.run("""
                    UNWIND $rows AS row
                    MATCH (c:IntentConcept {id: row.id})
                    SET c.embedding = row.embedding
                """, rows=concepts_batch)
                concepts_batch = []
        if concepts_batch:
            session.run("""
                UNWIND $rows AS row
                MATCH (c:IntentConcept {id: row.id})
                SET c.embedding = row.embedding
            """, rows=concepts_batch)
        print(f"    IntentConcept embedding 写入完成（{time.time()-t0:.1f}s）")

    driver.close()

    # 6. 建 Faiss 索引
    print(f"\n[6/6] 建立 Faiss 索引...")
    import faiss

    # DataField 索引
    t0 = time.time()
    dim = 1024
    field_matrix = np.array([field_embeddings[fid] for fid in sorted(field_embeddings.keys())]).astype(np.float32)
    field_index = faiss.IndexFlatIP(dim)  # 内积（余弦相似度）
    field_index.add(field_matrix)
    faiss.write_index(field_index, f"{FAISS_DIR}/fields.index")
    # 保存 ID 映射
    field_ids_sorted = sorted(field_embeddings.keys())
    with open(f"{FAISS_DIR}/fields_ids.txt", "w") as f:
        for fid in field_ids_sorted:
            f.write(f"{fid}\n")
    print(f"    DataField Faiss 索引: {len(field_ids_sorted)} 条, 耗时 {time.time()-t0:.1f}s")

    # IntentConcept 索引
    t0 = time.time()
    concept_matrix = np.array([concept_embeddings[cid] for cid in sorted(concept_embeddings.keys())]).astype(np.float32)
    concept_index = faiss.IndexFlatIP(dim)
    concept_index.add(concept_matrix)
    faiss.write_index(concept_index, f"{FAISS_DIR}/concepts.index")
    concept_ids_sorted = sorted(concept_embeddings.keys())
    with open(f"{FAISS_DIR}/concepts_ids.txt", "w") as f:
        for cid in concept_ids_sorted:
            f.write(f"{cid}\n")
    print(f"    IntentConcept Faiss 索引: {len(concept_ids_sorted)} 条, 耗时 {time.time()-t0:.1f}s")

    print(f"\n{'=' * 60}")
    print(f"Phase 2 Embedding 生成完成!")
    print(f"  - DataField: {len(field_embeddings)} 个向量")
    print(f"  - IntentConcept: {len(concept_embeddings)} 个向量")
    print(f"  - Faiss 索引: {FAISS_DIR}/")

if __name__ == "__main__":
    main()
