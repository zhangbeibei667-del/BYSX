from __future__ import annotations

import re

from backend.services.local_graphrag_service import get_local_graphrag_service
from backend.services.vector_retrieval_service import VectorRetrievalService
from backend.services.llm_client import get_llm_client


class RAGRetrievalTool:
    """Hybrid Qdrant + graph retrieval with evidence-bounded answers."""

    RELATION_INTENTS = {"formula_composition", "symptom_to_formula", "effect_query", "contraindication_query"}

    def query(self, query: str, syndromes: list[str] | None = None,
              formulas: list[str] | None = None, top_k: int = 5) -> dict:
        graph_service = get_local_graphrag_service()
        unknown = self._unknown_claim_subject(query, graph_service)
        if unknown:
            return self._insufficient(query, f"“{unknown}”不在当前知识图谱实体中，无法验证该治疗关系")
        try:
            result = graph_service.search(query=query, syndromes=syndromes or [], formulas=formulas or [], top_k=top_k)
            document_evidence = VectorRetrievalService().search(query, top_k=top_k)
            graph_evidence = result.get("evidence", [])
            has_relation = bool(result.get("graph", {}).get("edges"))
            if result.get("intent") in self.RELATION_INTENTS and not has_relation:
                insufficient = self._insufficient(query, "检索到的实体之间没有带来源依据的目标关系")
                insufficient["evidence"] = document_evidence[:top_k]
                insufficient["citations"] = [item["citation"] for item in document_evidence[:top_k]]
                return insufficient
            result["evidence"] = (document_evidence + graph_evidence)[:top_k]
            document_mode = (document_evidence[0].get("retrieval_mode")
                             if document_evidence else "no-document-hit")
            result["retrieval"] = {"mode": f"{document_mode}+graph", "document_hits": len(document_evidence),
                                   "graph_hits": len(graph_evidence), "citations_available": bool(result["evidence"])}
            result["citations"] = [item.get("citation") or f"《{item.get('title', '未命名资料')}》"
                                   for item in result["evidence"]]
            if result["citations"]:
                result["answer"] = result.get("answer", "").rstrip() + "\n\n参考依据：" + "；".join(
                    f"[{index}] {citation}" for index, citation in enumerate(result["citations"], 1))
            elif not has_relation:
                return self._insufficient(query, "没有召回可验证关系或可定位资料")
            result["evidence_confidence"] = "high" if has_relation and document_evidence else "medium"
            scores = [float(item.get("score", 0.75 if item.get("source") == "知识图谱" else 0.0))
                      for item in result["evidence"]]
            result["evidence_confidence_score"] = round(sum(scores) / max(1, len(scores)), 4)
            generated = self._generate_answer(query, result)
            if generated:
                result["answer"] = generated["content"]
                result["generation"] = {"mode": "llm-grounded", "provider": generated["provider"],
                                        "model": generated["model"], "usage": generated["usage"]}
            else:
                result["generation"] = {"mode": "local-evidence-template"}
            return result
        except Exception as exc:
            return {**self._insufficient(query, "检索服务暂时不可用"), "error": str(exc), "mode": "retrieval-error"}

    def retrieve(self, case_text: str, syndromes: list[str], formulas: list[str], top_k: int = 5) -> list[dict]:
        return self.query(" ".join([case_text, *syndromes, *formulas]).strip(), syndromes, formulas, top_k).get("evidence", [])[:top_k]

    @staticmethod
    def _unknown_claim_subject(query: str, graph_service) -> str:
        match = re.search(r"([\u4e00-\u9fff]{2,16})(?:能|可以|是否)(?:治疗|主治|用于)", query)
        if not match:
            return ""
        subject = match.group(1).lstrip("请问关于想知道")
        known = any(subject == entity.name or subject == entity.alias for entity in graph_service.entities)
        return "" if known else subject

    @staticmethod
    def _insufficient(query: str, reason: str) -> dict:
        return {"query": query, "mode": "evidence-insufficient", "answer": f"证据不足：{reason}，当前不能给出可靠结论。",
                "graph": {"nodes": [], "edges": []}, "evidence": [], "citations": [], "syndromes": [],
                "formulas": [], "herbs": [], "evidence_confidence": "insufficient",
                "retrieval": {"mode": "evidence-gated", "document_hits": 0, "graph_hits": 0,
                              "citations_available": False}}

    @staticmethod
    def _generate_answer(query: str, result: dict) -> dict | None:
        client = get_llm_client()
        if not client.available:
            return None
        evidence_lines = []
        for index, item in enumerate(result.get("evidence", [])[:5], 1):
            evidence_lines.append(
                f"[{index}] 来源：{item.get('citation') or item.get('title')}\n"
                f"内容：{str(item.get('content', ''))[:900]}"
            )
        graph_lines = [
            f"{edge.get('source_name', '')} --{edge.get('label', '')}--> {edge.get('target_name', '')}；依据：{edge.get('evidence', '')}"
            for edge in result.get("graph", {}).get("edges", [])[:12]
        ]
        messages = [
            {"role": "system", "content": (
                "你是面向中医药知识学习和辨证辅助的智能问答助手。回答应自然、亲切、简洁，避免报告式罗列。"
                "只能使用给定图谱关系和资料片段，不得补造方剂、功效或适应证。每个关键结论在句末标注对应[编号]；"
                "若证据支持不同证候，应解释需要哪些舌脉或兼症才能区分，不能直接给患者开方。"
                "最后用一句话提示结果用于知识学习，不替代医师诊断处方。不要重复输出完整参考文献列表。")},
            {"role": "user", "content": f"问题：{query}\n\n图谱关系：\n" + "\n".join(graph_lines)
             + "\n\n资料片段：\n" + "\n\n".join(evidence_lines)},
        ]
        return client.complete(messages, temperature=0.25)
