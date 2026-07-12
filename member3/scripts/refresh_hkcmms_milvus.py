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

from scripts.milvus_insert import main as insert_main


DEFAULT_INPUT = (
    PROJECT_ROOT
    / "data"
    / "pharmacopoeia"
    / "processed"
    / "hkcmms"
    / "index_ready"
    / "chunks_for_milvus.jsonl"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "刷新 Milvus 中的 HKCMMS 增量语料："
            "先删除 source == HKCMMS，再重新导入。"
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
    )
    parser.add_argument(
        "--source",
        default="HKCMMS",
        help="只允许刷新指定 source，默认 HKCMMS。",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="确认执行删除并重导入。",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.source != "HKCMMS":
        raise ValueError(
            "该脚本只允许刷新 HKCMMS，避免误删其他语料。"
        )

    if not args.yes:
        raise RuntimeError(
            "请显式传入 --yes 确认刷新 HKCMMS。"
        )

    if not args.input.exists():
        raise FileNotFoundError(
            f"找不到输入文件: {args.input}"
        )

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

    before = client.get_collection_stats(
        collection_name=collection_name,
    )

    print("=" * 60)
    print("Refresh HKCMMS Milvus Corpus")
    print("=" * 60)
    print(f"collection: {collection_name}")
    print(f"row_count before: {before.get('row_count')}")
    print("deleting: source == \"HKCMMS\"")

    result = client.delete(
        collection_name=collection_name,
        filter='source == "HKCMMS"',
    )
    print(f"delete result: {result}")

    client.flush(
        collection_name=collection_name,
    )

    after_delete = client.get_collection_stats(
        collection_name=collection_name,
    )
    print(f"row_count after delete: {after_delete.get('row_count')}")

    sys.argv = [
        "milvus_insert.py",
        "--input",
        str(args.input),
        "--limit",
        "0",
    ]

    insert_main()

    final_stats = client.get_collection_stats(
        collection_name=collection_name,
    )
    print(f"row_count final: {final_stats.get('row_count')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
