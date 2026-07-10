from backend.mock_data.tcm_mock_data import LITERATURE_SNIPPETS
from backend.services.local_graphrag_service import get_local_graphrag_service


class RAGRetrievalTool:
    """RAG retrieval tool used by the teaching agent.

    It prefers the local GraphRAG adapter backed by the full entities_relations
    graph.  The original mock snippets remain as a safe fallback so the app can
    still run if local graph data is missing.
    """

    def query(
        self,
        query: str,
        syndromes: list[str] | None = None,
        formulas: list[str] | None = None,
        top_k: int = 5,
    ) -> dict:
        try:
            return get_local_graphrag_service().search(
                query=query,
                syndromes=syndromes or [],
                formulas=formulas or [],
                top_k=top_k,
            )
        except Exception as exc:
            return {
                "query": query,
                "mode": "mock-fallback",
                "error": str(exc),
                "graph": {"nodes": [], "edges": []},
                "evidence": self._mock_retrieve(
                    syndromes=syndromes or [],
                    formulas=formulas or [],
                    top_k=top_k,
                ),
                "answer": "本地 GraphRAG 暂不可用，已回退到 mock 文献片段。",
                "syndromes": syndromes or [],
                "formulas": formulas or [],
                "herbs": [],
            }

    def retrieve(
        self,
        case_text: str,
        syndromes: list[str],
        formulas: list[str],
        top_k: int = 5,
    ) -> list[dict]:
        result = self.query(
            query=" ".join([case_text, *syndromes, *formulas]).strip(),
            syndromes=syndromes,
            formulas=formulas,
            top_k=top_k,
        )
        evidence = result.get("evidence", [])
        if evidence:
            return evidence[:top_k]
        return self._mock_retrieve(syndromes=syndromes, formulas=formulas, top_k=top_k)

    def _mock_retrieve(
        self,
        syndromes: list[str],
        formulas: list[str],
        top_k: int = 5,
    ) -> list[dict]:
        evidence = []
        for formula in formulas:
            evidence.extend(LITERATURE_SNIPPETS.get(formula, []))

        if not evidence and syndromes:
            evidence.append(
                {
                    "title": f"{syndromes[0]}证候说明",
                    "source": "中医基础 mock 资料",
                    "content": f"本片段用于辅助学习 {syndromes[0]} 与症状、方剂之间的关系。",
                }
            )

        if not evidence:
            evidence.append(
                {
                    "title": "四诊信息补全说明",
                    "source": "中医问诊 mock 资料",
                    "content": (
                        "当主诉较宽泛时，应先明确部位、性质、诱因、持续时间、"
                        "兼症以及舌脉信息，不宜直接关联具体证候和方剂。"
                    ),
                }
            )

        return evidence[:top_k]
