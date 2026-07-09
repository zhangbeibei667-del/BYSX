from __future__ import annotations

from pymilvus import DataType, MilvusClient


MILVUS_URI = "http://127.0.0.1:19530"
COLLECTION_NAME = "tcm_rag_chunks"
EMBEDDING_DIM = 1024


def main() -> None:
    client = MilvusClient(uri=MILVUS_URI)

    # 已存在则不重复创建
    if COLLECTION_NAME in client.list_collections():
        print(f"Collection 已存在: {COLLECTION_NAME}")
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

    schema.add_field(
        field_name="embedding",
        datatype=DataType.FLOAT_VECTOR,
        dim=EMBEDDING_DIM,
    )

    index_params = client.prepare_index_params()

    index_params.add_index(
        field_name="embedding",
        index_type="AUTOINDEX",
        metric_type="COSINE",
    )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
        index_params=index_params,
    )

    print(f"创建成功: {COLLECTION_NAME}")


if __name__ == "__main__":
    main()