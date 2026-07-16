"""Attach QA questions to existing Qdrant payloads without re-embedding vectors."""

from __future__ import annotations

import json
from pathlib import Path

from backend.services.qdrant_vector_store import get_qdrant_vector_store


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "member3" / "data" / "processed" / "rag_corpus_clean.jsonl"
POINT_BASE = 1_000_000_000


def sync(batch_size: int = 256) -> dict:
    store = get_qdrant_vector_store()
    metadata = []
    for index, line in enumerate(CORPUS.read_text(encoding="utf-8-sig").splitlines()):
        if not line.strip():
            continue
        item = json.loads(line)
        detail = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        metadata.append((POINT_BASE + index, [str(value) for value in detail.get("questions", [])]))
    updated = 0
    for start in range(0, len(metadata), batch_size):
        batch = metadata[start:start + batch_size]
        ids = [point_id for point_id, _ in batch]
        questions_by_id = dict(batch)
        points = store.client.retrieve(store.collection, ids=ids, with_payload=True, with_vectors=True)
        structs = []
        for point in points:
            payload = dict(point.payload or {})
            payload["questions"] = questions_by_id.get(int(point.id), [])
            structs.append(store.models.PointStruct(id=point.id, vector=point.vector, payload=payload))
        store.client.upsert(store.collection, points=structs, wait=True)
        updated += len(structs)
    report = {"passed": updated == len(metadata), "collection": store.collection,
              "corpus_records": len(metadata), "updated": updated}
    if not report["passed"]:
        raise RuntimeError(f"Qdrant payload 更新不完整: {report}")
    return report


if __name__ == "__main__":
    print(json.dumps(sync(), ensure_ascii=False, indent=2))
