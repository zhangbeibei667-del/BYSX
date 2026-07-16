"""Reproducible retrieval evaluation with hard evidence and citation gates."""

from __future__ import annotations

import json
from pathlib import Path

from backend.services.vector_retrieval_service import VectorRetrievalService


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evaluation" / "rag_formal_eval.jsonl"
JSON_REPORT = ROOT / "docs" / "任务3_RAG正式评测报告.json"
MD_REPORT = ROOT / "docs" / "任务3_RAG正式评测报告.md"


def _relevant(hit: dict, case: dict) -> bool:
    expected_ids = set(case.get("expected_chunk_ids", []))
    if expected_ids:
        return str(hit.get("id")) in expected_ids or str(hit.get("identifier")) in expected_ids
    categories = set(case.get("expected_categories", []))
    terms = case.get("expected_terms", [])
    category_ok = not categories or hit.get("category") in categories
    haystack = " ".join([str(hit.get("title", "")), str(hit.get("content", ""))])
    term_ok = not terms or any(term in haystack for term in terms)
    return category_ok and term_ok


def evaluate(top_k: int = 5) -> dict:
    service = VectorRetrievalService()
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    results = []
    reciprocal_ranks = []
    for case in cases:
        hits = service.search(case["query"], top_k=top_k)
        relevant_rank = next((rank for rank, hit in enumerate(hits, 1) if _relevant(hit, case)), None)
        categories = set(case.get("expected_categories", []))
        sources = set(case.get("expected_sources", []))
        checks = {
            "document_hits_gt_0": len(hits) > 0,
            "relevant_hit_at_k": relevant_rank is not None,
            "category_match": not categories or any(hit.get("category") in categories for hit in hits),
            "source_match": not sources or any(hit.get("source") in sources for hit in hits),
            "citations_locatable": bool(hits) and all(
                bool(hit.get("citation")) and bool((hit.get("trace") or {}).get("document_id")) for hit in hits
            ),
        }
        reciprocal_ranks.append(1.0 / relevant_rank if relevant_rank else 0.0)
        results.append({
            "id": case["id"], "query": case["query"], "passed": all(checks.values()),
            "checks": checks, "hit_count": len(hits), "relevant_rank": relevant_rank,
            "top_hits": [{"id": hit.get("id"), "title": hit.get("title"), "source": hit.get("source"),
                          "category": hit.get("category"), "score": hit.get("score"),
                          "citation": hit.get("citation")} for hit in hits],
        })
    total = len(results)
    metrics = {
        "document_hit_rate": round(sum(r["checks"]["document_hits_gt_0"] for r in results) / total, 4),
        f"recall_at_{top_k}": round(sum(r["checks"]["relevant_hit_at_k"] for r in results) / total, 4),
        "mrr": round(sum(reciprocal_ranks) / total, 4),
        "category_match_rate": round(sum(r["checks"]["category_match"] for r in results) / total, 4),
        "source_match_rate": round(sum(r["checks"]["source_match"] for r in results) / total, 4),
        "citation_locatable_rate": round(sum(r["checks"]["citations_locatable"] for r in results) / total, 4),
        "case_pass_rate": round(sum(r["passed"] for r in results) / total, 4),
    }
    thresholds = {
        "document_hit_rate": 1.0, f"recall_at_{top_k}": 0.90, "mrr": 0.75,
        "category_match_rate": 0.90, "source_match_rate": 0.95,
        "citation_locatable_rate": 1.0, "case_pass_rate": 0.85,
    }
    gates = {name: metrics[name] >= value for name, value in thresholds.items()}
    report = {"passed": all(gates.values()), "total_cases": total, "top_k": top_k,
              "metrics": metrics, "thresholds": thresholds, "gates": gates, "results": results}
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 任务 3：RAG 正式评测报告", "", f"- 总用例：{total}",
             f"- 总体通过：{'是' if report['passed'] else '否'}", "", "| 指标 | 实际值 | 门槛 | 通过 |",
             "|---|---:|---:|:---:|"]
    for name, threshold in thresholds.items():
        lines.append(f"| {name} | {metrics[name]:.4f} | {threshold:.4f} | {'是' if gates[name] else '否'} |")
    lines.extend(["", "## 未通过用例", ""])
    failed = [item for item in results if not item["passed"]]
    lines.extend([f"- `{item['id']}`：{item['query']}（{item['checks']}）" for item in failed] or ["- 无"])
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    result = evaluate()
    print(json.dumps({"passed": result["passed"], "total_cases": result["total_cases"],
                      "metrics": result["metrics"], "gates": result["gates"]},
                     ensure_ascii=False, indent=2))
