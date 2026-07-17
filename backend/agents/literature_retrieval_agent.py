from backend.tools.rag_tool import RAGRetrievalTool


class LiteratureRetrievalAgent:
    """Retrieve traceable text and graph evidence from the unified RAG service."""

    def __init__(self, rag_tool: RAGRetrievalTool | None = None) -> None:
        self.rag_tool = rag_tool or RAGRetrievalTool()

    def run(self, case_text: str, graph_result: dict) -> dict:
        print("[LiteratureRetrievalAgent] start")
        rag_result = self.rag_tool.query(
            query=case_text,
            syndromes=graph_result.get("syndromes", []),
            formulas=graph_result.get("formulas", []),
            generate_answer=False,
        )
        result = {
            "evidence": rag_result.get("evidence", []),
            "graph": rag_result.get("graph", {"nodes": [], "edges": []}),
            "answer": rag_result.get("answer", ""),
            "mode": rag_result.get("mode", "local-graphrag"),
            "retrieval": rag_result.get("retrieval", {}),
            "clinical_dimensions": rag_result.get("clinical_dimensions", {}),
            "differential_evidence": rag_result.get("differential_evidence", []),
        }
        print("[LiteratureRetrievalAgent] completed")
        return result
