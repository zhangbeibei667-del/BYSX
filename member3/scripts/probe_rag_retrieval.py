from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="抽样查看当前 Milvus RAG 检索结果。"
    )
    parser.add_argument(
        "queries",
        nargs="*",
        default=[
            "一枝黄花的来源是什么？",
            "黄芪的鉴别方法是什么？",
            "三七的检查项目有哪些？",
        ],
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")

    from app.milvus_search import MilvusVectorSearch

    searcher = MilvusVectorSearch()

    for query in args.queries:
        print("=" * 80)
        print(f"query: {query}")
        print("=" * 80)

        results = searcher.search_debug(
            query=query,
            top_k=args.top_k,
        )

        for rank, item in enumerate(results, start=1):
            print(
                f"[{rank}] "
                f"{item.get('source')} | "
                f"{item.get('title')} | "
                f"score={item.get('rerank_score', item.get('score')):.4f}"
            )
            content = str(item.get("content", "")).replace("\n", " ")
            print(content[:240])
            print()


if __name__ == "__main__":
    main()
