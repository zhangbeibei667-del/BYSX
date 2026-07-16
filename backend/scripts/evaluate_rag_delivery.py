from __future__ import annotations

import json
from pathlib import Path

from backend.services.rag_service import RAGService
from backend.services.rag_runtime_service import ROOT


CASES = ROOT / "evaluation" / "rag_delivery_eval.jsonl"
REPORT = ROOT / "docs" / "任务3_RAG评测报告.json"


def evaluate() -> dict:
    service = RAGService()
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    results = []
    for case in cases:
        answer = service.search(case["query"], top_k=5)
        checks = {
            "intent": not case.get("expected_intent") or answer.get("intent") == case["expected_intent"],
            "graph": not case.get("require_graph") or bool(answer.get("graph", {}).get("edges")),
            "reasoning_paths": not case.get("require_graph") or bool(answer.get("reasoning_paths")),
            "evidence": not case.get("require_evidence") or bool(answer.get("evidence")),
            "citations": (not answer.get("evidence")) or bool(answer.get("citations")),
            "insufficient": not case.get("expect_insufficient") or answer.get("mode") == "evidence-insufficient",
            "no_mock": "mock" not in json.dumps(answer, ensure_ascii=False).lower(),
        }
        results.append({"id": case["id"], "query": case["query"], "passed": all(checks.values()),
                        "checks": checks, "intent": answer.get("intent"), "mode": answer.get("mode"),
                        "evidence": len(answer.get("evidence", [])),
                        "edges": len(answer.get("graph", {}).get("edges", []))})
    passed = sum(item["passed"] for item in results)
    report = {"passed": passed == len(results), "total": len(results), "passed_cases": passed,
              "pass_rate": round(passed / max(1, len(results)), 4), "results": results}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
