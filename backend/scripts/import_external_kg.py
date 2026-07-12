from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


TYPE_PREFIX = {
    "症状": "S",
    "证候": "Z",
    "方剂": "F",
    "药材": "H",
}


RELATION_FILE_HINTS = {
    "syndrome2tcm_symptom": ("症状", "提示", "证候"),
    "prescription2symptom": ("症状", "提示", "方剂"),
    "prescription2medicinal_material": ("方剂", "包含", "药材"),
    "herb2symptom": ("药材", "关联症状", "症状"),
    "herb2syndrome": ("药材", "关联证候", "证候"),
}


ENTITY_FILE_HINTS = {
    "symptom": "症状",
    "tcm_symptom": "症状",
    "syndrome": "证候",
    "prescription": "方剂",
    "formula": "方剂",
    "medicinal_material": "药材",
    "herb": "药材",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import selected external TCM KG CSV/TSV files into the local "
            "entities_relations JSON format. Designed for AI-HPC TCM_knowledge_graph "
            "processed exports; also works for similarly named two-column relation files."
        )
    )
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory containing external CSV/TSV files")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("integrated_entities_graphrag/data"),
        help="Local KG data directory",
    )
    parser.add_argument("--source", default="external_kg_import", help="Source label written to properties/evidence")
    parser.add_argument("--limit", type=int, default=0, help="Optional max rows per file; 0 means all")
    args = parser.parse_args()

    importer = ExternalKGImporter(args.input_dir, args.output_dir, args.source, args.limit or None)
    importer.run()


class ExternalKGImporter:
    def __init__(self, input_dir: Path, output_dir: Path, source: str, limit: int | None = None) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.source = source
        self.limit = limit
        self.entity_name_to_id: dict[tuple[str, str], str] = {}
        self.entities: list[dict] = []
        self.relations: list[dict] = []
        self.type_counters = {prefix: 10000 for prefix in TYPE_PREFIX.values()}

    def run(self) -> None:
        files = sorted([path for path in self.input_dir.rglob("*") if path.suffix.lower() in {".csv", ".tsv"}])
        if not files:
            raise FileNotFoundError(f"No CSV/TSV files found under {self.input_dir}")

        for path in files:
            lower_name = path.stem.lower()
            relation_hint = self._match_hint(lower_name, RELATION_FILE_HINTS)
            entity_hint = self._match_hint(lower_name, ENTITY_FILE_HINTS)

            if relation_hint:
                self._import_relation_file(path, relation_hint)
            elif entity_hint:
                self._import_entity_file(path, entity_hint)

        self._write_outputs()

    @staticmethod
    def _match_hint(name: str, hints: dict):
        for key, value in hints.items():
            if key in name:
                return value
        return None

    def _import_entity_file(self, path: Path, entity_type: str) -> None:
        for index, row in enumerate(read_table(path), start=1):
            if self.limit and index > self.limit:
                break
            name = first_present(row, ["name", "entity", "label", "名称", "实体", "中文名"])
            if not name:
                name = first_non_empty_value(row)
            if name:
                self._ensure_entity(entity_type, name)

    def _import_relation_file(self, path: Path, hint: tuple[str, str, str]) -> None:
        source_type, relation_name, target_type = hint
        for index, row in enumerate(read_table(path), start=1):
            if self.limit and index > self.limit:
                break

            source_name, target_name = self._extract_relation_names(row)
            if not source_name or not target_name:
                continue

            source_id = self._ensure_entity(source_type, source_name)
            target_id = self._ensure_entity(target_type, target_name)
            self.relations.append(
                {
                    "source_id": source_id,
                    "source_name": source_name,
                    "relation": relation_name,
                    "target_id": target_id,
                    "target_name": target_name,
                    "evidence": self.source,
                }
            )

    @staticmethod
    def _extract_relation_names(row: dict[str, str]) -> tuple[str, str]:
        left = first_present(row, ["source", "head", "from", "src", "主体", "头实体", "起点", "0"])
        right = first_present(row, ["target", "tail", "to", "dst", "客体", "尾实体", "终点", "1"])
        if left and right:
            return left, right

        values = [value.strip() for value in row.values() if value and value.strip()]
        if len(values) >= 2:
            return values[0], values[1]
        return "", ""

    def _ensure_entity(self, entity_type: str, name: str) -> str:
        name = clean_text(name)
        key = (entity_type, name)
        if key in self.entity_name_to_id:
            return self.entity_name_to_id[key]

        prefix = TYPE_PREFIX[entity_type]
        self.type_counters[prefix] += 1
        entity_id = f"{prefix}X{self.type_counters[prefix]}"
        self.entity_name_to_id[key] = entity_id
        self.entities.append(
            {
                "id": entity_id,
                "name": name,
                "type": entity_type,
                "alias": "",
                "description": "",
                "properties": {
                    "source": self.source,
                    "note": "Imported from external TCM KG dataset; review before production use.",
                },
            }
        )
        return entity_id

    def _write_outputs(self) -> None:
        entities_dir = self.output_dir / "entities"
        relations_dir = self.output_dir / "relations"
        entities_dir.mkdir(parents=True, exist_ok=True)
        relations_dir.mkdir(parents=True, exist_ok=True)

        entities_path = entities_dir / "entities_external_import.json"
        relations_path = relations_dir / "relations_external_import.json"

        write_json(entities_path, dedupe_entities(self.entities))
        write_json(relations_path, dedupe_relations(self.relations))

        print(f"Wrote {entities_path}")
        print(f"Wrote {relations_path}")
        print(f"Entities: {len(dedupe_entities(self.entities))}")
        print(f"Relations: {len(dedupe_relations(self.relations))}")


def read_table(path: Path) -> list[dict[str, str]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    sample = text[:4096]
    if path.suffix.lower() == ".csv" and sample.count("\t") > sample.count(","):
        delimiter = "\t"

    lines = text.splitlines()
    if not lines:
        return []

    has_header = any(token.lower() in lines[0].lower() for token in ["source", "target", "head", "tail", "name"])
    if has_header:
        reader = csv.DictReader(lines, delimiter=delimiter)
        return [dict(row) for row in reader]

    reader = csv.reader(lines, delimiter=delimiter)
    return [{str(index): value for index, value in enumerate(row)} for row in reader]


def first_present(row: dict[str, str], keys: list[str]) -> str:
    lower_map = {key.lower(): value for key, value in row.items()}
    for key in keys:
        value = lower_map.get(key.lower())
        if value and value.strip():
            return clean_text(value)
    return ""


def first_non_empty_value(row: dict[str, str]) -> str:
    for value in row.values():
        if value and value.strip():
            return clean_text(value)
    return ""


def clean_text(value: str) -> str:
    return str(value).strip().strip('"').strip("'")


def dedupe_entities(items: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    result = []
    for item in items:
        key = (item["type"], item["name"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def dedupe_relations(items: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    result = []
    for item in items:
        key = (item["source_id"], item["relation"], item["target_id"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def write_json(path: Path, data: list[dict]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
