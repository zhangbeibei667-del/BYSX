"""Build GraphRAG's JSON files from the canonical knowledge-graph data."""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENTITY_DIR = PROJECT_ROOT / "data" / "entities"
RELATION_DIR = PROJECT_ROOT / "data" / "relations"
OUTPUT_DIR = PROJECT_ROOT / "member3" / "data"


def load_split_json(directory: Path, pattern: str) -> list[dict]:
    records: list[dict] = []
    for path in sorted(directory.glob(pattern)):
        records.extend(json.loads(path.read_text(encoding="utf-8")))
    return records


def validate_and_normalize(
    entities: list[dict], relations: list[dict]
) -> tuple[list[dict], list[dict]]:
    entity_by_id: dict[str, dict] = {}
    for entity in entities:
        entity_id = entity["id"]
        if entity_id in entity_by_id:
            raise ValueError(f"Duplicate entity id: {entity_id}")
        entity_by_id[entity_id] = entity

    seen_relations: set[tuple[str, str, str]] = set()
    normalized_relations: list[dict] = []
    for relation in relations:
        source_id = relation["source_id"]
        target_id = relation["target_id"]
        if source_id not in entity_by_id:
            raise ValueError(f"Dangling source id: {source_id}")
        if target_id not in entity_by_id:
            raise ValueError(f"Dangling target id: {target_id}")

        key = (source_id, relation["relation"], target_id)
        if key in seen_relations:
            raise ValueError(f"Duplicate relation: {key}")
        seen_relations.add(key)

        item = dict(relation)
        # Display names are derived from canonical entities so blanks or stale
        # denormalized values cannot leak into GraphRAG responses.
        item["source_name"] = entity_by_id[source_id]["name"]
        item["target_name"] = entity_by_id[target_id]["name"]
        normalized_relations.append(item)

    return entities, normalized_relations


def main() -> None:
    entities = load_split_json(ENTITY_DIR, "entities_*.json")
    relations = load_split_json(RELATION_DIR, "relations_*.json")
    entities, relations = validate_and_normalize(entities, relations)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "entities.json").write_text(
        json.dumps(entities, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "relations.json").write_text(
        json.dumps(relations, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Synced {len(entities)} entities and {len(relations)} relations.")


if __name__ == "__main__":
    main()
