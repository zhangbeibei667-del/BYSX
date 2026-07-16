"""Copy an embedded Qdrant collection into the independent service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qdrant_client import QdrantClient, models


ROOT = Path(__file__).resolve().parents[2]


def migrate(source_path: Path, url: str, api_key: str, collection: str) -> dict:
    source = QdrantClient(path=str(source_path))
    target = QdrantClient(url=url, api_key=api_key or None, timeout=120,
                          check_compatibility=False, trust_env=False)
    try:
        source_info = source.get_collection(collection)
        vector_config = source_info.config.params.vectors
        if target.collection_exists(collection):
            target.delete_collection(collection)
        target.create_collection(collection, vectors_config=models.VectorParams(
            size=vector_config.size, distance=vector_config.distance,
        ))
        offset = None
        copied = 0
        while True:
            points, offset = source.scroll(collection_name=collection, limit=256, offset=offset,
                                           with_payload=True, with_vectors=True)
            if points:
                target.upsert(collection_name=collection, points=[models.PointStruct(
                    id=point.id, vector=point.vector, payload=point.payload or {},
                ) for point in points], wait=True)
                copied += len(points)
            if offset is None:
                break
        target_info = target.get_collection(collection)
        return {"collection": collection, "source_points": source_info.points_count,
                "copied_points": copied, "target_points": target_info.points_count,
                "verified": copied == target_info.points_count}
    finally:
        source.close()
        target.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "backend" / "data" / "qdrant_v3")
    parser.add_argument("--url", default="http://127.0.0.1:6333")
    parser.add_argument("--api-key", default="tcm_qdrant_local_dev")
    parser.add_argument("--collection", default="tcm_documents_v5")
    args = parser.parse_args()
    print(json.dumps(migrate(args.source, args.url, args.api_key, args.collection), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
