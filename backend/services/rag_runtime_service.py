from __future__ import annotations

import hashlib
import json
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

from backend.db.database import DB_PATH, get_connection, init_db
from backend.services.llm_client import get_llm_client


REQUIRED_CATEGORIES = ("教材", "药典", "方剂说明", "科普资料")
ROOT = Path(__file__).resolve().parents[2]
CORPUS_SOURCES = (
    ROOT / "member3" / "data" / "processed" / "rag_corpus_clean.jsonl",
    ROOT / "member3" / "data" / "pharmacopoeia" / "processed" / "hkcmms" / "index_ready" / "chunks_for_milvus.jsonl",
)


def ensure_rag_initialized(force: bool = False) -> dict:
    """初始化 SQLite 文档库和四类可检索语料；可安全重复执行。"""
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT d.category, COUNT(DISTINCT d.id), COUNT(c.id)
               FROM documents d LEFT JOIN document_chunks c ON c.document_id=d.id
               GROUP BY d.category"""
        ).fetchall()
    current = {row[0]: {"documents": row[1], "chunks": row[2]} for row in rows}
    if force or any(category not in current or current[category]["chunks"] == 0
                    for category in REQUIRED_CATEGORIES):
        from backend.scripts.build_classified_corpus import build
        build()
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT d.category, COUNT(DISTINCT d.id), COUNT(c.id)
                   FROM documents d LEFT JOIN document_chunks c ON c.document_id=d.id
                   GROUP BY d.category"""
            ).fetchall()
        current = {row[0]: {"documents": row[1], "chunks": row[2]} for row in rows}
    return {"ready": all(current.get(item, {}).get("chunks", 0) > 0 for item in REQUIRED_CATEGORIES),
            "categories": current, "database": str(DB_PATH)}


def _jsonl_info(path: Path) -> dict:
    count = 0
    if path.exists():
        with path.open("rb") as handle:
            for line in handle:
                count += bool(line.strip())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        digest = ""
    return {"path": str(path.relative_to(ROOT)), "exists": path.exists(), "records": count,
            "sha256": digest, "bytes": path.stat().st_size if path.exists() else 0}


def _qdrant_status() -> dict:
    configured = os.getenv("QDRANT_ENABLED", "true").lower() == "true"
    if not configured:
        return {"status": "disabled", "configured": False}
    try:
        from backend.services.qdrant_vector_store import get_qdrant_vector_store
        store = get_qdrant_vector_store()
        info = store.client.get_collection(store.collection)
        with get_connection() as conn:
            sqlite_chunks = int(conn.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0])
        corpus_records = _jsonl_info(CORPUS_SOURCES[0])["records"]
        expected_points = sqlite_chunks + corpus_records
        return {"status": "ready", "configured": True, "deployment": store.deployment,
                "url": store.url or "local-path",
                "collection": store.collection, "embedding_provider": store.provider,
                "model": store.model_name, "dimensions": store.dimension,
                "query_embedding_available": store.embedding_available,
                "points": info.points_count, "expected_points": expected_points,
                "corpus_fully_indexed": info.points_count == expected_points,
                "semantic_embeddings": store.provider not in {"hash", "local-hash"}}
    except Exception as exc:
        return {"status": "unavailable", "configured": True, "error": str(exc)}


def _milvus_status() -> dict:
    enabled = os.getenv("MILVUS_ENABLED", "false").lower() == "true"
    uri = os.getenv("MILVUS_URI", "http://127.0.0.1:19530")
    collection = os.getenv("MILVUS_COLLECTION", "tcm_rag_chunks")
    if not enabled:
        return {"status": "disabled", "configured": False, "uri": uri, "collection": collection,
                "import_artifact": _jsonl_info(CORPUS_SOURCES[1])}
    try:
        parsed = urlparse(uri if "://" in uri else f"http://{uri}")
        with socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 19530), timeout=1.5):
            pass
        from pymilvus import MilvusClient
        client = MilvusClient(uri=uri)
        collections = client.list_collections()
        if collection not in collections:
            return {"status": "collection-missing", "configured": True, "uri": uri,
                    "collection": collection, "collections": collections}
        stats = client.get_collection_stats(collection_name=collection)
        return {"status": "ready", "configured": True, "uri": uri,
                "collection": collection, "row_count": int(stats.get("row_count", 0))}
    except Exception as exc:
        return {"status": "unavailable", "configured": True, "uri": uri,
                "collection": collection, "error": str(exc)}


def runtime_report() -> dict:
    sqlite = ensure_rag_initialized()
    llm = get_llm_client().status()
    llm["status"] = "ready" if llm["available"] else ("configured-disabled" if llm["configured"] else "disabled")
    sources = [_jsonl_info(path) for path in CORPUS_SOURCES]
    qdrant = _qdrant_status()
    return {
        "passed": sqlite["ready"] and all(item["exists"] and item["records"] > 0 for item in sources)
                  and qdrant.get("corpus_fully_indexed", False) and qdrant.get("semantic_embeddings", False),
        "primary_service": "backend.services.rag_service.RAGService",
        "legacy_member3_role": "offline corpus/Milvus utilities and compatibility adapter",
        "sqlite": sqlite, "qdrant": qdrant, "milvus": _milvus_status(), "llm": llm,
        "source_corpora": sources,
    }


def write_runtime_report(path: Path | None = None) -> dict:
    report = runtime_report()
    target = path or ROOT / "docs" / "任务3_RAG运行状态报告.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
