"""Build the production Qdrant collection from SQLite and the 7,951-record corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from backend.db.database import get_connection, init_db
from backend.services.qdrant_vector_store import get_qdrant_vector_store


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "member3" / "data" / "processed" / "rag_corpus_clean.jsonl"
STATE = ROOT / "backend" / "data" / "qdrant_import_state.json"
MANIFEST = ROOT / "docs" / "rag_vector_import_report.json"
CORPUS_POINT_BASE = 1_000_000_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sqlite_records() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.document_id, c.chunk_index, c.content, c.locator_json,
                      d.title, d.source, d.category, d.edition, d.publisher,
                      d.identifier, d.source_url
               FROM document_chunks c JOIN documents d ON d.id=c.document_id
               ORDER BY c.document_id, c.chunk_index"""
        ).fetchall()
    return [{
        "point_id": row["document_id"] * 1_000_000 + row["chunk_index"],
        "document_id": row["document_id"],
        "chunk_index": row["chunk_index"],
        "content": row["content"],
        "embedding_text": "\n".join(filter(None, [
            row["category"], row["title"], row["source"] or "", row["content"],
        ])),
        "locator": json.loads(row["locator_json"] or "{}"),
        "title": row["title"],
        "source": row["source"] or row["title"],
        "category": row["category"],
        "edition": row["edition"] or "",
        "publisher": row["publisher"] or "",
        "identifier": row["identifier"] or "",
        "source_url": row["source_url"] or "",
        "corpus_record": False,
    } for row in rows]


def _corpus_records() -> list[dict]:
    records = []
    for index, line in enumerate(CORPUS.read_text(encoding="utf-8-sig").splitlines()):
        if not line.strip():
            continue
        item = json.loads(line)
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        source = str(item.get("source") or "补充语料")
        category = "证候知识" if metadata.get("record_type") == "syndrome_knowledge" else "文献问答"
        chunk_id = str(item.get("chunk_id") or f"corpus-{index}")
        records.append({
            "point_id": CORPUS_POINT_BASE + index,
            "document_id": CORPUS_POINT_BASE + index,
            "chunk_index": 0,
            "chunk_id": chunk_id,
            "content": str(item.get("content") or ""),
            "embedding_text": "\n".join(filter(None, [
                category, str(item.get("title") or chunk_id), source,
                *[str(question) for question in metadata.get("questions", [])],
                str(item.get("content") or ""),
            ])),
            "locator": {
                "chapter": str(metadata.get("section") or ""),
                "section": str(metadata.get("part") or ""),
                "page": metadata.get("page"),
            },
            "title": str(item.get("title") or chunk_id),
            "source": source,
            "category": category,
            "identifier": chunk_id,
            "source_url": str(metadata.get("source_url") or ""),
            "record_type": str(metadata.get("record_type") or ""),
            "questions": [str(question) for question in metadata.get("questions", [])],
            "corpus_record": True,
        })
    return records


def _upsert_batches(store, records: list[dict], start: int, stage: str, corpus_hash: str) -> None:
    request_size = store.batch_size * store.concurrency
    for offset in range(start, len(records), request_size):
        store.upsert(records[offset:offset + request_size])
        completed = min(offset + request_size, len(records))
        STATE.write_text(json.dumps({
            "collection": store.collection,
            "model": store.model_name,
            "dimensions": store.dimension,
            "corpus_sha256": corpus_hash,
            "stage": stage,
            "completed": completed,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        if completed % 100 == 0 or completed == len(records):
            print(f"{stage}: {completed}/{len(records)}", flush=True)


def run(reset: bool = False) -> dict:
    init_db()
    corpus_hash = _sha256(CORPUS)
    sqlite_records = _sqlite_records()
    corpus_records = _corpus_records()
    store = get_qdrant_vector_store()
    state = {}
    if STATE.exists() and not reset:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if state.get("collection") != store.collection or state.get("model") != store.model_name \
                or state.get("corpus_sha256") != corpus_hash:
            state = {}
    if reset or not state:
        store.reset()
        state = {"stage": "sqlite", "completed": 0}

    if state.get("stage") == "sqlite":
        _upsert_batches(store, sqlite_records, int(state.get("completed", 0)), "sqlite", corpus_hash)
        state = {"stage": "corpus", "completed": 0}
        STATE.write_text(json.dumps({
            "collection": store.collection, "model": store.model_name, "dimensions": store.dimension,
            "corpus_sha256": corpus_hash, **state,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    _upsert_batches(store, corpus_records, int(state.get("completed", 0)), "corpus", corpus_hash)

    info = store.client.get_collection(store.collection)
    expected = len(sqlite_records) + len(corpus_records)
    report = {
        "passed": info.points_count == expected,
        "collection": store.collection,
        "provider": store.provider,
        "model": store.model_name,
        "dimensions": store.dimension,
        "sqlite_chunks": len(sqlite_records),
        "corpus_records": len(corpus_records),
        "expected_points": expected,
        "actual_points": info.points_count,
        "corpus_sha256": corpus_hash,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE.write_text(json.dumps({**report, "stage": "complete", "completed": len(corpus_records)},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError(f"向量点数量不一致: {report}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="重建集合并从头导入")
    args = parser.parse_args()
    print(json.dumps(run(reset=args.reset), ensure_ascii=False, indent=2))
