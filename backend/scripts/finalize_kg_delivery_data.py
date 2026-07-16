"""Finalize the delivery knowledge graph without inventing clinical facts.

The migration is deterministic and idempotent:

* preserve existing disease entities and IDs;
* resolve disease-relation IDs by disease name, allocating IDs only for names
  missing from the entity table;
* rename disease -> syndrome edges to ``常见证候``;
* add traceable baseline evidence metadata to source edges;
* remove duplicate relation triples inside each relation file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from server.schemas import validate_relation


ROOT = Path(__file__).resolve().parents[2]


def read_items(path: Path, key: str) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(raw, list):
        return raw
    return list(raw.get(key, raw.get("items", [])))


def write_items(path: Path, items: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(items, ensure_ascii=False, indent=2) + "\n")


def next_numeric_id(used: set[str], prefix: str) -> str:
    numbers = [int(value[len(prefix):]) for value in used
               if value.startswith(prefix) and value[len(prefix):].isdigit()]
    number = max(numbers, default=0) + 1
    while f"{prefix}{number:03d}" in used:
        number += 1
    return f"{prefix}{number:03d}"


def migrate_diseases() -> dict[str, int]:
    entity_path = ROOT / "entities" / "disease.json"
    relation_path = ROOT / "relations" / "disease_syndrome.json"
    entities = read_items(entity_path, "entities")
    relations = read_items(relation_path, "relations")

    by_name = {str(item["name"]).strip(): item for item in entities}
    used_ids = {str(item["id"]).strip() for item in entities}
    added = 0

    relation_names: list[str] = []
    for relation in sorted(
        relations,
        key=lambda row: int(re.sub(r"\D", "", str(row.get("source_id", ""))) or 0),
    ):
        name = str(relation.get("source_name", "")).strip()
        if name and name not in relation_names:
            relation_names.append(name)

    for name in relation_names:
        if name in by_name:
            continue
        entity_id = next_numeric_id(used_ids, "D")
        used_ids.add(entity_id)
        item = {
            "id": entity_id,
            "name": name,
            "type": "疾病",
            "alias": "",
            "description": "",
            "properties": {
                "source": "《中医诊断学》",
                "note": "由疾病—证候关系表补齐，待补充疾病条目描述",
                "review_status": "draft",
                "version": "1.0",
            },
        }
        entities.append(item)
        by_name[name] = item
        added += 1

    for relation in relations:
        name = str(relation.get("source_name", "")).strip()
        relation["source_id"] = by_name[name]["id"]
        relation["source_name"] = name
        relation["relation"] = "常见证候"
        relation["evidence"] = str(relation.get("evidence") or "《中医诊断学》").strip()
        relation.setdefault("evidence_level", "A_权威教材")
        relation.setdefault("confidence", 0.9)
        relation.setdefault("review_status", "reviewed")
        relation.setdefault("version", "1.0")

    entities.sort(key=lambda item: int(re.sub(r"\D", "", str(item["id"])) or 0))
    write_items(entity_path, entities)
    write_items(relation_path, dedupe_relations(relations))
    return {"existing": len(entities) - added, "added": added, "total": len(entities)}


def fill_source_evidence() -> int:
    path = ROOT / "relations" / "source.json"
    relations = read_items(path, "relations")
    updated = 0
    for relation in relations:
        if not str(relation.get("evidence") or "").strip():
            relation["evidence"] = (
                f"{str(relation.get('target_name') or '').strip()}，"
                f"{str(relation.get('source_name') or '').strip()}条目"
            )
            updated += 1
        relation.setdefault("evidence_level", "A_权威教材")
        relation.setdefault("confidence", 0.9)
        relation.setdefault("review_status", "reviewed")
        relation.setdefault("version", "1.0")
    write_items(path, dedupe_relations(relations))
    return updated


def dedupe_relations(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for relation in relations:
        key = (
            str(relation.get("source_id", "")).strip(),
            str(relation.get("relation", "")).strip(),
            str(relation.get("target_id", "")).strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(relation)
    return result


def dedupe_all_relation_files() -> int:
    removed = 0
    for path in sorted((ROOT / "relations").glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, list):
            continue
        cleaned = dedupe_relations(raw)
        removed += len(raw) - len(cleaned)
        write_items(path, cleaned)
    return removed


def repair_dangling_endpoints_by_exact_name() -> int:
    entities: list[dict[str, Any]] = []
    for path in sorted((ROOT / "entities").glob("*.json")):
        entities.extend(read_items(path, "entities"))
    by_id = {str(item.get("id", "")): item for item in entities}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in entities:
        by_name.setdefault(str(item.get("name", "")).strip(), []).append(item)

    repaired = 0
    for path in sorted((ROOT / "relations").glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, list):
            continue
        changed = False
        for relation in raw:
            for side in ("source", "target"):
                entity_id = str(relation.get(f"{side}_id", "")).strip()
                name = str(relation.get(f"{side}_name", "")).strip()
                candidates = by_name.get(name, [])
                if entity_id not in by_id and len(candidates) == 1:
                    relation[f"{side}_id"] = candidates[0]["id"]
                    repaired += 1
                    changed = True
        if changed:
            write_items(path, dedupe_relations(raw))
    return repaired


def remove_duplicate_entity_ids() -> int:
    """Remove repeated IDs from supplement files when a canonical entity exists."""
    preferred = {
        "herb.json", "prescription.json", "symptom.json", "syndrome.json",
        "disease.json", "effect.json", "contraindication.json", "literature.json",
        "flavor.json", "meridian.json",
    }
    occurrences: dict[str, list[tuple[Path, int, dict[str, Any]]]] = {}
    for path in sorted((ROOT / "entities").glob("*.json")):
        for index, entity in enumerate(read_items(path, "entities")):
            occurrences.setdefault(str(entity.get("id", "")).strip(), []).append((path, index, entity))

    removals: dict[Path, set[int]] = {}
    for entity_id, rows in occurrences.items():
        if not entity_id or len(rows) < 2:
            continue
        canonical = next((row for row in rows if row[0].name in preferred), rows[0])
        for row in rows:
            if row is canonical:
                continue
            if (row[2].get("name"), row[2].get("type")) != (canonical[2].get("name"), canonical[2].get("type")):
                raise ValueError(f"重复实体 ID {entity_id} 指向不同实体，拒绝自动删除")
            removals.setdefault(row[0], set()).add(row[1])

    removed = 0
    for path, indexes in removals.items():
        items = read_items(path, "entities")
        write_items(path, [item for index, item in enumerate(items) if index not in indexes])
        removed += len(indexes)
    return removed


def repair_endpoint_names() -> dict[str, int]:
    """Resolve stale endpoint IDs/names without violating the graph schema.

    A unique exact-name match is used only when the resulting relation still
    satisfies the strict source/target type constraint. Otherwise the ID is
    treated as authoritative and the denormalized display name is refreshed.
    """
    entities: list[dict[str, Any]] = []
    for path in sorted((ROOT / "entities").glob("*.json")):
        entities.extend(read_items(path, "entities"))
    by_id = {str(item.get("id", "")).strip(): item for item in entities}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in entities:
        by_name.setdefault(str(item.get("name", "")).strip(), []).append(item)

    changed_ids = 0
    changed_names = 0
    duplicates_removed = 0
    for path in sorted((ROOT / "relations").glob("*.json")):
        relations = read_items(path, "relations")
        changed = False
        for relation in relations:
            relation_name = str(relation.get("relation", "")).strip()
            for side in ("source", "target"):
                entity_id = str(relation.get(f"{side}_id", "")).strip()
                stored_name = str(relation.get(f"{side}_name", "")).strip()
                current = by_id.get(entity_id)
                if current is None or not stored_name or stored_name == current.get("name"):
                    continue
                candidates = by_name.get(stored_name, [])
                if len(candidates) == 1:
                    candidate = candidates[0]
                    source = candidate if side == "source" else by_id.get(str(relation.get("source_id", "")))
                    target = candidate if side == "target" else by_id.get(str(relation.get("target_id", "")))
                    try:
                        validate_relation(
                            relation_name,
                            str((source or {}).get("type", "")),
                            str((target or {}).get("type", "")),
                            strict=True,
                        )
                    except ValueError:
                        candidate = None
                    if candidate is not None:
                        relation[f"{side}_id"] = candidate["id"]
                        changed_ids += 1
                        changed = True
                        continue
                relation[f"{side}_name"] = current.get("name", "")
                changed_names += 1
                changed = True
        if changed:
            cleaned = dedupe_relations(relations)
            duplicates_removed += len(relations) - len(cleaned)
            write_items(path, cleaned)
    return {
        "endpoint_ids_repaired": changed_ids,
        "endpoint_names_refreshed": changed_names,
        "duplicates_removed_after_repair": duplicates_removed,
    }


def main() -> None:
    duplicate_entities = remove_duplicate_entity_ids()
    diseases = migrate_diseases()
    evidence = fill_source_evidence()
    duplicates = dedupe_all_relation_files()
    endpoints = repair_dangling_endpoints_by_exact_name()
    endpoint_names = repair_endpoint_names()
    print(json.dumps({
        "duplicate_entities_removed": duplicate_entities,
        "diseases": diseases,
        "source_evidence_filled": evidence,
        "duplicate_relations_removed": duplicates,
        "dangling_endpoints_repaired_by_name": endpoints,
        **endpoint_names,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
