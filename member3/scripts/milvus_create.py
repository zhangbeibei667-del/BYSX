from __future__ import annotations

import os

from dotenv import load_dotenv
from pymilvus import DataType, MilvusClient


OPTIONAL_TEXT_FIELDS = {
    "record_type": 64,
    "chinese_name": 128,
    "chinese_name_simplified": 128,
    "official_name": 256,
    "pinyin_name": 128,
    "section_type": 64,
    "section_number": 64,
    "section_title": 512,
    "parent_section": 512,
    "citation": 512,
    "source_url": 1024,
}


def main() -> None:
    load_dotenv()

    milvus_uri = os.getenv("MILVUS_URI", "http://127.0.0.1:19530")
    collection_name = os.getenv("MILVUS_COLLECTION", "tcm_rag_chunks")
    embedding_dim = int(os.getenv("EMBEDDING_DIM", os.getenv("EMBEDDING_DIMENSIONS", "1024")))

    client = MilvusClient(uri=milvus_uri)

    # 已存在则不重复创建
    if collection_name in client.list_collections():
        print(f"Collection 已存在: {collection_name}")
        return

    schema = client.create_schema(
        auto_id=True,
        enable_dynamic_field=False,
        description="TCM GraphRAG cleaned text chunks",
    )

    schema.add_field(
        field_name="id",
        datatype=DataType.INT64,
        is_primary=True,
    )

    schema.add_field(
        field_name="chunk_id",
        datatype=DataType.VARCHAR,
        max_length=128,
    )

    schema.add_field(
        field_name="doc_id",
        datatype=DataType.VARCHAR,
        max_length=128,
    )

    schema.add_field(
        field_name="title",
        datatype=DataType.VARCHAR,
        max_length=512,
    )

    schema.add_field(
        field_name="content",
        datatype=DataType.VARCHAR,
        max_length=8192,
    )

    schema.add_field(
        field_name="source",
        datatype=DataType.VARCHAR,
        max_length=64,
    )

    for field_name, max_length in OPTIONAL_TEXT_FIELDS.items():
        schema.add_field(
            field_name=field_name,
            datatype=DataType.VARCHAR,
            max_length=max_length,
        )

    schema.add_field(
        field_name="embedding",
        datatype=DataType.FLOAT_VECTOR,
        dim=embedding_dim,
    )

    index_params = client.prepare_index_params()

    index_params.add_index(
        field_name="embedding",
        index_type="AUTOINDEX",
        metric_type="COSINE",
    )

    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )

    print(f"创建成功: {collection_name}")


if __name__ == "__main__":
    main()
