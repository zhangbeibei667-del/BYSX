from backend.tools.graph_tool import GraphQueryTool


class GraphReasoningAgent:
    """Query the graph tool and return syndrome, formula, herbs and graph paths."""

    def __init__(self, graph_tool: GraphQueryTool | None = None) -> None:
        self.graph_tool = graph_tool or GraphQueryTool()

    def run(self, symptom_result: dict) -> dict:
        print("[GraphReasoningAgent] start")
        symptoms = symptom_result.get("symptoms", [])
        result = self.graph_tool.query_by_symptoms(symptoms)
        print("[GraphReasoningAgent] completed")
        return result
