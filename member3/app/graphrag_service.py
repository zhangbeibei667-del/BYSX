from __future__ import annotations

import re
from typing import Protocol

from app.community_search import (
    CommunitySummary,
    LightweightCommunitySearch,
)
from app.graph_search import GraphSearch
from app.hkcmms_cleaning import (
    clean_hkcmms_item_text,
    simplify_hkcmms_display_text,
)
from app.llm_client import LLMClient
from app.schemas import (
    EvidenceItem,
    GraphData,
    GraphRAGQueryRequest,
    QAResult,
)
from app.vector_search import RetrievedChunk


TYPE_TO_FIELD = {
    "症状": "symptoms",
    "证候": "syndromes",
    "方剂": "formulas",
    "药材": "herbs",
}


INTENT_LABELS = {
    "formula_composition": "方剂组成查询",
    "syndrome_manifestation": "证候症状表现查询",
    "symptom_to_formula": "症状到方剂查询",
    "mechanism_explanation": "配伍/机制解释查询",
    "effect_query": "功效作用查询",
    "contraindication_query": "禁忌注意查询",
    "definition_query": "概念定义查询",
    "global_summary": "图谱全局概览查询",
    "general": "一般知识查询",
}


class TextRetriever(Protocol):
    """GraphRAGService 所需的最小文本检索接口。"""

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[RetrievedChunk]:
        ...


class GraphRAGService:
    """
    TCM GraphRAG 核心服务。

    本版重点增加：
    1. Query Intent Detection；
    2. Intent-aware RAG Evidence Selection；
    3. Intent-aware Graph Path Pruning；
    4. Intent-aware Structured Field Filtering；
    5. Answer Prefix Cleaning；
    6. 更自然的 Fallback Answer。

    目标：
    - 让文本证据和图谱证据按问题意图分层使用；
    - 避免无关图谱支路、弱相关文档片段进入 Prompt；
    - 降低 LLM 幻觉和结构化字段污染；
    - 保持 FastAPI / 前端 / 成员 4 调用接口不变。
    """

    def __init__(
        self,
        vector_search: TextRetriever,
        graph_search: GraphSearch,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.vector_search = vector_search
        self.graph_search = graph_search
        self.llm_client = llm_client
        self.community_search = LightweightCommunitySearch(
            graph_search
        )

    # ========================================================
    # 1. Query Intent + Hint
    # ========================================================
    @staticmethod
    def _detect_intent(
        query: str,
    ) -> str:
        """识别用户问题意图，用于后续证据分层和字段过滤。"""
        text = query.strip().lower()

        if any(
            keyword in text
            for keyword in [
                "包含哪些药材",
                "含有哪些药材",
                "由哪些药材组成",
                "有哪些药材组成",
                "组成是什么",
                "方中有哪些",
                "药物组成",
                "方剂组成",
                "组成药材",
                "包含什么药材",
            ]
        ):
            return "formula_composition"

        if any(
            keyword in text
            for keyword in [
                "有哪些症状",
                "有什么症状",
                "典型症状",
                "主要症状",
                "有哪些表现",
                "典型表现",
                "主要表现",
                "临床表现",
                "体征",
            ]
        ):
            return "syndrome_manifestation"

        if (
            any(
                keyword in text
                for keyword in [
                    "有什么方剂",
                    "哪些方剂",
                    "关联哪些方剂",
                    "相关方剂",
                    "用什么方剂",
                    "推荐什么方剂",
                    "对应什么方剂",
                    "可用什么方剂",
                    "哪些证候和方剂",
                ]
            )
            and any(
                keyword in text
                for keyword in [
                    "关联",
                    "相关",
                    "治疗",
                    "用于",
                    "失眠",
                    "咳嗽",
                    "心悸",
                    "头痛",
                    "鼻衄",
                ]
            )
        ):
            return "symptom_to_formula"

        if any(
            keyword in text
            for keyword in [
                "为什么",
                "为何",
                "原因",
                "机制",
                "机理",
                "原理",
                "反佐",
                "配伍",
                "佐制",
                "相须",
                "相使",
                "相畏",
                "相杀",
            ]
        ):
            return "mechanism_explanation"

        if any(
            keyword in text
            for keyword in [
                "有什么功效",
                "有哪些功效",
                "什么功效",
                "有什么作用",
                "有哪些作用",
                "主治什么",
                "功效是什么",
            ]
        ):
            return "effect_query"

        if any(
            keyword in text
            for keyword in [
                "禁忌",
                "慎用",
                "不宜",
                "注意事项",
                "不能用",
            ]
        ):
            return "contraindication_query"

        if any(
            keyword in text
            for keyword in [
                "整体概览",
                "总体概览",
                "知识结构",
                "图谱结构",
                "社区摘要",
                "社区发现",
                "全局检索",
                "全局总结",
                "宏观",
                "总结一下",
                "概览",
                "总览",
                "学习路线",
                "有哪些模块",
                "有哪些主题",
            ]
        ):
            return "global_summary"

        if any(
            keyword in text
            for keyword in [
                "是什么",
                "定义",
                "解释一下",
                "介绍一下",
                "概念",
            ]
        ):
            return "definition_query"

        return "general"

    @staticmethod
    def _extract_query_hint(
        query: str,
    ) -> str:
        """从常见问句中提取较稳定的目标词面。"""
        text = query.strip().lower()

        prefixes = [
            "请问",
            "我想知道",
            "想了解",
            "请介绍一下",
            "介绍一下",
            "请说明",
        ]

        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        suffixes = [
            "包含哪些药材？",
            "包含哪些药材",
            "含有哪些药材？",
            "含有哪些药材",
            "由哪些药材组成？",
            "由哪些药材组成",
            "有哪些药材组成？",
            "有哪些药材组成",
            "组成是什么？",
            "组成是什么",
            "药物组成是什么？",
            "药物组成是什么",
            "有哪些典型症状表现？",
            "有哪些典型症状表现",
            "有哪些典型表现？",
            "有哪些典型表现",
            "有哪些症状？",
            "有哪些症状",
            "有什么症状？",
            "有什么症状",
            "主要症状是什么？",
            "主要症状是什么",
            "有什么方剂？",
            "有什么方剂",
            "有哪些方剂？",
            "有哪些方剂",
            "有什么功效？",
            "有什么功效",
            "有哪些功效？",
            "有哪些功效",
            "有什么作用？",
            "有什么作用",
            "有哪些作用？",
            "有哪些作用",
            "是什么？",
            "是什么",
            "为什么？",
            "为什么",
        ]

        for suffix in suffixes:
            if text.endswith(suffix):
                text = text[:-len(suffix)].strip()
                break

        if text.startswith("治疗"):
            text = text[len("治疗"):].strip()

        return text

    def _extract_query_entities(
        self,
        query: str,
    ) -> list[str]:
        """提取 Query 中出现的图谱实体名称和别名。"""
        query_text = query.strip().lower()
        result: list[str] = []

        for entity in self.graph_search.entities:
            for name in [entity.name, entity.alias]:
                if (
                    name
                    and name.strip()
                    and name.lower() in query_text
                    and name not in result
                ):
                    result.append(name)

        # 补充常见方剂名词面，如“吴茱萸汤”可能尚未进入图谱实体。
        for match in re.finditer(
            r"[\u4e00-\u9fff]{2,12}(?:汤|丸|散|方|丹)",
            query,
        ):
            value = match.group(0)
            if value not in result:
                result.append(value)

        return result

    # ========================================================
    # 2. Query-aware Evidence Selection
    # ========================================================
    @staticmethod
    def _chunk_text(
        chunk: RetrievedChunk,
    ) -> str:
        return f"{chunk.title}\n{chunk.content}"

    def _select_mechanism_chunks(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """机制/配伍类问题优先保留真正解释机制的文本证据。"""
        if not chunks:
            return []

        query_terms = self._extract_query_entities(query)

        for keyword in [
            "反佐",
            "配伍",
            "格拒",
            "同气相求",
            "反从其病",
            "辛热太过",
            "佐制",
        ]:
            if keyword in query and keyword not in query_terms:
                query_terms.append(keyword)

        scored: list[tuple[float, RetrievedChunk]] = []

        for chunk in chunks:
            text = self._chunk_text(chunk)
            score = 0.0

            for term in query_terms:
                if term and term in text:
                    score += 2.0

            if "反佐" in text:
                score += 4.0

            if "格拒" in text:
                score += 2.0

            if "同气相求" in text:
                score += 2.0

            if "辛热太过" in text:
                score += 2.0

            # 保留原始检索分作为弱排序依据。
            score += float(getattr(chunk, "score", 0.0)) * 0.01

            if score >= 3.0:
                scored.append((score, chunk))

        scored.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            item[1]
            for item in scored[:top_k]
        ]

    def _select_relevant_chunks(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        intent: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """按问题意图筛选最终进入 Prompt / Evidence 的文本片段。"""
        if not chunks:
            return []

        hint = self._extract_query_hint(query)
        query_entities = self._extract_query_entities(query)
        query_terms = [
            term
            for term in [hint, *query_entities]
            if term and len(term) >= 2
        ]

        # ----------------------------------------------------
        # 方剂组成：文本证据必须同时命中目标方剂和“直接组成”语义。
        # 避免“某证候方用某方”这类弱相关文本进入 evidence。
        # 若没有直接组成证据，允许 evidence 为空，交给图谱主证据。
        # ----------------------------------------------------
        if intent == "formula_composition":
            direct_composition_patterns = [
                r"药物组成\s*[:：]",
                r"组成\s*[:：]",
                r"处方组成\s*[:：]",
                r"方药组成\s*[:：]",
                r"本方由[^。；\n]{0,80}组成",
                r"由[^。；\n]{0,80}组成",
                r"(?:含有|包含)[^。；\n]{0,30}(?:药材|药味|药物)",
                r"(?:药材|药味|药物)[^。；\n]{0,30}(?:包括|包含|有)",
                r"方中[^。；\n]{0,80}(?:药|味)",
            ]

            selected: list[RetrievedChunk] = []

            for chunk in chunks:
                text = self._chunk_text(chunk)

                has_target = any(
                    term in text
                    for term in query_terms
                )

                has_direct_composition = any(
                    re.search(pattern, text)
                    for pattern in direct_composition_patterns
                )

                if has_target and has_direct_composition:
                    selected.append(chunk)

            return selected[:top_k]

        # ----------------------------------------------------
        # 机制解释：去掉只靠泛化语义召回的弱相关文档。
        # ----------------------------------------------------
        if intent == "mechanism_explanation":
            return self._select_mechanism_chunks(
                query=query,
                chunks=chunks,
                top_k=top_k,
            )

        # ----------------------------------------------------
        # 证候表现：优先保留标题或正文精确命中的 TCM-SD 结构化片段。
        # ----------------------------------------------------
        if intent == "syndrome_manifestation":
            title_matches = [
                chunk
                for chunk in chunks
                if any(
                    term in chunk.title
                    for term in query_terms
                )
            ]

            if title_matches:
                return title_matches[:top_k]

            content_matches = [
                chunk
                for chunk in chunks
                if any(
                    term in chunk.content
                    for term in query_terms
                )
            ]

            if content_matches:
                return content_matches[:top_k]

            return chunks[:top_k]

        # ----------------------------------------------------
        # 症状找方剂：文本证据只作为备用补充。
        # 最终若图谱路径可用，会在 query() 中以图谱为主并压制文本证据，
        # 避免把养生文章、经验方或图谱外方剂扩展到主答案。
        # ----------------------------------------------------
        if intent == "symptom_to_formula":
            selected = [
                chunk
                for chunk in chunks
                if any(
                    term in self._chunk_text(chunk)
                    for term in query_terms
                )
            ]

            if selected:
                return selected[:top_k]

            return chunks[:top_k]

        # ----------------------------------------------------
        # 其他意图：沿用“精确命中优先，否则保留原 Top-K”。
        # ----------------------------------------------------
        if query_terms:
            title_matches = [
                chunk
                for chunk in chunks
                if any(
                    term in chunk.title
                    for term in query_terms
                )
            ]

            if title_matches:
                return title_matches[:top_k]

            content_matches = [
                chunk
                for chunk in chunks
                if any(
                    term in chunk.content
                    for term in query_terms
                )
            ]

            if content_matches:
                return content_matches[:top_k]

        return chunks[:top_k]

    # ========================================================
    # 3. Intent-aware Graph Pruning
    # ========================================================
    @staticmethod
    def _get_graph_node(
        graph: GraphData,
        node_id: str,
    ):
        for node in graph.nodes:
            if node.id == node_id:
                return node

        return None

    @staticmethod
    def _build_subgraph_from_edges(
        graph: GraphData,
        edges: list,
    ) -> GraphData:
        used_node_ids: set[str] = set()

        for edge in edges:
            used_node_ids.add(edge.source)
            used_node_ids.add(edge.target)

        nodes = [
            node
            for node in graph.nodes
            if node.id in used_node_ids
        ]

        return GraphData(
            nodes=nodes,
            edges=edges,
        )

    def _prune_graph_by_intent(
        self,
        query: str,
        intent: str,
        graph: GraphData,
    ) -> GraphData:
        """根据问题意图裁剪图谱，避免无关关系污染答案。"""
        if not graph.edges:
            # 没有边时，避免只返回孤立种子节点造成“似乎有图谱证据”的误解。
            return GraphData()

        allowed_edges: list = []
        query_text = query.strip().lower()

        # ----------------------------------------------------
        # 方剂组成：只保留 方剂 --包含--> 药材。
        # ----------------------------------------------------
        if intent == "formula_composition":
            for edge in graph.edges:
                source_node = self._get_graph_node(
                    graph,
                    edge.source,
                )
                target_node = self._get_graph_node(
                    graph,
                    edge.target,
                )

                if not source_node or not target_node:
                    continue

                target_formula_matched = (
                    source_node.label.lower() in query_text
                )

                if (
                    target_formula_matched
                    and source_node.type == "方剂"
                    and target_node.type == "药材"
                    and edge.label == "包含"
                ):
                    allowed_edges.append(edge)

            return self._build_subgraph_from_edges(
                graph,
                allowed_edges,
            )

        # ----------------------------------------------------
        # 症状找方剂：只保留 症状 --提示--> 证候 --对应--> 方剂。
        # ----------------------------------------------------
        if intent == "symptom_to_formula":
            for edge in graph.edges:
                source_node = self._get_graph_node(
                    graph,
                    edge.source,
                )
                target_node = self._get_graph_node(
                    graph,
                    edge.target,
                )

                if not source_node or not target_node:
                    continue

                keep_symptom_to_syndrome = (
                    source_node.type == "症状"
                    and target_node.type == "证候"
                    and edge.label == "提示"
                )

                keep_syndrome_to_formula = (
                    source_node.type == "证候"
                    and target_node.type == "方剂"
                    and edge.label == "对应"
                )

                if keep_symptom_to_syndrome or keep_syndrome_to_formula:
                    allowed_edges.append(edge)

            return self._build_subgraph_from_edges(
                graph,
                allowed_edges,
            )

        # ----------------------------------------------------
        # 证候表现：只保留 证候 -> 症状/表现 的直接关系。
        # 当前团队图谱若没有该类边，graph 返回空是合理结果。
        # ----------------------------------------------------
        if intent == "syndrome_manifestation":
            for edge in graph.edges:
                source_node = self._get_graph_node(
                    graph,
                    edge.source,
                )
                target_node = self._get_graph_node(
                    graph,
                    edge.target,
                )

                if not source_node or not target_node:
                    continue

                if (
                    source_node.type == "证候"
                    and target_node.type == "症状"
                    and edge.label in {
                        "表现",
                        "症状",
                        "包含",
                        "提示",
                    }
                ):
                    allowed_edges.append(edge)

            return self._build_subgraph_from_edges(
                graph,
                allowed_edges,
            )

        # ----------------------------------------------------
        # 机制解释：没有直接机制/配伍关系时，不保留一般功效、禁忌、来源关系。
        # ----------------------------------------------------
        if intent == "mechanism_explanation":
            mechanism_keywords = [
                "反佐",
                "配伍",
                "制约",
                "佐制",
                "相须",
                "相使",
                "相畏",
                "相杀",
                "机制",
                "原因",
                "原理",
            ]

            for edge in graph.edges:
                label = edge.label or ""

                if any(
                    keyword in label
                    for keyword in mechanism_keywords
                ):
                    allowed_edges.append(edge)

            return self._build_subgraph_from_edges(
                graph,
                allowed_edges,
            )

        # ----------------------------------------------------
        # 功效查询：只保留实体 --具有--> 功效。
        # ----------------------------------------------------
        if intent == "effect_query":
            for edge in graph.edges:
                source_node = self._get_graph_node(
                    graph,
                    edge.source,
                )
                target_node = self._get_graph_node(
                    graph,
                    edge.target,
                )

                if not source_node or not target_node:
                    continue

                if (
                    target_node.type == "功效"
                    and edge.label == "具有"
                ):
                    allowed_edges.append(edge)

            return self._build_subgraph_from_edges(
                graph,
                allowed_edges,
            )

        # ----------------------------------------------------
        # 禁忌查询：只保留实体 --禁忌--> 禁忌。
        # ----------------------------------------------------
        if intent == "contraindication_query":
            for edge in graph.edges:
                target_node = self._get_graph_node(
                    graph,
                    edge.target,
                )

                if (
                    target_node
                    and target_node.type == "禁忌"
                    and edge.label == "禁忌"
                ):
                    allowed_edges.append(edge)

            return self._build_subgraph_from_edges(
                graph,
                allowed_edges,
            )

        return graph

    # ========================================================
    # 4. Structured Entity Helpers
    # ========================================================
    @staticmethod
    def _append_unique(
        target: list[str],
        value: str,
    ) -> None:
        value = value.strip()

        if value and value not in target:
            target.append(value)

    @staticmethod
    def _clean_phrase(
        value: str,
    ) -> str:
        """清理结构化字段中的轻量噪声。"""
        text = value.strip()
        text = text.replace("**", "")

        prefixes = [
            "兼有",
            "或见",
            "可见",
            "常见",
            "症见",
            "表现为",
            "主要表现为",
        ]

        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        text = text.strip(
            " \t\r\n，。；：:、！？!?"
        )

        return text

    @classmethod
    def _split_manifestations(
        cls,
        text: str,
    ) -> list[str]:
        """将“典型表现”字段拆成轻量症状短语。"""
        parts = re.split(
            r"[，、；;。\n]+",
            text,
        )

        result: list[str] = []

        for part in parts:
            phrase = cls._clean_phrase(part)

            if not phrase:
                continue

            if len(phrase) > 16:
                continue

            cls._append_unique(
                result,
                phrase,
            )

        return result

    @classmethod
    def _extract_structured_from_evidence(
        cls,
        query: str,
        answer: str,
        chunks: list[RetrievedChunk],
    ) -> dict[str, list[str]]:
        """从最终采用的文本证据中提取结构化字段。"""
        result = {
            "symptoms": [],
            "syndromes": [],
            "formulas": [],
            "herbs": [],
        }

        if not chunks:
            return result

        query_text = query.lower()
        answer_text = answer.lower()

        asks_manifestations = any(
            keyword in query_text
            for keyword in [
                "症状",
                "表现",
                "体征",
            ]
        )

        for chunk in chunks:
            content = chunk.content

            # --------------------------------------------
            # 证候
            # --------------------------------------------
            for match in re.finditer(
                r"(?:^|\n)\s*(?:证候|证型)\s*[:：]\s*([^\n，。；]+)",
                content,
            ):
                syndrome = cls._clean_phrase(
                    match.group(1)
                )

                if syndrome and (
                    syndrome.lower() in query_text
                    or syndrome.lower() in answer_text
                    or syndrome.lower() in chunk.title.lower()
                ):
                    cls._append_unique(
                        result["syndromes"],
                        syndrome,
                    )

            # --------------------------------------------
            # 典型表现 / 症状
            # --------------------------------------------
            if asks_manifestations:
                manifestation_patterns = [
                    r"典型表现\s*[:：]\s*([^\n]+)",
                    r"主要表现\s*[:：]\s*([^\n]+)",
                    r"常见症状\s*[:：]\s*([^\n]+)",
                    r"症见\s*[:：]?\s*([^\n。]+)",
                ]

                for pattern in manifestation_patterns:
                    match = re.search(
                        pattern,
                        content,
                    )

                    if match is None:
                        continue

                    for symptom in cls._split_manifestations(
                        match.group(1)
                    ):
                        cls._append_unique(
                            result["symptoms"],
                            symptom,
                        )

                    break

        return result

    # ========================================================
    # 5. Categorize Response Entities
    # ========================================================
    def _categorize_response_entities(
        self,
        query: str,
        answer: str,
        chunks: list[RetrievedChunk],
        graph: GraphData,
    ) -> dict[str, list[str]]:
        """生成统一结构化实体字段。"""
        result = {
            "symptoms": [],
            "syndromes": [],
            "formulas": [],
            "herbs": [],
        }

        mention_text = f"{query}\n{answer}".lower()

        # --------------------------------------------
        # A. 经过 intent pruning 后的图谱节点可以直接进入结构化字段。
        #    因为此时 graph 已经不再是原始 BFS 大子图。
        # --------------------------------------------
        for node in graph.nodes:
            field = TYPE_TO_FIELD.get(
                node.type
            )

            if field is not None:
                self._append_unique(
                    result[field],
                    node.label,
                )

        # --------------------------------------------
        # B. 文本证据中明确出现的图谱已知实体，
        #    仅在 Query / Answer 中被提及时补充。
        # --------------------------------------------
        chunk_text = "\n".join(
            chunk.content
            for chunk in chunks
        ).lower()

        for entity in self.graph_search.entities:
            field = TYPE_TO_FIELD.get(
                entity.type
            )

            if field is None:
                continue

            candidates = [
                entity.name,
                entity.alias,
            ]

            supported_by_text = any(
                name
                and name.lower() in chunk_text
                for name in candidates
            )

            mentioned = any(
                name
                and name.lower() in mention_text
                for name in candidates
            )

            if supported_by_text and mentioned:
                self._append_unique(
                    result[field],
                    entity.name,
                )

        # --------------------------------------------
        # C. TCM-SD 等结构化文本字段提取。
        # --------------------------------------------
        evidence_categories = (
            self._extract_structured_from_evidence(
                query=query,
                answer=answer,
                chunks=chunks,
            )
        )

        for field, values in evidence_categories.items():
            for value in values:
                self._append_unique(
                    result[field],
                    value,
                )

        return result

    @staticmethod
    def _filter_categories_by_intent(
        intent: str,
        categories: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        """根据用户问题意图限制结构化字段，避免字段污染。"""
        allowed_fields_by_intent = {
            "formula_composition": {
                "formulas",
                "herbs",
            },
            "syndrome_manifestation": {
                "symptoms",
                "syndromes",
            },
            "symptom_to_formula": {
                "symptoms",
                "syndromes",
                "formulas",
            },
            "mechanism_explanation": {
                "formulas",
                "herbs",
            },
            "effect_query": {
                "formulas",
                "herbs",
            },
            "contraindication_query": {
                "formulas",
                "herbs",
            },
            "definition_query": {
                "symptoms",
                "syndromes",
                "formulas",
                "herbs",
            },
            "global_summary": set(),
            "general": {
                "symptoms",
                "syndromes",
                "formulas",
                "herbs",
            },
        }

        allowed = allowed_fields_by_intent.get(
            intent,
            {
                "symptoms",
                "syndromes",
                "formulas",
                "herbs",
            },
        )

        return {
            field: values if field in allowed else []
            for field, values in categories.items()
        }

    @staticmethod
    def _should_use_community_summaries(
        query: str,
        intent: str,
        matched_entity_count: int,
    ) -> bool:
        """判断是否启用轻量社区摘要，避免具体事实问题被全局摘要冲淡。"""
        if intent == "global_summary":
            return True

        if matched_entity_count > 0:
            return False

        return any(
            keyword in query
            for keyword in [
                "概览",
                "总览",
                "总结",
                "知识结构",
                "学习路线",
                "有哪些模块",
                "有哪些主题",
            ]
        )

    # ========================================================
    # 6. Query
    # ========================================================
    def query(
        self,
        request: GraphRAGQueryRequest,
    ) -> QAResult:
        intent = self._detect_intent(
            request.query
        )

        print(
            "[GraphRAG] "
            f"intent={intent}"
        )

        # ----------------------------------------------------
        # 路 1：RAG 文本证据
        # ----------------------------------------------------
        retrieval_k = max(
            request.top_k * 3,
            8,
        )

        retrieved_chunks = self.vector_search.search(
            request.query,
            top_k=retrieval_k,
        )

        chunks = self._select_relevant_chunks(
            query=request.query,
            chunks=retrieved_chunks,
            intent=intent,
            top_k=request.top_k,
        )

        # ----------------------------------------------------
        # 路 2：实体识别 + 图谱路径
        # ----------------------------------------------------
        entities = self.graph_search.extract_entities(
            request.query
        )

        community_summaries: list[CommunitySummary] = []

        if self._should_use_community_summaries(
            query=request.query,
            intent=intent,
            matched_entity_count=len(entities),
        ):
            community_summaries = self.community_search.search(
                query=request.query,
                top_k=min(
                    request.top_k,
                    3,
                ),
            )

        candidate_graph = self.graph_search.search_paths(
            entities,
            max_hops=request.max_hops,
        )

        graph = self._prune_graph_by_intent(
            query=request.query,
            intent=intent,
            graph=candidate_graph,
        )

        # ----------------------------------------------------
        # 图谱主导型问题的证据收口
        # ----------------------------------------------------
        # 症状找方剂类问题的主证据是“症状--提示-->证候--对应-->方剂”。
        # 当该图谱路径已经命中时，不再把文本片段中的图谱外方剂、食疗汤、粥方
        # 扩展进主答案，降低回答发散和 evidence 噪声。
        if intent == "symptom_to_formula" and graph.edges:
            chunks = []

        print(
            "[GraphRAG] "
            f"candidate_graph={len(candidate_graph.nodes)} nodes / "
            f"{len(candidate_graph.edges)} edges; "
            f"final_graph={len(graph.nodes)} nodes / "
            f"{len(graph.edges)} edges; "
            f"evidence={len(chunks)}; "
            f"communities={len(community_summaries)}"
        )

        # ----------------------------------------------------
        # Evidence Fusion Prompt
        # ----------------------------------------------------
        prompt = self._build_prompt(
            query=request.query,
            chunks=chunks,
            graph=graph,
            community_summaries=community_summaries,
            intent=intent,
        )

        # ----------------------------------------------------
        # LLM / Fallback Answer
        # ----------------------------------------------------
        answer = self._generate_answer(
            query=request.query,
            chunks=chunks,
            graph=graph,
            community_summaries=community_summaries,
            prompt=prompt,
            intent=intent,
        )

        # ----------------------------------------------------
        # Structured Fields
        # ----------------------------------------------------
        categories = self._categorize_response_entities(
            query=request.query,
            answer=answer,
            chunks=chunks,
            graph=graph,
        )

        categories = self._filter_categories_by_intent(
            intent=intent,
            categories=categories,
        )

        # ----------------------------------------------------
        # Unified QAResult
        # ----------------------------------------------------
        community_evidence_items = [
            EvidenceItem(
                title=(
                    "图谱社区摘要："
                    f"{summary.title}"
                ),
                content=summary.content,
            )
            for summary in community_summaries
        ]

        chunk_evidence_items = [
            EvidenceItem(
                title=item.title,
                content=item.content,
            )
            for item in chunks
        ]

        if intent == "global_summary":
            evidence_items = [
                *community_evidence_items,
                *chunk_evidence_items,
            ]
        else:
            evidence_items = [
                *chunk_evidence_items,
                *community_evidence_items,
            ]

        return QAResult(
            answer=answer,
            symptoms=categories["symptoms"],
            syndromes=categories["syndromes"],
            formulas=categories["formulas"],
            herbs=categories["herbs"],
            graph=graph,
            evidence=evidence_items,
            follow_up_questions=[],
        )

    # ========================================================
    # 7. Prompt
    # ========================================================
    @staticmethod
    def _build_prompt(
        query: str,
        chunks: list[RetrievedChunk],
        graph: GraphData,
        community_summaries: list[CommunitySummary],
        intent: str,
    ) -> str:
        """将文本证据和图谱证据融合成统一 Prompt。"""
        text_lines: list[str] = []

        for idx, chunk in enumerate(
            chunks,
            start=1,
        ):
            text_lines.append(
                f"[文本证据{idx}] "
                f"标题：{chunk.title}\n"
                f"内容：{chunk.content}"
            )

        node_name = {
            node.id: node.label
            for node in graph.nodes
        }

        graph_lines: list[str] = []

        for idx, edge in enumerate(
            graph.edges,
            start=1,
        ):
            source = node_name.get(
                edge.source,
                edge.source,
            )

            target = node_name.get(
                edge.target,
                edge.target,
            )

            graph_lines.append(
                f"[图谱证据{idx}] "
                f"{source} "
                f"--{edge.label}--> "
                f"{target}"
            )

        text_block = (
            "\n\n".join(text_lines)
            if text_lines
            else "未检索到文本证据。"
        )

        graph_block = (
            "\n".join(graph_lines)
            if graph_lines
            else "未检索到图谱关系。"
        )

        community_lines = [
            f"[社区摘要{idx}] "
            f"{summary.title}\n"
            f"{summary.content}"
            for idx, summary in enumerate(
                community_summaries,
                start=1,
            )
        ]

        community_block = (
            "\n\n".join(community_lines)
            if community_lines
            else "未启用或未命中社区摘要。"
        )

        intent_label = INTENT_LABELS.get(
            intent,
            "一般知识查询",
        )

        intent_rules = {
            "formula_composition": (
                "本题是方剂组成查询。优先使用“方剂--包含-->药材”的图谱证据；"
                "只回答组成药材，不展开禁忌、功效、文献或其他方剂。"
            ),
            "syndrome_manifestation": (
                "本题是证候症状表现查询。优先使用包含“证候/典型表现/症状”的文本证据；"
                "图谱为空时不需要强行解释图谱。"
            ),
            "symptom_to_formula": (
                "本题是症状到方剂查询。优先使用“症状--提示-->证候--对应-->方剂”的图谱路径；"
                "主答案只围绕图谱证据中出现的证候和方剂作答；"
                "不要根据文本证据额外扩展图谱外方剂、食疗汤、粥方或药材组成，除非用户明确追问。"
            ),
            "mechanism_explanation": (
                "本题是机制或配伍解释查询。优先使用直接说明机制的文本证据；"
                "普通功效、来源、禁忌关系不能作为机制结论的主要依据。"
            ),
            "effect_query": (
                "本题是功效作用查询。只围绕用户询问对象的功效作答，"
                "不要扩展无关方剂、药材或文献支路。"
            ),
            "contraindication_query": (
                "本题是禁忌注意查询。只围绕用户询问对象的禁忌或慎用信息作答，"
                "不要输出个体化用药建议。"
            ),
            "global_summary": (
                "本题是图谱全局概览查询。优先使用社区摘要组织知识结构，"
                "再用文本证据或图谱路径补充一两个具体例子；"
                "不要把社区摘要误当成药典原文。"
            ),
        }.get(
            intent,
            "只回答用户直接询问的目标信息。",
        )

        return f"""
请依据下面证据回答用户问题。

【用户问题】
{query}

【问题意图】
{intent_label}

【意图规则】
{intent_rules}

【文本证据】
{text_block}

【图谱证据】
{graph_block}

【社区摘要】
{community_block}

【回答要求】
1. 先直接回答用户问题，不要以“根据提供的证据”“根据检索结果”“根据图谱证据”“结合文本证据”等模板化语句开头；
2. 只依据提供证据回答，不补造不存在的事实；
3. 严格区分文本证据与图谱证据，证据不足时明确说明；
4. 不得进行证据未明确支持的医学因果、疗效或调理方向推断；
5. 若问题明确包含某个证候、方剂、药材或症状名称，优先使用名称完全匹配的证据，不得把相近概念混为同一概念；
6. 只回答用户直接询问的目标信息；
7. 除非回答当前问题所必需，不得列举或解释无关的方剂、药材、功效、文献或其他图谱支路；
8. 对与当前问题无关的证据直接忽略，不要为了说明“未使用”而再次复述这些证据；
9. 回答要像教学辅助说明：先给结论，再用短句分层解释，避免堆砌证据标题；
10. 药典/HKCMMS 类证据只回答来源、性状、鉴别、检查、含量测定等标准信息，不扩展成临床用药建议；
11. 不构成医疗诊断或用药建议。
""".strip()

    # ========================================================
    # 8. Generate Answer
    # ========================================================
    @staticmethod
    def _clean_answer_prefix(
        answer: str,
    ) -> str:
        """清理 LLM 常见模板化开头。"""
        cleaned = answer.strip()

        prefixes = [
            "根据提供的证据，",
            "根据检索结果，",
            "根据图谱证据，",
            "根据文本证据，",
            "结合文本证据，",
            "结合图谱证据，",
            "根据提供的文本证据和图谱证据，",
            "根据文本证据和图谱证据，",
        ]

        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break

        # 再处理少量变体：根据……证据，xxx
        cleaned = re.sub(
            r"^根据[^，。]{0,30}证据[，,]\s*",
            "",
            cleaned,
        ).strip()

        return cleaned

    def _generate_answer(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        graph: GraphData,
        community_summaries: list[CommunitySummary],
        prompt: str,
        intent: str,
    ) -> str:
        if self.llm_client is not None:
            try:
                answer = self.llm_client.generate(
                    prompt
                )

                answer = str(answer).strip()

                if not answer:
                    raise RuntimeError(
                        "LLM 返回空字符串"
                    )

                print(
                    "[LLM] 调用成功"
                )

                return self._clean_answer_prefix(
                    simplify_hkcmms_display_text(answer)
                )

            except Exception as exc:
                print(
                    "[LLM] 调用失败，使用 fallback answer"
                )
                print(
                    "[LLM] "
                    f"错误类型: {type(exc).__name__}"
                )
                print(
                    "[LLM] "
                    f"错误信息: {exc}"
                )

        return simplify_hkcmms_display_text(
            self._fallback_answer(
                query=query,
                chunks=chunks,
                graph=graph,
                community_summaries=community_summaries,
                intent=intent,
            )
        )

    # ========================================================
    # 9. Fallback Answer
    # ========================================================
    @staticmethod
    def _list_graph_nodes_by_type(
        graph: GraphData,
        node_type: str,
    ) -> list[str]:
        result: list[str] = []

        for node in graph.nodes:
            if node.type == node_type and node.label not in result:
                result.append(node.label)

        return result

    @staticmethod
    def _evidence_target(
        content: str,
    ) -> str:
        target_match = re.search(
            r"药材条目：([^\n]+)",
            content,
        )

        if target_match:
            return target_match.group(1).strip()

        return ""

    @staticmethod
    def _evidence_body(
        content: str,
    ) -> str:
        body = content.strip()
        body_match = re.search(
            r"正文：\s*(.+)",
            body,
            flags=re.S,
        )

        if body_match:
            body = body_match.group(1).strip()

        return re.sub(
            r"\s+",
            " ",
            body,
        ).strip()

    @staticmethod
    def _clean_pharmacopoeia_item(
        item: str,
    ) -> str:
        return clean_hkcmms_item_text(item)

    @classmethod
    def _extract_check_items_from_chunks(
        cls,
        chunks: list[RetrievedChunk],
    ) -> tuple[str, list[str]]:
        target = ""
        items: list[str] = []

        for chunk in chunks:
            if not target:
                target = cls._evidence_target(
                    chunk.content
                )

            searchable_text = "\n".join(
                [
                    chunk.title,
                    cls._evidence_body(chunk.content),
                ]
            )

            for match in re.finditer(
                r"(?:5\.\d+){1,2}\s*([^。；;\n]{1,60})",
                searchable_text,
            ):
                item = cls._clean_pharmacopoeia_item(
                    match.group(1)
                )

                if item and item not in items:
                    items.append(item)

        return target, items

    @classmethod
    def _extract_identification_methods_from_chunks(
        cls,
        chunks: list[RetrievedChunk],
    ) -> tuple[str, list[str]]:
        target = ""
        methods: list[str] = []
        method_keywords = [
            "顯微鑒別",
            "显微鉴别",
            "理化鑒別",
            "理化鉴别",
            "薄層色譜鑒別",
            "薄层色谱鉴别",
            "高效液相色譜指紋圖譜鑒別法",
            "高效液相色譜指紋圖譜法",
            "高效液相色谱指纹图谱鉴别法",
        ]

        for chunk in chunks:
            if not target:
                target = cls._evidence_target(
                    chunk.content
                )

            searchable_text = "\n".join(
                [
                    chunk.title,
                    cls._evidence_body(chunk.content),
                ]
            )

            for keyword in method_keywords:
                if keyword in searchable_text and keyword not in methods:
                    methods.append(keyword)

        return target, methods

    @classmethod
    def _extract_assay_parts_from_chunks(
        cls,
        chunks: list[RetrievedChunk],
    ) -> tuple[str, list[str]]:
        target = ""
        parts: list[str] = []

        for chunk in chunks:
            if not target:
                target = cls._evidence_target(
                    chunk.content
                )

            searchable_text = "\n".join(
                [
                    chunk.title,
                    cls._evidence_body(chunk.content),
                ]
            )

            for keyword in [
                "對照品溶液",
                "对照品溶液",
                "供試品溶液",
                "供试品溶液",
                "操作程序",
                "色譜條件",
                "色谱条件",
            ]:
                if keyword in searchable_text and keyword not in parts:
                    parts.append(keyword)

        return target, parts

    @classmethod
    def _extract_concise_evidence_answer(
        cls,
        query: str,
        content: str,
    ) -> str:
        """从结构化 evidence 中抽取一句更像回答的话，用于无 LLM fallback。"""
        text = content.strip()

        if not text:
            return ""

        target = cls._evidence_target(
            text
        )

        body = cls._evidence_body(
            text,
        )

        if not body:
            return ""

        target_prefix = (
            f"{target}："
            if target
            else ""
        )

        if "来源" in query:
            sentence = re.search(
                r"(?:\d+\.)?來源(.+?。)",
                body,
            )
            if sentence:
                return (
                    f"{target}的来源是"
                    f"{sentence.group(1).strip()}"
                    if target
                    else f"来源是{sentence.group(1).strip()}"
                )

        if any(
            keyword in query
            for keyword in [
                "检查",
                "檢查",
                "检查项目",
            ]
        ):
            items = re.findall(
                r"5\.\d+\s*([^。；\n]{2,40})",
                body,
            )
            cleaned = [
                cls._clean_pharmacopoeia_item(item)
                for item in items
            ]
            cleaned = [
                item
                for item in cleaned
                if item
            ]

            if cleaned:
                unique_items = list(
                    dict.fromkeys(cleaned)
                )

                return (
                    f"{target_prefix}检查项目包括："
                    f"{'、'.join(unique_items[:6])}。"
                )

        if any(
            keyword in query
            for keyword in [
                "鉴别",
                "鑒別",
                "鉴别方法",
            ]
        ):
            methods = []

            for keyword in [
                "顯微鑒別",
                "理化鑒別",
                "薄層色譜鑒別",
                "高效液相色譜指紋圖譜",
            ]:
                if keyword in body and keyword not in methods:
                    methods.append(keyword)

            if methods:
                return (
                    f"{target_prefix}鉴别相关内容包括"
                    f"{'、'.join(methods)}。"
                )

        first_sentence = re.split(
            r"(?<=[。！？!?])",
            body,
        )[0].strip()

        if first_sentence and len(first_sentence) <= 180:
            return f"{target_prefix}{first_sentence}"

        return ""

    def _fallback_answer(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        graph: GraphData,
        community_summaries: list[CommunitySummary],
        intent: str,
    ) -> str:
        """无可用 LLM 时的意图感知降级回答。"""
        if intent == "global_summary" and community_summaries:
            lines = [
                "这个问题更适合从图谱社区来做整体理解。"
            ]

            for summary in community_summaries[:3]:
                lines.append(
                    f"{summary.title}：{summary.content}"
                )

            return "\n".join(lines)

        if intent == "formula_composition":
            formulas = self._list_graph_nodes_by_type(
                graph,
                "方剂",
            )
            herbs = self._list_graph_nodes_by_type(
                graph,
                "药材",
            )

            if formulas and herbs:
                return (
                    f"{formulas[0]}包含的药材包括："
                    f"{'、'.join(herbs)}。"
                )

        if intent == "syndrome_manifestation":
            extracted = self._extract_structured_from_evidence(
                query=query,
                answer="",
                chunks=chunks,
            )

            syndromes = extracted.get(
                "syndromes",
                [],
            )
            symptoms = extracted.get(
                "symptoms",
                [],
            )

            if symptoms:
                syndrome_name = (
                    syndromes[0]
                    if syndromes
                    else self._extract_query_hint(query)
                )

                return (
                    f"{syndrome_name}的典型表现主要包括："
                    f"{'、'.join(symptoms)}。"
                )

        if intent == "symptom_to_formula":
            node_name = {
                node.id: node.label
                for node in graph.nodes
            }

            syndrome_to_formulas: dict[
                str,
                list[str],
            ] = {}

            for edge in graph.edges:
                source_node = self._get_graph_node(
                    graph,
                    edge.source,
                )
                target_node = self._get_graph_node(
                    graph,
                    edge.target,
                )

                if (
                    source_node
                    and target_node
                    and source_node.type == "证候"
                    and target_node.type == "方剂"
                    and edge.label == "对应"
                ):
                    syndrome = node_name.get(
                        edge.source,
                        edge.source,
                    )
                    formula = node_name.get(
                        edge.target,
                        edge.target,
                    )
                    syndrome_to_formulas.setdefault(
                        syndrome,
                        [],
                    ).append(formula)

            if syndrome_to_formulas:
                parts = []

                for syndrome, formulas in syndrome_to_formulas.items():
                    parts.append(
                        f"{syndrome}：{'、'.join(formulas)}"
                    )

                return (
                    f"与“{query}”相关的证候及对应方剂包括："
                    + "；".join(parts)
                    + "。"
                )

        if intent == "mechanism_explanation" and chunks:
            selected_sentences: list[str] = []

            for chunk in chunks:
                sentences = re.split(
                    r"(?<=[。！？!?])",
                    chunk.content,
                )

                for sentence in sentences:
                    text = sentence.strip()

                    if not text:
                        continue

                    if any(
                        keyword in text
                        for keyword in [
                            "反佐",
                            "格拒",
                            "同气相求",
                            "辛热太过",
                            "吴茱萸汤",
                            "黄连",
                        ]
                    ):
                        self._append_unique(
                            selected_sentences,
                            text,
                        )

                    if len(selected_sentences) >= 3:
                        break

                if len(selected_sentences) >= 3:
                    break

            if selected_sentences:
                return "".join(
                    selected_sentences
                )

        if chunks and any(
            keyword in query
            for keyword in [
                "鉴别",
                "鑒別",
                "鉴别方法",
                "鑒別方法",
            ]
        ):
            (
                target,
                methods,
            ) = self._extract_identification_methods_from_chunks(
                chunks
            )

            if methods:
                target_name = (
                    target
                    if target
                    else self._extract_query_hint(query)
                )

                return (
                    f"从已召回的 HKCMMS 标准片段看，"
                    f"{target_name}的鉴别内容主要包括："
                    f"{'、'.join(methods[:6])}。"
                    "如需做实验细节核对，应继续查看对应的操作程序原文。"
                )

        if chunks and any(
            keyword in query
            for keyword in [
                "含量",
                "测定",
                "測定",
            ]
        ):
            (
                target,
                assay_parts,
            ) = self._extract_assay_parts_from_chunks(
                chunks
            )

            if assay_parts:
                target_name = (
                    target
                    if target
                    else self._extract_query_hint(query)
                )

                return (
                    f"从已召回的 HKCMMS 标准片段看，"
                    f"{target_name}的含量测定依据在“含量測定”栏目下，"
                    f"当前证据涉及：{'、'.join(assay_parts[:6])}。"
                    "具体称量、溶剂和色谱条件建议以药典原文为准。"
                )

        if chunks and any(
            keyword in query
            for keyword in [
                "检查",
                "檢查",
                "检查项目",
                "檢查項目",
            ]
        ):
            target, check_items = self._extract_check_items_from_chunks(
                chunks
            )

            if check_items:
                target_name = (
                    target
                    if target
                    else self._extract_query_hint(query)
                )
                item_text = "、".join(
                    check_items[:8]
                )

                return (
                    f"从已召回的 HKCMMS 标准片段看，"
                    f"{target_name}的检查项目包括：{item_text}。"
                    "这些内容适合用于药典条目核对，"
                    "不等同于临床用药建议。"
                )

        if chunks:
            source_title = chunks[0].title
            source_content = chunks[0].content

            concise = self._extract_concise_evidence_answer(
                query=query,
                content=source_content,
            )

            if concise:
                return concise

            return (
                f"可以先看“{source_title}”这条资料。"
                "它与问题最相关；如果需要更完整的教学表述，"
                "建议开启大模型生成后再结合其他证据整合。"
            )

        if graph.edges:
            node_name = {
                node.id: node.label
                for node in graph.nodes
            }

            path_texts = [
                f"{node_name.get(edge.source, edge.source)}"
                f" --{edge.label}--> "
                f"{node_name.get(edge.target, edge.target)}"
                for edge in graph.edges[:8]
            ]

            return (
                f"与“{query}”相关的图谱关系包括："
                + "；".join(path_texts)
                + "。"
            )

        return (
            f"当前未检索到足够证据回答“{query}”。"
            "请结合规范教材与正式资料进一步核对。"
        )

    # ========================================================
    # 10. Legacy Helper
    # ========================================================
    @staticmethod
    def _categorize_nodes(
        graph: GraphData,
    ) -> dict[str, list[str]]:
        """保留旧辅助函数，避免其他模块可能仍有调用。"""
        result = {
            "symptoms": [],
            "syndromes": [],
            "formulas": [],
            "herbs": [],
        }

        for node in graph.nodes:
            field = TYPE_TO_FIELD.get(
                node.type
            )

            if (
                field
                and node.label not in result[field]
            ):
                result[field].append(
                    node.label
                )

        return result
