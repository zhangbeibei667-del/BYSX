from __future__ import annotations

import re
from typing import Protocol

from app.graph_search import GraphSearch
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

    完整流程：
    1. 文本检索；
    2. 查询感知证据过滤；
    3. 实体识别；
    4. 图谱路径检索；
    5. 文本证据与图谱证据融合；
    6. 调用 LLM 或本地降级回答；
    7. 生成结构化 symptoms / syndromes / formulas / herbs；
    8. 返回统一 QAResult。

    当前兼容：
    - Hash VectorSearch；
    - MilvusVectorSearch。
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

    # ========================================================
    # 1. Query Hint
    # ========================================================
    @staticmethod
    def _extract_query_hint(
        query: str,
    ) -> str:
        """
        从常见问句中提取较稳定的目标词面。

        示例：
            风寒袭肺证有哪些症状？
            -> 风寒袭肺证

            归脾汤有什么功效？
            -> 归脾汤

        该 hint 只用于：
        - 证据过滤；
        - 结构化结果辅助。

        它不替代正式知识图谱实体识别。
        """
        text = query.strip().lower()

        prefixes = [
            "请问",
            "我想知道",
            "想了解",
            "请介绍一下",
            "介绍一下",
        ]

        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        suffixes = [
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
        ]

        for suffix in suffixes:
            if text.endswith(suffix):
                text = text[:-len(suffix)].strip()
                break

        return text

    # ========================================================
    # 2. Query-aware Evidence Selection
    # ========================================================
    def _select_relevant_chunks(
        self,
        query: str,
        chunks: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        """
        对最终进入 Prompt / Evidence 的文本片段做轻量过滤。

        目的：
        当用户明确询问某个证候、方剂等对象时，
        避免把名称相近但并非同一对象的片段一起交给 LLM。

        示例：
            Query: 风寒袭肺证有哪些症状？

        若候选中存在：
            风寒袭肺证：定义与典型表现

        则优先只保留明确包含“风寒袭肺证”的片段，
        避免把“风寒束肺证”“风寒袭表证”混入回答。

        无稳定 hint 或无精确命中时，保留原检索结果。
        """
        if not chunks:
            return []

        hint = self._extract_query_hint(query)

        if not hint or len(hint) < 2:
            return chunks

        # 标题精确包含优先级最高。
        title_matches = [
            chunk
            for chunk in chunks
            if hint in chunk.title.lower()
        ]

        if title_matches:
            return title_matches

        # 标题没有命中时，再看正文。
        content_matches = [
            chunk
            for chunk in chunks
            if hint in chunk.content.lower()
        ]

        if content_matches:
            return content_matches

        return chunks

    # ========================================================
    # 3. Structured Entity Helpers
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

        # 去 Markdown 强调。
        text = text.replace("**", "")

        # 去常见引导词。
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

        # 去句末符号。
        text = text.strip(
            " \t\r\n，。；：:、！？!?"
        )

        return text

    @classmethod
    def _split_manifestations(
        cls,
        text: str,
    ) -> list[str]:
        """
        将“典型表现”字段拆成轻量症状短语。

        仅做证据内字符串拆分，
        不进行医学推断。
        """
        parts = re.split(
            r"[，、；;。\n]+",
            text,
        )

        result: list[str] = []

        for part in parts:
            phrase = cls._clean_phrase(part)

            if not phrase:
                continue

            # 过长片段往往已是解释性句子，
            # 不直接塞入 symptoms。
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
        """
        从最终采用的文本证据中提取结构化字段。

        当前重点支持 TCM-SD 这类结构化文本：
            证候：xxx
            典型表现：xxx，xxx，xxx

        约束：
        - 只从已经展示给 LLM / 页面使用的证据提取；
        - 不凭空补造；
        - symptoms 仅在用户确实询问症状/表现时提取。
        """
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

                # 只保留与当前问答真正相关的名称。
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

                    # 同一片段命中第一个明确表现区块即可。
                    break

        return result

    # ========================================================
    # 4. Categorize Response Entities
    # ========================================================
    def _categorize_response_entities(
        self,
        query: str,
        answer: str,
        chunks: list[RetrievedChunk],
        graph: GraphData,
    ) -> dict[str, list[str]]:
        """
        生成统一结构化实体字段。

        证据来源分两层：

        A. 图谱已知实体
           - Query / Answer 中实际出现；
           - 且得到 Graph 或文本证据支持。

        B. 文本证据中的明确结构化信息
           - 例如 TCM-SD 的“证候：”“典型表现：”；
           - 只从最终采用的证据中提取。

        最终进行去重合并。
        """
        result = {
            "symptoms": [],
            "syndromes": [],
            "formulas": [],
            "herbs": [],
        }

        mention_text = f"{query}\n{answer}".lower()

        # --------------------------------------------
        # A. Graph / Graph Catalog 支持
        # --------------------------------------------
        supported_ids = {
            node.id
            for node in graph.nodes
        }

        chunk_text = "\n".join(
            chunk.content
            for chunk in chunks
        ).lower()

        # 文本证据中明确出现的图谱已知实体，
        # 也视为被证据支持。
        for entity in self.graph_search.entities:
            candidates = [
                entity.name,
                entity.alias,
            ]

            if any(
                name
                and name.lower() in chunk_text
                for name in candidates
            ):
                supported_ids.add(entity.id)

        for entity in self.graph_search.entities:
            field = TYPE_TO_FIELD.get(
                entity.type
            )

            if field is None:
                continue

            if entity.id not in supported_ids:
                continue

            candidates = [
                entity.name,
                entity.alias,
            ]

            mentioned = any(
                name
                and name.lower() in mention_text
                for name in candidates
            )

            if mentioned:
                self._append_unique(
                    result[field],
                    entity.name,
                )

        # --------------------------------------------
        # B. Text Evidence Structured Extraction
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

    # ========================================================
    # 5. Query
    # ========================================================
    def query(
        self,
        request: GraphRAGQueryRequest,
    ) -> QAResult:
        # ----------------------------------------------------
        # 路 1：RAG 文本证据
        # ----------------------------------------------------
        retrieved_chunks = self.vector_search.search(
            request.query,
            top_k=request.top_k,
        )

        # 进一步过滤“同名近似但非同一对象”的噪声。
        chunks = self._select_relevant_chunks(
            query=request.query,
            chunks=retrieved_chunks,
        )

        # ----------------------------------------------------
        # 路 2：实体识别 + 图谱路径
        # ----------------------------------------------------
        entities = self.graph_search.extract_entities(
            request.query
        )

        graph = self.graph_search.search_paths(
            entities,
            max_hops=request.max_hops,
        )

        # ----------------------------------------------------
        # Evidence Fusion Prompt
        # ----------------------------------------------------
        prompt = self._build_prompt(
            query=request.query,
            chunks=chunks,
            graph=graph,
        )

        # ----------------------------------------------------
        # LLM / Fallback Answer
        # ----------------------------------------------------
        answer = self._generate_answer(
            query=request.query,
            chunks=chunks,
            graph=graph,
            prompt=prompt,
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

        # ----------------------------------------------------
        # Unified QAResult
        # ----------------------------------------------------
        return QAResult(
            answer=answer,
            symptoms=categories["symptoms"],
            syndromes=categories["syndromes"],
            formulas=categories["formulas"],
            herbs=categories["herbs"],
            graph=graph,
            evidence=[
                EvidenceItem(
                    title=item.title,
                    content=item.content,
                )
                for item in chunks
            ],
            follow_up_questions=[],
        )

    # ========================================================
    # 6. Prompt
    # ========================================================
    @staticmethod
    def _build_prompt(
        query: str,
        chunks: list[RetrievedChunk],
        graph: GraphData,
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

        return f"""
请根据下面证据回答用户问题。

【用户问题】
{query}

【文本证据】
{text_block}

【图谱证据】
{graph_block}

【要求】
1. 只依据提供证据回答；
2. 不补造不存在的事实；
3. 严格区分文本证据与图谱证据；
4. 不得进行证据未明确支持的医学因果、疗效或调理方向推断；
5. 若问题明确包含某个证候、方剂、药材或症状名称，优先使用名称完全匹配的证据，不得把相近概念混为同一概念；
6. 只回答用户直接询问的目标信息；
7. 除非回答当前问题所必需，不得列举或解释无关的方剂、药材、功效、文献或其他图谱支路；
8. 对与当前问题无关的证据直接忽略，不要为了说明“未使用”而再次复述这些证据；
9. 证据不足时明确说明；
10. 不构成医疗诊断或用药建议。
""".strip()

    # ========================================================
    # 7. Generate Answer
    # ========================================================
    def _generate_answer(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        graph: GraphData,
        prompt: str,
    ) -> str:
        if self.llm_client is not None:
            try:
                return self.llm_client.generate(
                    prompt
                )
            except Exception:
                # 开发期避免上游模型临时错误导致整个 API 500。
                pass

        return self._fallback_answer(
            query=query,
            chunks=chunks,
            graph=graph,
        )

    # ========================================================
    # 8. Fallback Answer
    # ========================================================
    @staticmethod
    def _fallback_answer(
        query: str,
        chunks: list[RetrievedChunk],
        graph: GraphData,
    ) -> str:
        """无可用 LLM 时的开发期降级回答。"""
        node_name = {
            node.id: node.label
            for node in graph.nodes
        }

        path_texts = [
            f"{node_name.get(edge.source, edge.source)}"
            f" --{edge.label}--> "
            f"{node_name.get(edge.target, edge.target)}"
            for edge in graph.edges[:12]
        ]

        parts = [
            f"针对“{query}”，当前依据已检索证据进行教学辅助整理。"
        ]

        if path_texts:
            parts.append(
                "图谱关系显示："
                + "；".join(path_texts)
                + "。"
            )
        else:
            parts.append(
                "当前未匹配到可用图谱关系。"
            )

        if chunks:
            parts.append(
                "资料片段方面，已检索到："
                + "；".join(
                    item.title
                    for item in chunks[:3]
                )
                + "。"
            )
        else:
            parts.append(
                "当前未检索到可用文本片段。"
            )

        parts.append(
            "请结合规范教材与正式资料进一步核对。"
        )

        return "".join(parts)

    # ========================================================
    # 9. Legacy Helper
    # ========================================================
    @staticmethod
    def _categorize_nodes(
        graph: GraphData,
    ) -> dict[str, list[str]]:
        """
        保留旧辅助函数，避免其他模块可能仍有调用。
        """
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
