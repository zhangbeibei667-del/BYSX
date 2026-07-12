from backend.tools.rag_tool import RAGRetrievalTool


class LiteratureRetrievalAgent:
    """Retrieve supporting teaching snippets from mock RAG data."""

    def __init__(self, rag_tool: RAGRetrievalTool | None = None) -> None:
        self.rag_tool = rag_tool or RAGRetrievalTool()

    def run(self, case_text: str, graph_result: dict) -> dict:
        print("[LiteratureRetrievalAgent] start")
        rag_result = self.rag_tool.query(
            query=case_text,
            syndromes=graph_result.get("syndromes", []),
            formulas=graph_result.get("formulas", []),
        )
        result = {
            "evidence": rag_result.get("evidence", []),
            "graph": rag_result.get("graph", {"nodes": [], "edges": []}),
            "answer": rag_result.get("answer", ""),
            "mode": rag_result.get("mode", "local-graphrag"),
        }
        print("[LiteratureRetrievalAgent] completed")
        return result
