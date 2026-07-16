from __future__ import annotations

import atexit
import hashlib
import http.client
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _load_local_env() -> None:
    """Load repository-local configuration without overriding process env."""
    candidates = (Path(__file__).resolve().parents[1] / ".env", Path(__file__).resolve().parents[2] / ".env")
    for path in candidates:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()


class QdrantVectorStore:
    collection = os.getenv("QDRANT_COLLECTION", "tcm_documents_v3")
    provider = os.getenv("EMBEDDING_PROVIDER", "hash").lower()
    model_name = os.getenv("EMBEDDING_MODEL", "hash-bigram-v1")

    def __init__(self) -> None:
        from qdrant_client import QdrantClient, models

        self.models = models
        root = Path(os.getenv("QDRANT_PATH", str(Path(__file__).resolve().parents[1] / "data" / "qdrant_v3")))
        root.mkdir(parents=True, exist_ok=True)
        self.url = os.getenv("QDRANT_URL", "").strip().rstrip("/")
        self.api_key = os.getenv("QDRANT_API_KEY", "").strip()
        self.deployment = "remote-service" if self.url else "embedded-local"
        self.client = (
            QdrantClient(url=self.url, api_key=self.api_key or None, timeout=60, trust_env=False)
            if self.url
            else QdrantClient(path=str(root))
        )
        atexit.register(self.client.close)
        self.embedding = None
        self.dimension = int(os.getenv("EMBEDDING_DIMENSIONS", "384"))
        self.embedding_base_url = os.getenv(
            "EMBEDDING_BASE_URL", os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        ).rstrip("/")
        self.embedding_api_key = os.getenv("EMBEDDING_API_KEY", os.getenv("LLM_API_KEY", ""))
        self.embedding_available = self.provider not in {"dashscope", "aliyun-bailian"} or bool(self.embedding_api_key)
        self.batch_size = max(1, min(int(os.getenv("EMBEDDING_BATCH_SIZE", "10")), 10))
        self.concurrency = max(1, min(int(os.getenv("EMBEDDING_CONCURRENCY", "4")), 8))
        if self.provider == "fastembed":
            from fastembed import TextEmbedding

            self.embedding = TextEmbedding(model_name=self.model_name, cache_dir=str(root / "models"))
            self.dimension = len(next(iter(self.embedding.embed(["维度探测"]))))
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(size=self.dimension, distance=models.Distance.COSINE),
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
        vectors = self._embed_many([record.get("embedding_text") or record["content"] for record in records])
        points = [
            self.models.PointStruct(
                id=record["point_id"], vector=vector,
                payload={key: value for key, value in record.items() if key != "embedding_text"},
            )
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
        vector = self._embed_many([query], query=True)[0]
        response = self.client.query_points(self.collection, query=vector, limit=limit, with_payload=True)
        return [{**(point.payload or {}), "semantic_score": float(point.score),
                 "retrieval_mode": "qdrant-semantic"} for point in response.points]

    def _embed_many(self, texts: list[str], query: bool = False) -> list[list[float]]:
        if self.embedding is not None:
            method = self.embedding.query_embed if query else self.embedding.embed
            return [vector.tolist() for vector in method(texts)]
        if self.provider in {"dashscope", "aliyun-bailian"}:
            if not self.embedding_api_key:
                raise RuntimeError("阿里云向量模型已启用，但 EMBEDDING_API_KEY/LLM_API_KEY 未配置")
            batches = [texts[start:start + self.batch_size] for start in range(0, len(texts), self.batch_size)]
            with ThreadPoolExecutor(max_workers=min(self.concurrency, len(batches))) as executor:
                embedded_batches = list(executor.map(self._dashscope_embed, batches))
            vectors = [vector for batch in embedded_batches for vector in batch]
            return vectors
        return [self._hash_embed(text) for text in texts]

    def _dashscope_embed(self, texts: list[str]) -> list[list[float]]:
        payload = json.dumps({
            "model": self.model_name,
            "input": texts,
            "dimensions": self.dimension,
            "encoding_format": "float",
        }, ensure_ascii=False).encode("utf-8")
        last_error: Exception | None = None
        for attempt in range(5):
            request = urllib.request.Request(
                f"{self.embedding_base_url}/embeddings",
                data=payload,
                headers={"Authorization": f"Bearer {self.embedding_api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    body = json.loads(response.read().decode("utf-8"))
                rows = sorted(body.get("data", []), key=lambda item: int(item.get("index", 0)))
                vectors = [row["embedding"] for row in rows]
                if len(vectors) != len(texts) or any(len(vector) != self.dimension for vector in vectors):
                    raise RuntimeError("阿里云向量接口返回数量或维度不匹配")
                return vectors
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
                last_error = RuntimeError(f"阿里云向量接口 HTTP {exc.code}: {detail}")
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
            except (urllib.error.URLError, TimeoutError, RuntimeError, http.client.IncompleteRead,
                    ConnectionError, OSError) as exc:
                last_error = exc
            time.sleep(min(8.0, 0.75 * (2 ** attempt)))
        raise RuntimeError(f"阿里云向量化失败: {last_error}")

    def _hash_embed(self, text: str) -> list[float]:
        compact = re.sub(r"\s+", "", text.lower())
        terms = [compact[i:i + 2] for i in range(max(0, len(compact) - 1))]
        terms += re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]{1,6}", text.lower())
        counts: Counter[int] = Counter()
        for term in terms:
            idx = int.from_bytes(hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest(), "big") % self.dimension
            counts[idx] += 1
        norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
        return [counts.get(index, 0) / norm for index in range(self.dimension)]


_STORE: QdrantVectorStore | None = None


def get_qdrant_vector_store() -> QdrantVectorStore:
    if os.getenv("QDRANT_ENABLED", "true").lower() != "true":
        raise RuntimeError("Qdrant 已通过 QDRANT_ENABLED=false 禁用")
    global _STORE
    if _STORE is None:
        _STORE = QdrantVectorStore()
    return _STORE
