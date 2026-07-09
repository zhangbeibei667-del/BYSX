from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from pymilvus import MilvusClient


# 让 scripts/ 下的脚本可以导入 app/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from app.embedding_client import EmbeddingClient


MILVUS_URI = "http://127.0.0.1:19530"
COLLECTION_NAME = "tcm_rag_chunks"

DEFAULT_CORPUS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "rag_corpus_clean.jsonl"
)

# text-embedding-v4 单批最多 10 条
EMBEDDING_BATCH_SIZE = 10

# Milvus 每累计多少条执行一次 insert
MILVUS_INSERT_BATCH_SIZE = 100


def read_jsonl(
    path: Path,
    limit: int | None = None,
) -> Iterator[dict]:
    """
    逐行读取 JSONL，避免一次性全部加载到内存。
    """
    count = 0

    with path.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        for line_no, line in enumerate(
            file,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"第 {line_no} 行 JSON 解析失败"
                ) from exc

            yield item

            count += 1

            if (
                limit is not None
                and count >= limit
            ):
                break


def batched(
    items: list[dict],
    batch_size: int,
) -> Iterator[list[dict]]:
    """
    将列表切成多个小批次。
    """
    for start in range(
        0,
        len(items),
        batch_size,
    ):
        yield items[
            start:start + batch_size
        ]


def validate_chunk(
    item: dict,
) -> None:
    """
    检查 RAG chunk 是否具备必要字段。
    """
    required_fields = [
        "chunk_id",
        "doc_id",
        "title",
        "content",
        "source",
    ]

    missing = [
        field
        for field in required_fields
        if field not in item
    ]

    if missing:
        raise ValueError(
            "Chunk 缺少字段: "
            + ", ".join(missing)
        )

    if not str(item["content"]).strip():
        raise ValueError(
            f"Chunk 内容为空: "
            f"{item.get('chunk_id')}"
        )


def build_milvus_rows(
    embedding_client: EmbeddingClient,
    chunks: list[dict],
) -> list[dict]:
    """
    对一小批 chunk 生成向量，
    转换成 Milvus 插入格式。
    """
    texts = [
        str(item["content"]).strip()
        for item in chunks
    ]

    vectors = embedding_client.embed_batch(
        texts
    )

    rows = []

    for item, vector in zip(
        chunks,
        vectors,
        strict=True,
    ):
        rows.append(
            {
                "chunk_id": str(
                    item["chunk_id"]
                ),
                "doc_id": str(
                    item["doc_id"]
                ),
                "title": str(
                    item["title"]
                ),
                "content": str(
                    item["content"]
                ),
                "source": str(
                    item["source"]
                ),
                "embedding": vector,
            }
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "将清洗后的 TCM RAG corpus "
            "向量化并写入 Milvus"
        )
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_CORPUS_PATH,
        help="rag_corpus_clean.jsonl 路径",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help=(
            "最多导入多少条。"
            "默认 100；传 0 表示全部。"
        ),
    )

    args = parser.parse_args()

    load_dotenv(
        PROJECT_ROOT / ".env"
    )

    if not args.input.exists():
        raise FileNotFoundError(
            f"找不到输入文件: {args.input}"
        )

    client = MilvusClient(
        uri=MILVUS_URI
    )

    collections = client.list_collections()

    if COLLECTION_NAME not in collections:
        raise RuntimeError(
            f"Collection 不存在: "
            f"{COLLECTION_NAME}"
        )

    embedding_client = EmbeddingClient()

    limit = (
        None
        if args.limit == 0
        else args.limit
    )

    print("=" * 60)
    print("TCM GraphRAG Milvus Insert")
    print("=" * 60)
    print(f"输入文件: {args.input}")
    print(f"Collection: {COLLECTION_NAME}")
    print(
        "导入数量: "
        + (
            "全部"
            if limit is None
            else str(limit)
        )
    )
    print(
        f"Embedding 批次: "
        f"{EMBEDDING_BATCH_SIZE}"
    )
    print("=" * 60)

    chunks = []

    for item in read_jsonl(
        args.input,
        limit=limit,
    ):
        validate_chunk(item)
        chunks.append(item)

    print(
        f"读取成功: {len(chunks)} 条"
    )

    pending_rows: list[dict] = []
    inserted_total = 0

    start_time = time.time()

    embedding_batches = list(
        batched(
            chunks,
            EMBEDDING_BATCH_SIZE,
        )
    )

    for batch_no, chunk_batch in enumerate(
        embedding_batches,
        start=1,
    ):
        print(
            f"[Embedding] "
            f"{batch_no}/"
            f"{len(embedding_batches)} "
            f"({len(chunk_batch)} 条)"
        )

        rows = build_milvus_rows(
            embedding_client,
            chunk_batch,
        )

        pending_rows.extend(rows)

        # 累计到 100 条再写 Milvus
        if (
            len(pending_rows)
            >= MILVUS_INSERT_BATCH_SIZE
        ):
            result = client.insert(
                collection_name=COLLECTION_NAME,
                data=pending_rows,
            )

            server_insert_count = int(
                result.get(
                    "insert_count",
                    len(pending_rows),
                )
            )

            inserted_total += server_insert_count

            print(
                f"[Milvus] 本批请求: "
                f"{len(pending_rows)} 条, "
                f"服务端确认: "
                f"{server_insert_count} 条, "
                f"累计确认: "
                f"{inserted_total}"
            )

            print(
                f"[Milvus] 已插入: "
                f"{inserted_total}"
            )

            pending_rows = []

    # 写入最后不足 100 条的数据
    if pending_rows:
        client.insert(
            collection_name=COLLECTION_NAME,
            data=pending_rows,
        )

        inserted_total += len(
            pending_rows
        )

        print(
            f"[Milvus] 已插入: "
            f"{inserted_total}"
        )

# 强制 flush，确保 Milvus 完成数据持久化和统计刷新
print("[Milvus] 正在 flush...")

client.flush(
    collection_name=COLLECTION_NAME,
)

stats = client.get_collection_stats(
    collection_name=COLLECTION_NAME,
)

row_count = int(
    stats.get("row_count", 0)
)

elapsed = time.time() - start_time

print("=" * 60)
print("导入完成")
print(f"脚本累计提交: {inserted_total}")
print(f"Milvus row_count: {row_count}")
print(f"耗时: {elapsed:.2f} 秒")
print("=" * 60)

if row_count != inserted_total:
    print(
        "[警告] Milvus 当前统计数量 "
        f"{row_count} 与脚本提交数量 "
        f"{inserted_total} 不一致"
    )

if __name__ == "__main__":
    main()