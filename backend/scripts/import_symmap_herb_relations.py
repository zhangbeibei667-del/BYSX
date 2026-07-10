from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


COMPONENT_CONFIG = {
    "TCM_symptom": {
        "id_col": "TCM symptom id",
        "name_col": "TCM symptom name",
        "type": "症状",
        "forward": "关联症状",
        "reverse": "相关药材",
    },
    "Syndrome": {
        "id_col": "Syndrome id",
        "name_col": "Syndrome name",
        "type": "证候",
        "forward": "关联证候",
        "reverse": "相关药材",
    },
    "MM_symptom": {
        "id_col": "MM symptom id",
        "name_col": "MM symptom name",
        "type": "现代症状",
        "forward": "关联现代症状",
        "reverse": "相关药材",
    },
    "Mol": {
        "id_col": "Ingredient id",
        "name_col": "Ingredient name",
        "type": "成分",
        "forward": "包含成分",
        "reverse": "来源药材",
    },
}


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().strip("\ufeff")
    if text.lower() in {"none", "null", "nan"}:
        return ""
    return text


def load_entities(entities_dir: Path) -> tuple[dict[str, dict], dict[str, str]]:
    entities_by_id: dict[str, dict] = {}
    herb_names: dict[str, str] = {}
    for path in entities_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            entity_id = clean(item.get("id"))
            if not entity_id:
                continue
            entities_by_id[entity_id] = item
            props = item.get("properties") or {}
            symmap_id = clean(props.get("symmap_id"))
            if item.get("type") == "药材":
                herb_names[entity_id] = clean(item.get("name"))
                if symmap_id:
                    herb_names[symmap_id] = clean(item.get("name"))
    return entities_by_id, herb_names


def read_csv(path: Path) -> list[dict[str, str]]:
    # SymMap returns UTF-8 CSV with BOM.  Some PowerShell views look garbled, but
    # Python decodes the downloaded bytes correctly with utf-8-sig.
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def import_relations(raw_dir: Path, graph_data_dir: Path) -> dict[str, Any]:
    entities_dir = graph_data_dir / "entities"
    relations_dir = graph_data_dir / "relations"
    relations_dir.mkdir(parents=True, exist_ok=True)
    entities_by_id, herb_names = load_entities(entities_dir)

    new_entities: dict[str, dict] = {}
    relations: dict[tuple[str, str, str], dict] = {}
    stats = {"files": 0, "rows": 0, "relations": 0, "new_entities": 0}

    for component, config in COMPONENT_CONFIG.items():
        component_dir = raw_dir / component
        if not component_dir.exists():
            continue
        for csv_path in sorted(component_dir.glob("SMHB*.csv")):
            stats["files"] += 1
            herb_id = csv_path.stem
            herb_name = herb_names.get(herb_id, herb_id)
            if not herb_name:
                continue

            for row in read_csv(csv_path):
                stats["rows"] += 1
                target_id = clean(row.get(config["id_col"]))
                target_name = clean(row.get(config["name_col"]))
                if not target_id or not target_name:
                    continue

                if target_id not in entities_by_id and target_id not in new_entities:
                    new_entities[target_id] = {
                        "id": target_id,
                        "name": target_name,
                        "type": config["type"],
                        "alias": "",
                        "description": "",
                        "properties": {
                            "source": "SymMap v2.0 related_components",
                            "symmap_component": component,
                        },
                    }

                evidence = f"SymMap v2.0 herb related_components: {herb_id} -> {component}"
                forward_key = (herb_id, config["forward"], target_id)
                relations[forward_key] = {
                    "source_id": herb_id,
                    "source_name": herb_name,
                    "relation": config["forward"],
                    "target_id": target_id,
                    "target_name": target_name,
                    "evidence": evidence,
                }

                reverse_key = (target_id, config["reverse"], herb_id)
                relations[reverse_key] = {
                    "source_id": target_id,
                    "source_name": target_name,
                    "relation": config["reverse"],
                    "target_id": herb_id,
                    "target_name": herb_name,
                    "evidence": evidence,
                }

    entity_output = entities_dir / "entities_symmap_relation_targets.json"
    relation_output = relations_dir / "relations_symmap_herb.json"
    entity_output.write_text(
        json.dumps(list(new_entities.values()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    relation_output.write_text(
        json.dumps(list(relations.values()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    stats["relations"] = len(relations)
    stats["new_entities"] = len(new_entities)
    stats["entity_output"] = str(entity_output)
    stats["relation_output"] = str(relation_output)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Import crawled SymMap herb relation CSV files into local KG JSON.")
    parser.add_argument(
        "--raw-dir",
        default="integrated_entities_graphrag/external_data/symmap_v2/herb_relations/raw",
    )
    parser.add_argument(
        "--graph-data-dir",
        default="integrated_entities_graphrag/data",
    )
    args = parser.parse_args()
    stats = import_relations(Path(args.raw_dir), Path(args.graph_data_dir))
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
