from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymilvus import MilvusClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="验证 HKCMMS 是否已导入当前 Milvus RAG collection。"
    )
    parser.add_argument(
        "--query",
        default="一枝黄花的来源是什么？",
        help="可选：执行一次 RAG 向量检索验证。",
    )
    parser.add_argument(
        "--skip-search",
        action="store_true",
        help="只检查 Milvus 中的 HKCMMS 记录，不调用 Embedding API。",
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")

    milvus_uri = os.getenv(
        "MILVUS_URI",
        "http://127.0.0.1:19530",
    )
    collection_name = os.getenv(
        "MILVUS_COLLECTION",
        "tcm_rag_chunks",
    )

    client = MilvusClient(uri=milvus_uri)

    stats = client.get_collection_stats(
        collection_name=collection_name,
    )

    hits = client.query(
        collection_name=collection_name,
        filter='source == "HKCMMS"',
        output_fields=[
            "chunk_id",
            "title",
            "source",
        ],
        limit=5,
    )

    visible_rows = client.query(
        collection_name=collection_name,
        filter='source == "HKCMMS"',
        output_fields=[
            "chunk_id",
        ],
        limit=2000,
    )
    visible_ids = [
        item.get("chunk_id")
        for item in visible_rows
    ]

    print("=" * 60)
    print("Milvus HKCMMS Verify")
    print("=" * 60)
    print(f"collection: {collection_name}")
    print(f"row_count : {stats.get('row_count')}")
    print(f"visible HKCMMS rows: {len(visible_rows)}")
    print(f"unique HKCMMS chunk_ids: {len(set(visible_ids))}")
    print(f"HKCMMS sample rows: {len(hits)}")

    for item in hits[:3]:
        print(
            f"- {item.get('chunk_id')} | "
            f"{item.get('title')} | "
            f"{item.get('source')}"
        )

    if args.skip_search:
        return

    from app.milvus_search import MilvusVectorSearch

    searcher = MilvusVectorSearch()
    results = searcher.search_debug(
        query=args.query,
        top_k=3,
    )

    print()
    print(f"query: {args.query}")

    for rank, item in enumerate(results, start=1):
        print(
            f"[{rank}] {item.get('source')} | "
            f"{item.get('title')} | "
            f"{item.get('rerank_score', item.get('score')):.4f}"
        )


if __name__ == "__main__":
    main()
