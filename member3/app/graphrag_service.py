"""Deprecated member3 service facade.

All online retrieval delegates to backend.services.rag_service.RAGService.  The
constructor remains compatible with older member3 scripts so they can migrate
without keeping a second answer-generation implementation.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.rag_service import RAGService
from member3.app.community_search import LightweightCommunitySearch
from member3.app.schemas import EvidenceItem, GraphData, GraphEdge, GraphNode, QAResult


class GraphRAGService:
    def __init__(self, vector_search=None, graph_search=None, llm_client=None) -> None:
        self.vector_search = vector_search
        self.graph_search = graph_search
        self.llm_client = llm_client
        self.community_search = LightweightCommunitySearch(graph_search) if graph_search else None
        self.primary = RAGService()

    def query(self, request) -> QAResult:
        result = self.primary.search(query=request.query, top_k=request.top_k)
        graph = result.get("graph", {})
        return QAResult(
            answer=result.get("answer", ""),
            symptoms=result.get("symptoms", []), syndromes=result.get("syndromes", []),
            formulas=result.get("formulas", []), herbs=result.get("herbs", []),
            graph=GraphData(
                nodes=[GraphNode(id=item["id"], label=item["label"], type=item["type"])
                       for item in graph.get("nodes", [])],
                edges=[GraphEdge(source=item["source"], target=item["target"], label=item["label"])
                       for item in graph.get("edges", [])],
            ),
            evidence=[EvidenceItem(title=item.get("citation") or item.get("title", ""),
                                   content=item.get("content", ""))
                      for item in result.get("evidence", [])],
            follow_up_questions=result.get("follow_up_questions", []),
            safety_notice=result.get("safety_notice", "本结果仅用于知识学习，不替代医师诊断处方。"),
        )
