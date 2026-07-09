from __future__ import annotations

from app.graph_search import GraphSearch
from app.llm_client import LLMClient
from app.schemas import (
    EvidenceItem,
    GraphData,
    GraphRAGQueryRequest,
    QAResult,
)
from app.vector_search import RetrievedChunk, VectorSearch


TYPE_TO_FIELD = {
    "症状": "symptoms",
    "证候": "syndromes",
    "方剂": "formulas",
    "药材": "herbs",
}


class GraphRAGService:
    """
   
    完整流程：
    1. 文本检索；
    2. 实体识别；
    3. 图谱路径检索；
    4. 两路证据融合；
    5. 调用 LLM 或使用本地降级回答；
    6. 返回组长统一 QAResult JSON。
    """

    def __init__(
        self,
        vector_search: VectorSearch,
        graph_search: GraphSearch,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.vector_search = vector_search
        self.graph_search = graph_search
        self.llm_client = llm_client

    def query(self, request: GraphRAGQueryRequest) -> QAResult:
        # 路 1：RAG 文本证据
        chunks = self.vector_search.search(
            request.query,
            top_k=request.top_k,
        )

        # 路 2：实体识别 + 图谱路径
        entities = self.graph_search.extract_entities(request.query)

        graph = self.graph_search.search_paths(
            entities,
            max_hops=request.max_hops,
        )

        # 融合文本和图谱证据
        prompt = self._build_prompt(
            query=request.query,
            chunks=chunks,
            graph=graph,
        )

        # 有真实 LLM 配置就调用；否则使用本地可重复回答
        answer = self._generate_answer(
            query=request.query,
            chunks=chunks,
            graph=graph,
            prompt=prompt,
        )

        categories = self._categorize_nodes(graph)

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

    @staticmethod
    def _build_prompt(
        query: str,
        chunks: list[RetrievedChunk],
        graph: GraphData,
    ) -> str:
        """将文本证据和图谱证据融合成统一 Prompt。"""

        text_lines = []

        for idx, chunk in enumerate(chunks, start=1):
            text_lines.append(
                f"[文本证据{idx}] "
                f"标题：{chunk.title}\n"
                f"内容：{chunk.content}"
            )

        node_name = {
            node.id: node.label
            for node in graph.nodes
        }

        graph_lines = []

        for idx, edge in enumerate(graph.edges, start=1):
            source = node_name.get(edge.source, edge.source)
            target = node_name.get(edge.target, edge.target)

            graph_lines.append(
                f"[图谱证据{idx}] "
                f"{source} --{edge.label}--> {target}"
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
3. 可以说明“资料片段显示”或“图谱关系显示”；
4. 证据不足时明确说明；
5. 不构成医疗诊断或用药建议。
""".strip()

    def _generate_answer(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        graph: GraphData,
        prompt: str,
    ) -> str:
        if self.llm_client is not None:
            try:
                return self.llm_client.generate(prompt)
            except Exception:
                # 开发期避免上游模型临时错误导致整个 API 500
                pass

        return self._fallback_answer(
            query=query,
            chunks=chunks,
            graph=graph,
        )

    @staticmethod
    def _fallback_answer(
        query: str,
        chunks: list[RetrievedChunk],
        graph: GraphData,
    ) -> str:
        """无 API Key 时的开发期降级回答，确保接口仍能联调。"""

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
            f"针对“{query}”，当前开发版依据已检索证据进行教学辅助整理。"
        ]

        if path_texts:
            parts.append(
                "图谱关系显示："
                + "；".join(path_texts)
                + "。"
            )
        else:
            parts.append("当前未匹配到可用图谱关系。")

        if chunks:
            parts.append(
                "资料片段方面，已检索到："
                + "；".join(item.title for item in chunks[:3])
                + "。"
            )
        else:
            parts.append("当前未检索到可用文本片段。")

        parts.append("请结合规范教材与正式资料进一步核对。")

        return "".join(parts)

    @staticmethod
    def _categorize_nodes(
        graph: GraphData,
    ) -> dict[str, list[str]]:
        """按组长统一结果格式提取 symptoms / syndromes / formulas / herbs。"""

        result = {
            "symptoms": [],
            "syndromes": [],
            "formulas": [],
            "herbs": [],
        }

        for node in graph.nodes:
            field = TYPE_TO_FIELD.get(node.type)

            if field and node.label not in result[field]:
                result[field].append(node.label)

        return result
