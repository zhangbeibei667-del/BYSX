from backend.services.local_graphrag_service import get_local_graphrag_service


class GraphQueryTool:
    """Evidence-gated symptom graph query using only the formal local KG."""

    def query_by_symptoms(self, symptoms: list[str]) -> dict:
        try:
            result = get_local_graphrag_service().query_by_symptoms(symptoms)
        except Exception as exc:
            return self._insufficient(symptoms, f"图谱查询失败：{exc}")
        if result.get("syndromes") or result.get("formulas"):
            result["evidence_status"] = "verified-graph"
            result["confidence"] = result.get("confidence") or "local-kg-match"
            return result
        return {**self._insufficient(symptoms, result.get("reason") or "未形成可验证关系路径"),
                "graph": result.get("graph", {"nodes": [], "edges": []})}

    @staticmethod
    def _insufficient(symptoms: list[str], reason: str) -> dict:
        return {
            "syndromes": [], "formulas": [], "herbs": [],
            "graph": {"nodes": [{"id": f"input:{index}", "label": symptom, "type": "症状"}
                                for index, symptom in enumerate(symptoms, 1)], "edges": []},
            "reasoning_paths": ["证据不足，未建立证候与方剂推理路径"],
            "reason": reason, "evidence_status": "insufficient", "confidence": 0,
            "needs_clarification": True,
        }
