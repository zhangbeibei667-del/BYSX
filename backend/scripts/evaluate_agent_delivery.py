from __future__ import annotations

import json
import re
import uuid

from backend.services.agent_service import AgentService
from backend.services.conversation_service import ConversationService
from backend.services.local_graphrag_service import get_local_graphrag_service
from backend.services.rag_runtime_service import ROOT


CASES = ROOT / "evaluation" / "agent_delivery_eval.jsonl"
REPORT = ROOT / "docs" / "任务4_Agent端到端评测报告.json"


def _safe_sql(result: dict) -> bool:
    sql = str(result.get("sql_result", {}).get("text_to_sql", {}).get("generated_sql") or "").strip()
    if not sql:
        return True
    return bool(re.match(r"^(SELECT|WITH)\b", sql, re.I)) and not re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH|PRAGMA)\b", sql, re.I)


def evaluate() -> dict:
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    formal_names = {entity.name for entity in get_local_graphrag_service().entities}
    service = AgentService()
    conversations = ConversationService()
    rows = []
    totals = {"intent": 0, "entity_hit": 0, "entity_total": 0, "tool_hit": 0, "tool_expected": 0,
              "tool_selected": 0, "hallucinated": 0, "claims": 0, "followup": 0, "followup_total": 0,
              "safety": 0, "sql": 0}
    for case in cases:
        session_id = f"agent-eval-{uuid.uuid4().hex}"
        result = service.chat(case["input"], session_id)
        conversations.delete(session_id)
        service.history_service.delete_history(result["history_id"])
        selected = set(result.get("agent_plan", {}).get("tools", []))
        expected_tools = set(case.get("expected_tools", []))
        visible = json.dumps(result, ensure_ascii=False)
        entity_hits = sum(name in visible for name in case.get("expected_entities", []))
        claims = [*result.get("syndromes", []), *result.get("formulas", []), *result.get("herbs", [])]
        hallucinated = [name for name in claims if name not in formal_names]
        forbidden = [name for name in case.get("forbidden_entities", [])
                     if name in [*result.get("syndromes", []), *result.get("formulas", []), *result.get("herbs", [])]]
        followup_keywords = case.get("followup_keywords", [])
        followup_text = " ".join(result.get("follow_up_questions", []))
        followup_ok = not followup_keywords or all(word in followup_text for word in followup_keywords)
        checks = {
            "intent": result.get("agent_plan", {}).get("intent") == case["expected_intent"],
            "entities": entity_hits == len(case.get("expected_entities", [])),
            "tools": expected_tools.issubset(selected),
            "grounded_claims": not hallucinated and not forbidden,
            "followup": followup_ok,
            "safety": bool(result.get("safety_notice")) and "不构成" in result.get("safety_notice", ""),
            "sql_read_only": _safe_sql(result),
            "trace": bool(result.get("agent_steps")) and bool(result.get("agent_plan")),
        }
        totals["intent"] += checks["intent"]
        totals["entity_hit"] += entity_hits; totals["entity_total"] += len(case.get("expected_entities", []))
        totals["tool_hit"] += len(selected & expected_tools); totals["tool_expected"] += len(expected_tools)
        totals["tool_selected"] += len(selected); totals["hallucinated"] += len(hallucinated) + len(forbidden)
        totals["claims"] += len(claims); totals["followup"] += followup_ok; totals["followup_total"] += 1
        totals["safety"] += checks["safety"]; totals["sql"] += checks["sql_read_only"]
        rows.append({"id": case["id"], "passed": all(checks.values()), "checks": checks,
                     "intent": result.get("agent_plan", {}).get("intent"), "tools": sorted(selected),
                     "entities": {"syndromes": result.get("syndromes", []), "formulas": result.get("formulas", []),
                                  "herbs": result.get("herbs", [])}, "followups": result.get("follow_up_questions", [])})
    # Dedicated multi-turn effectiveness check.
    multi_id = f"agent-eval-multi-{uuid.uuid4().hex}"
    first = service.chat("患者失眠多梦，伴心悸", multi_id)
    second = service.chat("舌淡，脉细，还伴食少乏力", multi_id)
    service.history_service.delete_history(first["history_id"])
    service.history_service.delete_history(second["history_id"])
    restored = conversations.load(multi_id); conversations.delete(multi_id)
    multi_turn = all(item in restored.get("collected", {}).get("symptoms", []) for item in ["失眠", "多梦", "心悸", "食少乏力"]) \
        and "舌淡" in restored.get("collected", {}).get("tongue", []) and "脉细" in restored.get("collected", {}).get("pulse", []) \
        and len(restored.get("turns", [])) == 4
    n = len(cases)
    metrics = {
        "intent_accuracy": round(totals["intent"] / n, 4),
        "entity_recall": round(totals["entity_hit"] / max(1, totals["entity_total"]), 4),
        "tool_recall": round(totals["tool_hit"] / max(1, totals["tool_expected"]), 4),
        "tool_precision": round(totals["tool_hit"] / max(1, totals["tool_selected"]), 4),
        "hallucination_rate": round(totals["hallucinated"] / max(1, totals["claims"]), 4),
        "followup_effectiveness": round(totals["followup"] / totals["followup_total"], 4),
        "safety_compliance": round(totals["safety"] / n, 4),
        "sql_read_only_rate": round(totals["sql"] / n, 4),
        "multi_turn_retention": 1.0 if multi_turn else 0.0,
    }
    passed = all(row["passed"] for row in rows) and multi_turn
    report = {"passed": passed, "cases": n, "passed_cases": sum(row["passed"] for row in rows),
              "metrics": metrics, "multi_turn": {"passed": multi_turn,
              "first_status": first.get("conversation", {}).get("status"),
              "second_status": second.get("conversation", {}).get("status")}, "results": rows}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    report = evaluate()
    print(json.dumps({key: report[key] for key in ("passed", "cases", "passed_cases", "metrics", "multi_turn")},
                     ensure_ascii=False, indent=2))
