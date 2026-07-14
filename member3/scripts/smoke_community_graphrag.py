from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.graph_search import GraphSearch
from app.graphrag_service import GraphRAGService
from app.schemas import GraphRAGQueryRequest


class EmptyRetriever:
    def search(
        self,
        query: str,
        top_k: int = 3,
    ):
        return []


def main() -> None:
    graph_search = GraphSearch(
        PROJECT_ROOT / "data" / "entities.json",
        PROJECT_ROOT / "data" / "relations.json",
    )
    service = GraphRAGService(
        vector_search=EmptyRetriever(),
        graph_search=graph_search,
        llm_client=None,
    )
    result = service.query(
        GraphRAGQueryRequest(
            query="这个图谱的知识结构做一个概览",
            top_k=3,
        )
    )

    print(result.answer)
    print("evidence:")

    for item in result.evidence:
        print("-", item.title)


if __name__ == "__main__":
    main()
