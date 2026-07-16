"""File-level knowledge-graph quality audit used by CI and delivery reports."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from server.schemas import validate_relation


ROOT = Path(__file__).resolve().parents[2]


def _items(path: Path, key: str) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return [item for item in raw.get(key, raw.get("items", [])) if isinstance(item, dict)]


def audit_kg(root: Path = ROOT) -> dict[str, Any]:
    entities: dict[str, dict[str, Any]] = {}
    duplicate_entity_ids: list[str] = []
    for path in sorted((root / "entities").glob("*.json")):
        for entity in _items(path, "entities"):
            entity_id = str(entity.get("id", "")).strip()
            if entity_id in entities:
                duplicate_entity_ids.append(entity_id)
            entities[entity_id] = entity

    relations: list[tuple[str, int, dict[str, Any]]] = []
    for path in sorted((root / "relations").glob("*.json")):
        for index, relation in enumerate(_items(path, "relations"), 1):
            relations.append((path.name, index, relation))

    seen: set[tuple[str, str, str]] = set()
    duplicate_relations: list[dict[str, Any]] = []
    dangling: list[dict[str, Any]] = []
    missing_evidence: list[dict[str, Any]] = []
    name_mismatches: list[dict[str, Any]] = []
    invalid_constraints: list[dict[str, Any]] = []
    evidence_levels = Counter()
    relation_types = Counter()

    for file_name, row, relation in relations:
        source_id = str(relation.get("source_id", "")).strip()
        target_id = str(relation.get("target_id", "")).strip()
        relation_name = str(relation.get("relation", "")).strip()
        key = (source_id, relation_name, target_id)
        location = {"file": file_name, "row": row, "key": "|".join(key)}
        if key in seen:
            duplicate_relations.append(location)
        seen.add(key)
        relation_types[relation_name] += 1
        evidence_levels[str(relation.get("evidence_level") or "未标注")] += 1

        source = entities.get(source_id)
        target = entities.get(target_id)
        if source is None or target is None:
            dangling.append({**location, "missing_source": source is None, "missing_target": target is None})
            continue
        if relation.get("source_name") and relation["source_name"] != source.get("name"):
            name_mismatches.append({**location, "side": "source", "stored": relation["source_name"],
                                    "actual": source.get("name", "")})
        if relation.get("target_name") and relation["target_name"] != target.get("name"):
            name_mismatches.append({**location, "side": "target", "stored": relation["target_name"],
                                    "actual": target.get("name", "")})
        try:
            validate_relation(relation_name, str(source.get("type", "")), str(target.get("type", "")), strict=True)
        except ValueError as exc:
            invalid_constraints.append({**location, "reason": str(exc)})
        if not str(relation.get("evidence") or "").strip():
            missing_evidence.append(location)

    entity_types = Counter(str(entity.get("type", "")) for entity in entities.values())
    disease_ids = {entity_id for entity_id, entity in entities.items() if entity.get("type") == "疾病"}
    connected_disease_ids = {
        str(relation.get("source_id"))
        for _, _, relation in relations
        if relation.get("relation") == "常见证候" and relation.get("source_id") in disease_ids
    }

    critical = {
        "duplicate_entity_ids": len(duplicate_entity_ids),
        "duplicate_relations": len(duplicate_relations),
        "dangling_relations": len(dangling),
        "missing_evidence": len(missing_evidence),
        "invalid_relation_constraints": len(invalid_constraints),
    }
    return {
        "passed": all(value == 0 for value in critical.values()),
        "critical": critical,
        "warnings": {"endpoint_name_mismatches": len(name_mismatches)},
        "summary": {
            "entities": len(entities),
            "relations": len(relations),
            "evidence_coverage": round((len(relations) - len(missing_evidence)) / max(1, len(relations)), 4),
            "entity_types": dict(sorted(entity_types.items())),
            "relation_types": dict(sorted(relation_types.items())),
            "evidence_levels": dict(sorted(evidence_levels.items())),
            "diseases": len(disease_ids),
            "diseases_with_syndrome_relations": len(connected_disease_ids),
        },
        "details": {
            "duplicate_entity_ids": duplicate_entity_ids,
            "duplicate_relations": duplicate_relations,
            "dangling_relations": dangling,
            "missing_evidence": missing_evidence,
            "invalid_relation_constraints": invalid_constraints,
            "endpoint_name_mismatches": name_mismatches,
        },
    }


def assert_kg_quality(root: Path = ROOT) -> dict[str, Any]:
    report = audit_kg(root)
    if not report["passed"]:
        raise RuntimeError(f"知识图谱质量门禁失败：{report['critical']}")
    return report
