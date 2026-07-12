from __future__ import annotations

import os
import atexit
from pathlib import Path


class QdrantVectorStore:
    collection = "tcm_documents_v2"
    model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")

    def __init__(self) -> None:
        from fastembed import TextEmbedding
        from qdrant_client import QdrantClient, models

        self.models = models
        root = Path(__file__).resolve().parents[1] / "data" / "qdrant"
        root.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(root))
        atexit.register(self.client.close)
        self.embedding = TextEmbedding(model_name=self.model_name, cache_dir=str(root / "models"))
        dimension = len(next(iter(self.embedding.embed(["维度探测"]))))
        self.dimension = dimension
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            )

    def reset(self) -> None:
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
        self.client.create_collection(
            self.collection,
            vectors_config=self.models.VectorParams(size=self.dimension, distance=self.models.Distance.COSINE),
        )

    def upsert(self, records: list[dict]) -> None:
        if not records:
            return
        vectors = list(self.embedding.embed([record["content"] for record in records]))
        points = [
            self.models.PointStruct(id=record["point_id"], vector=vector.tolist(), payload=record)
            for record, vector in zip(records, vectors)
        ]
        self.client.upsert(self.collection, points=points, wait=True)

    def delete_document(self, document_id: int) -> None:
        self.client.delete(
            self.collection,
            points_selector=self.models.FilterSelector(filter=self.models.Filter(
                must=[self.models.FieldCondition(key="document_id", match=self.models.MatchValue(value=document_id))]
            )),
            wait=True,
        )

    def search(self, query: str, limit: int = 20) -> list[dict]:
        vector = next(iter(self.embedding.query_embed(query))).tolist()
        response = self.client.query_points(self.collection, query=vector, limit=limit, with_payload=True)
        return [{**(point.payload or {}), "semantic_score": float(point.score)} for point in response.points]


_STORE: QdrantVectorStore | None = None


def get_qdrant_vector_store() -> QdrantVectorStore:
    global _STORE
    if _STORE is None:
        _STORE = QdrantVectorStore()
    return _STORE
