from __future__ import annotations

import re
from collections import Counter, deque
from dataclasses import dataclass

from app.graph_search import GraphSearch
from app.schemas import EntityRecord, RelationRecord


@dataclass(frozen=True)
class CommunitySummary:
    """轻量 GraphRAG 社区摘要，作为 RAG 内部全局检索证据。"""

    community_id: str
    title: str
    content: str
    node_ids: list[str]
    entity_names: list[str]
    entity_types: list[str]
    relation_types: list[str]
    score: float = 0.0


class LightweightCommunitySearch:
    """
    无额外依赖的轻量社区发现与摘要。

    边界：
    - 只读取当前服务已经加载的统一实体和关系；
    - 不改写原始图谱数据；
    - 不新增对外 API 字段；
    - 社区摘要作为 RAG evidence 进入现有 QAResult。
    """

    def __init__(
        self,
        graph_search: GraphSearch,
        min_size: int = 2,
    ) -> None:
        self.graph_search = graph_search
        self.min_size = min_size
        self.summaries = self._build_summaries()

    def _build_undirected_adjacency(
        self,
    ) -> dict[str, set[str]]:
        adjacency: dict[str, set[str]] = {
            entity.id: set()
            for entity in self.graph_search.entities
        }

        for relation in self.graph_search.relations:
            if (
                relation.source_id
                not in self.graph_search.entity_by_id
                or relation.target_id
                not in self.graph_search.entity_by_id
            ):
                continue

            adjacency.setdefault(
                relation.source_id,
                set(),
            ).add(relation.target_id)

            adjacency.setdefault(
                relation.target_id,
                set(),
            ).add(relation.source_id)

        return adjacency

    def _discover_components(
        self,
        adjacency: dict[str, set[str]],
    ) -> list[list[str]]:
        visited: set[str] = set()
        components: list[list[str]] = []

        for node_id in sorted(adjacency):
            if node_id in visited:
                continue

            queue: deque[str] = deque([node_id])
            visited.add(node_id)
            component: list[str] = []

            while queue:
                current = queue.popleft()
                component.append(current)

                for next_id in sorted(
                    adjacency.get(current, set())
                ):
                    if next_id in visited:
                        continue

                    visited.add(next_id)
                    queue.append(next_id)

            if len(component) >= self.min_size:
                components.append(component)

        components.sort(
            key=lambda item: (
                -len(item),
                item[0],
            )
        )

        return components

    def _relations_in_component(
        self,
        node_ids: set[str],
    ) -> list[RelationRecord]:
        return [
            relation
            for relation in self.graph_search.relations
            if (
                relation.source_id in node_ids
                and relation.target_id in node_ids
            )
        ]

    @staticmethod
    def _top_items(
        counter: Counter[str],
        limit: int,
    ) -> list[str]:
        return [
            name
            for name, _count in counter.most_common(limit)
        ]

    def _summarize_component(
        self,
        index: int,
        node_ids: list[str],
    ) -> CommunitySummary:
        node_id_set = set(node_ids)
        entities = [
            self.graph_search.entity_by_id[node_id]
            for node_id in node_ids
            if node_id in self.graph_search.entity_by_id
        ]
        relations = self._relations_in_component(
            node_id_set
        )

        type_counter = Counter(
            entity.type
            for entity in entities
        )
        relation_counter = Counter(
            relation.relation
            for relation in relations
        )
        degree_counter: Counter[str] = Counter()

        for relation in relations:
            degree_counter[relation.source_id] += 1
            degree_counter[relation.target_id] += 1

        top_entities = [
            self.graph_search.entity_by_id[node_id].name
            for node_id in self._top_items(
                degree_counter,
                8,
            )
            if node_id in self.graph_search.entity_by_id
        ]

        if not top_entities:
            top_entities = [
                entity.name
                for entity in entities[:8]
            ]

        relation_examples: list[str] = []
        for relation in relations[:8]:
            source = self.graph_search.entity_by_id.get(
                relation.source_id
            )
            target = self.graph_search.entity_by_id.get(
                relation.target_id
            )

            if not source or not target:
                continue

            relation_examples.append(
                f"{source.name}--{relation.relation}-->{target.name}"
            )

        entity_types = self._top_items(
            type_counter,
            6,
        )
        relation_types = self._top_items(
            relation_counter,
            6,
        )

        type_text = "、".join(
            f"{name}{count}个"
            for name, count in type_counter.most_common()
        )
        relation_text = "、".join(
            f"{name}{count}条"
            for name, count in relation_counter.most_common(6)
        )
        top_text = "、".join(top_entities)
        example_text = "；".join(relation_examples)

        title_entities = "、".join(top_entities[:3])
        title = (
            f"社区{index + 1}：{title_entities}"
            if title_entities
            else f"社区{index + 1}"
        )

        content = (
            f"该社区包含{len(entities)}个实体、{len(relations)}条关系。"
            f"主题可以概括为围绕{top_text or '核心实体'}展开的知识联系。"
            f"实体类型分布：{type_text or '暂无'}。"
            f"主要关系：{relation_text or '暂无'}。"
            f"核心实体：{top_text or '暂无'}。"
        )

        if example_text:
            content += f"代表路径：{example_text}。"

        return CommunitySummary(
            community_id=f"C{index + 1:03d}",
            title=title,
            content=content,
            node_ids=node_ids,
            entity_names=top_entities,
            entity_types=entity_types,
            relation_types=relation_types,
        )

    def _build_summaries(
        self,
    ) -> list[CommunitySummary]:
        adjacency = self._build_undirected_adjacency()
        components = self._discover_components(
            adjacency
        )

        return [
            self._summarize_component(
                index=index,
                node_ids=node_ids,
            )
            for index, node_ids in enumerate(
                components
            )
        ]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        ascii_tokens = re.findall(
            r"[a-z0-9_]+",
            text.lower(),
        )
        chinese = "".join(
            re.findall(
                r"[\u4e00-\u9fff]",
                text,
            )
        )
        zh_tokens = [
            chinese[index:index + 2]
            for index in range(
                max(0, len(chinese) - 1)
            )
        ]

        return ascii_tokens + zh_tokens

    @staticmethod
    def _is_overview_query(query: str) -> bool:
        return any(
            keyword in query
            for keyword in [
                "概览",
                "总览",
                "总结",
                "社区",
                "模块",
                "知识结构",
                "学习",
                "关联",
                "关系",
                "相关",
                "联系",
                "脉络",
            ]
        )

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[CommunitySummary]:
        if not self.summaries:
            return []

        query_tokens = set(
            self._tokens(query)
        )
        overview_query = self._is_overview_query(query)

        scored: list[CommunitySummary] = []

        for summary in self.summaries:
            entity_text = " ".join(summary.entity_names)
            relation_text = " ".join(summary.relation_types)
            type_text = " ".join(summary.entity_types)
            text = (
                f"{summary.title}\n{summary.content}\n"
                f"{entity_text}\n{relation_text}\n{type_text}"
            )
            text_tokens = set(
                self._tokens(text)
            )
            overlap = len(
                query_tokens & text_tokens
            )

            score = float(overlap)

            for entity_name in summary.entity_names:
                if entity_name and entity_name in query:
                    score += 8.0

            for relation_type in summary.relation_types:
                if relation_type and relation_type in query:
                    score += 3.0

            if overview_query:
                score += len(summary.node_ids) * 0.01

            if score <= 0:
                continue

            scored.append(
                CommunitySummary(
                    community_id=summary.community_id,
                    title=summary.title,
                    content=summary.content,
                    node_ids=summary.node_ids,
                    entity_names=summary.entity_names,
                    entity_types=summary.entity_types,
                    relation_types=summary.relation_types,
                    score=score,
                )
            )

        if not scored and self.summaries:
            scored = [
                CommunitySummary(
                    community_id=summary.community_id,
                    title=summary.title,
                    content=summary.content,
                    node_ids=summary.node_ids,
                    entity_names=summary.entity_names,
                    entity_types=summary.entity_types,
                    relation_types=summary.relation_types,
                    score=len(summary.node_ids) * 0.01,
                )
                for summary in self.summaries[:top_k]
            ]

        scored.sort(
            key=lambda item: (
                -item.score,
                item.community_id,
            )
        )

        return scored[:top_k]

    def get_stats(
        self,
    ) -> dict[str, int]:
        return {
            "community_count": len(self.summaries),
            "community_node_count": sum(
                len(summary.node_ids)
                for summary in self.summaries
            ),
        }
