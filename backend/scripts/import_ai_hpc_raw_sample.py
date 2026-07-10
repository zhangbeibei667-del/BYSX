from __future__ import annotations

import argparse
import json
from pathlib import Path


TYPE_PREFIX = {
    "症状": "S",
    "证候": "Z",
    "方剂": "F",
    "药材": "H",
}


class RawAIHPCImporter:
    """Import the small raw sample shipped in the GitHub ZIP.

    The public GitHub repository does not include the full `merge_result`
    directory.  It includes a small raw-data sample under `data/`.  This script
    extracts useful symptom/syndrome/formula/herb links from that sample without
    pretending it is the full 3.4M-record KG.
    """

    def __init__(self, repo_dir: Path, output_dir: Path) -> None:
        self.repo_dir = repo_dir
        self.output_dir = output_dir
        self.entities: list[dict] = []
        self.relations: list[dict] = []
        self.name_to_id: dict[tuple[str, str], str] = {}
        self.counters = {prefix: 20000 for prefix in TYPE_PREFIX.values()}

    def run(self) -> None:
        self.import_symmap()
        self.import_cpmcp()
        self.write_outputs()

    def import_symmap(self) -> None:
        symmap_dir = self.repo_dir / "data" / "symmap"

        for syndrome_dir in (symmap_dir / "syndrome").glob("*"):
            if not syndrome_dir.is_dir():
                continue
            syndrome_name = syndrome_dir.name
            syndrome_id = self.ensure_entity("证候", syndrome_name, source_id=syndrome_dir.name)

            symptoms_file = syndrome_dir / "tcm_symptom.json"
            for item in read_data_items(symptoms_file):
                symptom_name = item.get("TCM_symptom_name") or item.get("Symptom_name")
                if not symptom_name:
                    continue
                symptom_id = self.ensure_entity("症状", symptom_name, source_id=item.get("TCM_symptom_id", ""))
                self.add_relation(symptom_id, symptom_name, "提示", syndrome_id, syndrome_name, "AI-HPC raw sample: symmap syndrome/tcm_symptom")

            herbs_file = syndrome_dir / "herb.json"
            for item in read_data_items(herbs_file):
                herb_name = item.get("Chinese_name") or item.get("name_chinese")
                if not herb_name:
                    continue
                herb_id = self.ensure_entity("药材", herb_name, source_id=item.get("Herb_id", ""))
                self.add_relation(herb_id, herb_name, "关联证候", syndrome_id, syndrome_name, "AI-HPC raw sample: symmap syndrome/herb")

        for symptom_dir in (symmap_dir / "symptom").glob("*"):
            if not symptom_dir.is_dir():
                continue
            symptom_name = symptom_dir.name

            herbs_file = symptom_dir / "herb.json"
            for item in read_data_items(herbs_file):
                herb_name = item.get("Chinese_name") or item.get("name_chinese")
                if not herb_name:
                    continue
                herb_id = self.ensure_entity("药材", herb_name, source_id=item.get("Herb_id", ""))
                symptom_id = self.ensure_entity("症状", symptom_name, source_id=symptom_dir.name)
                self.add_relation(herb_id, herb_name, "关联症状", symptom_id, symptom_name, "AI-HPC raw sample: symmap symptom/herb")

    def import_cpmcp(self) -> None:
        cpmcp_dir = self.repo_dir / "data" / "CPMCP"

        for symptom_dir in (cpmcp_dir / "TCM symptom").glob("*"):
            if not symptom_dir.is_dir():
                continue
            symptom_name = f"CPMCP症状{symptom_dir.name}"
            symptom_id = self.ensure_entity("症状", symptom_name, source_id=symptom_dir.name)

            cpm_file = symptom_dir / "cpm.json"
            for item in read_count_items(cpm_file):
                formula_name = item.get("name")
                if not formula_name:
                    continue
                formula_id = self.ensure_entity("方剂", formula_name, source_id=str(item.get("id", "")))
                self.add_relation(formula_id, formula_name, "关联症状", symptom_id, symptom_name, "AI-HPC raw sample: CPMCP TCM symptom/cpm")

            herb_file = symptom_dir / "herb.json"
            for item in read_count_items(herb_file):
                herb_name = item.get("name_chinese") or item.get("Chinese_name")
                if not herb_name:
                    continue
                herb_id = self.ensure_entity("药材", herb_name, source_id=str(item.get("id", "")))
                self.add_relation(herb_id, herb_name, "关联症状", symptom_id, symptom_name, "AI-HPC raw sample: CPMCP TCM symptom/herb")

        for cpm_dir in (cpmcp_dir / "cpm").glob("*"):
            if not cpm_dir.is_dir():
                continue
            formula_name = f"CPMCP方剂{cpm_dir.name}"
            formula_id = self.ensure_entity("方剂", formula_name, source_id=cpm_dir.name)

            herb_file = cpm_dir / "herb.json"
            for item in read_count_items(herb_file):
                herb_name = item.get("name_chinese") or item.get("Chinese_name")
                if not herb_name:
                    continue
                herb_id = self.ensure_entity("药材", herb_name, source_id=str(item.get("id", "")))
                self.add_relation(formula_id, formula_name, "包含", herb_id, herb_name, "AI-HPC raw sample: CPMCP cpm/herb")

    def ensure_entity(self, entity_type: str, name: str, source_id: str = "") -> str:
        name = str(name).strip()
        key = (entity_type, name)
        if key in self.name_to_id:
            return self.name_to_id[key]

        prefix = TYPE_PREFIX[entity_type]
        self.counters[prefix] += 1
        entity_id = f"{prefix}R{self.counters[prefix]}"
        self.name_to_id[key] = entity_id
        self.entities.append(
            {
                "id": entity_id,
                "name": name,
                "type": entity_type,
                "alias": source_id,
                "description": "",
                "properties": {
                    "source": "AI-HPC raw sample",
                    "note": "Imported from raw sample files included in the GitHub ZIP; not the full merge_result KG.",
                },
            }
        )
        return entity_id

    def add_relation(self, source_id: str, source_name: str, relation: str, target_id: str, target_name: str, evidence: str) -> None:
        self.relations.append(
            {
                "source_id": source_id,
                "source_name": source_name,
                "relation": relation,
                "target_id": target_id,
                "target_name": target_name,
                "evidence": evidence,
            }
        )

    def write_outputs(self) -> None:
        entities_dir = self.output_dir / "entities"
        relations_dir = self.output_dir / "relations"
        entities_dir.mkdir(parents=True, exist_ok=True)
        relations_dir.mkdir(parents=True, exist_ok=True)

        entities = dedupe_entities(self.entities)
        relations = dedupe_relations(self.relations)
        (entities_dir / "entities_ai_hpc_raw_sample.json").write_text(json.dumps(entities, ensure_ascii=False, indent=2), encoding="utf-8")
        (relations_dir / "relations_ai_hpc_raw_sample.json").write_text(json.dumps(relations, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Imported raw sample entities: {len(entities)}")
        print(f"Imported raw sample relations: {len(relations)}")


def read_data_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    return data.get("data", []) if isinstance(data, dict) else []


def read_count_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    return data.get("items", []) if isinstance(data, dict) else []


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Import AI-HPC GitHub raw sample files into local KG JSON.")
    parser.add_argument("--repo-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("integrated_entities_graphrag/data"))
    args = parser.parse_args()
    RawAIHPCImporter(args.repo_dir, args.output_dir).run()


if __name__ == "__main__":
    main()
