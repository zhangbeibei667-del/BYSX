from backend.tools.graph_tool import GraphQueryTool
from backend.services.local_graphrag_service import get_local_graphrag_service


class GraphReasoningAgent:
    """Query the graph tool and return syndrome, formula, herbs and graph paths."""

    def __init__(self, graph_tool: GraphQueryTool | None = None) -> None:
        self.graph_tool = graph_tool or GraphQueryTool()

    def run(self, symptom_result: dict, query: str = "") -> dict:
        print("[GraphReasoningAgent] start")
        symptoms = symptom_result.get("symptoms", [])
        if symptoms:
            result = self.graph_tool.query_by_symptoms(symptoms)
        else:
            searched = get_local_graphrag_service().search(query=query, top_k=5)
            result = {
                "syndromes": searched.get("syndromes", []),
                "formulas": searched.get("formulas", []),
                "herbs": searched.get("herbs", []),
                "graph": searched.get("graph", {"nodes": [], "edges": []}),
                "reasoning_paths": searched.get("reasoning_paths", []),
                "evidence_status": "verified-graph" if searched.get("graph", {}).get("edges") else "insufficient",
                "needs_clarification": False,
            }
        print("[GraphReasoningAgent] completed")
        return result
