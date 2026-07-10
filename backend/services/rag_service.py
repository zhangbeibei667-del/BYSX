from backend.tools.rag_tool import RAGRetrievalTool


class RAGService:
    """RAG search service backed by the local GraphRAG adapter."""

    def __init__(self, rag_tool: RAGRetrievalTool | None = None) -> None:
        self.rag_tool = rag_tool or RAGRetrievalTool()

    def search(
        self,
        query: str,
        case_text: str = "",
        syndromes: list[str] | None = None,
        formulas: list[str] | None = None,
        top_k: int = 5,
    ) -> dict:
        result = self.rag_tool.query(
            query=" ".join([query, case_text, *(syndromes or []), *(formulas or [])]).strip(),
            syndromes=syndromes or [],
            formulas=formulas or [],
            top_k=top_k,
        )
        result["query"] = query
        result["top_k"] = top_k
        return result
