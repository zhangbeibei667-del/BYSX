"""Build deterministic, reviewable RAG and Agent evaluation sets."""

from __future__ import annotations

import json
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "member3" / "data" / "processed" / "rag_corpus_clean.jsonl"
EVALUATION = ROOT / "evaluation"


def _load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def build_rag() -> list[dict]:
    records = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    qg = [row for row in records if row.get("source") == "TCM-QG" and row.get("metadata", {}).get("questions")]
    sd = [row for row in records if row.get("source") == "TCM-SD"
          and row.get("metadata", {}).get("section") == "overview"]
    # Fixed strides make the sample reproducible while covering the whole files.
    qg_sample = [qg[index] for index in range(0, len(qg), max(1, len(qg) // 60))][:60]
    sd_sample = [sd[index] for index in range(0, len(sd), max(1, len(sd) // 60))][:60]
    rows: list[dict] = []
    question_chunks: dict[str, list[str]] = {}
    for record in qg:
        for question in record["metadata"]["questions"]:
            normalized = "".join(character for character in question if character.isalnum())
            question_chunks.setdefault(normalized, []).append(record["chunk_id"])
    for index, record in enumerate(qg_sample, 1):
        question = record["metadata"]["questions"][0]
        normalized = "".join(character for character in question if character.isalnum())
        rows.append({
            "id": f"rag_qg_{index:03d}",
            "query": question,
            "expected_chunk_ids": question_chunks[normalized],
            "expected_categories": ["文献问答"],
            "expected_sources": ["TCM-QG"],
            "split": "held-out-query",
        })
    for index, record in enumerate(sd_sample, 1):
        syndrome = record["metadata"]["syndrome"]
        rows.append({
            "id": f"rag_sd_{index:03d}",
            "query": f"{syndrome}的定义、典型表现和辨证要点是什么？",
            "expected_chunk_ids": [record["chunk_id"]],
            "expected_categories": ["证候知识"],
            "expected_sources": ["TCM-SD"],
            "split": "generated-independent-query",
        })
    _write_jsonl(EVALUATION / "rag_formal_eval.jsonl", rows)
    return rows


def build_agent() -> list[dict]:
    herbs = [item for item in _load_json(ROOT / "entities" / "herb.json")
             if not any(marker in item["name"] for marker in ("汤", "丸", "散"))][:20]
    formulas = _load_json(ROOT / "entities" / "prescription.json")[:15]
    symptoms = _load_json(ROOT / "entities" / "symptom.json")[:20]
    rows: list[dict] = []
    common = ["graph_query", "literature_search", "knowledge_explanation", "safety_review"]
    formula_tools = ["graph_query", "sql_query", "literature_search", "formula_explanation",
                     "knowledge_explanation", "safety_review"]
    case_tools = ["symptom_analysis", "followup", "graph_query", "sql_query", "literature_search",
                  "formula_explanation", "knowledge_explanation", "safety_review"]
    for index, herb in enumerate(herbs, 1):
        rows.append({"id": f"knowledge_{index:03d}", "input": f"{herb['name']}有什么功效和禁忌？",
                     "expected_intent": "knowledge_query", "expected_entities": [herb["name"]],
                     "expected_tools": common})
    for index, formula in enumerate(formulas, 1):
        rows.append({"id": f"formula_{index:03d}", "input": f"{formula['name']}的组成和主治是什么？",
                     "expected_intent": "formula_query", "expected_entities": [formula["name"]],
                     "expected_tools": formula_tools})
    for index, herb in enumerate(herbs[:10], 1):
        rows.append({"id": f"literature_{index:03d}", "input": f"请给出{herb['name']}功效的药典或文献依据",
                     "expected_intent": "literature_query", "expected_entities": [herb["name"]],
                     "expected_tools": common})
    for index in range(10):
        pair = symptoms[index * 2:index * 2 + 2]
        names = [item["name"] for item in pair]
        rows.append({"id": f"case_{index + 1:03d}", "input": f"患者{'、'.join(names)}，请作教学辨证分析",
                     "expected_intent": "case_analysis", "expected_entities": names,
                     "expected_tools": case_tools, "followup_keywords": ["舌", "脉"]})
    for index, name in enumerate(("火星回魂神方", "量子养生丹", "太空补元汤", "玄铁安神丸", "银河清热散"), 1):
        rows.append({"id": f"insufficient_{index:03d}", "input": f"{name}的组成和功效是什么？",
                     "expected_intent": "formula_query", "expected_entities": [],
                     "expected_tools": formula_tools, "forbidden_entities": [name]})
    _write_jsonl(EVALUATION / "agent_delivery_eval.jsonl", rows)
    return rows


def main() -> None:
    EVALUATION.mkdir(parents=True, exist_ok=True)
    rag = build_rag()
    agent = build_agent()
    review_path = EVALUATION / "human_review_template.csv"
    with review_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["case_id", "question", "system_answer", "citations", "reviewer", "review_date",
                  "conclusion_correctness_0_2", "evidence_consistency_0_2", "dangerous_advice_0_1", "comments"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for case in [*rag[:20], *agent[:10]]:
            writer.writerow({"case_id": case["id"], "question": case.get("query") or case.get("input")})
    print(json.dumps({"rag_cases": len(rag), "agent_cases": len(agent)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
