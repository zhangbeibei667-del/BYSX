from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from app.schemas import (
    EntityRecord,
    RelationRecord,
    GraphData,
    GraphNode,
    GraphEdge,
)


class GraphSearch:
    """
    图谱检索模块。

    当前阶段：
    - 从 entities.json 读取实体；
    - 从 relations.json 读取关系；
    - 根据用户问题识别实体；
    - 从命中实体出发进行 1~N 跳 BFS 路径搜索。

    后续和成员 2 对接时，可把这里的数据读取部分替换成 HTTP / Neo4j 接口，
    但外部返回的 GraphData 格式保持不变。
    """

    def __init__(self, entities_path: Path, relations_path: Path) -> None:
        self.entities = self._load_entities(entities_path)
        self.relations = self._load_relations(relations_path)
        self.entity_by_id = {entity.id: entity for entity in self.entities}

    @staticmethod
    def _load_entities(path: Path) -> list[EntityRecord]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [EntityRecord.model_validate(item) for item in raw]

    @staticmethod
    def _load_relations(path: Path) -> list[RelationRecord]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [RelationRecord.model_validate(item) for item in raw]

    def extract_entities(self, query: str) -> list[EntityRecord]:
        """
        开发期轻量实体识别：
        - 标准名出现在问题中 -> 命中；
        - alias 出现在问题中 -> 命中。

        暂时不用 LLM，保证没有 API Key 也能稳定运行。
        """
        q = query.strip().lower()
        matched: list[EntityRecord] = []

        for entity in self.entities:
            candidates = [entity.name, entity.alias]
            if any(name and name.lower() in q for name in candidates):
                matched.append(entity)

        # 长实体名优先，减少短词抢匹配
        matched.sort(key=lambda x: len(x.name), reverse=True)
        return matched

    def search_paths(
        self,
        seed_entities: list[EntityRecord],
        max_hops: int = 2,
    ) -> GraphData:
        """从命中的实体出发搜索 1~N 跳关系，并转为统一 nodes / edges 格式。"""

        if not seed_entities:
            return GraphData()

        # 建立单向邻接表，只沿知识图谱原始关系方向向前搜索
        adjacency: dict[str, list[tuple[str, int]]] = {}

        for idx, rel in enumerate(self.relations):
            # 只按照知识图谱中定义的原始方向向前搜索
            adjacency.setdefault(rel.source_id, []).append(
                (rel.target_id, idx)
            )
        queue: deque[tuple[str, int]] = deque()
        visited_depth: dict[str, int] = {}

        for entity in seed_entities:
            queue.append((entity.id, 0))
            visited_depth[entity.id] = 0

        selected_relation_indexes: set[int] = set()

        while queue:
            current_id, depth = queue.popleft()

            if depth >= max_hops:
                continue

            for next_id, relation_index in adjacency.get(current_id, []):
                selected_relation_indexes.add(relation_index)
                next_depth = depth + 1

                old_depth = visited_depth.get(next_id)
                if old_depth is None or next_depth < old_depth:
                    visited_depth[next_id] = next_depth
                    queue.append((next_id, next_depth))

        node_map: dict[str, GraphNode] = {}
        edge_map: dict[tuple[str, str, str], GraphEdge] = {}

        # 即使种子实体没有关系，也返回节点
        for entity in seed_entities:
            node_map[entity.id] = GraphNode(
                id=entity.id,
                label=entity.name,
                type=entity.type,
            )

        for idx in sorted(selected_relation_indexes):
            rel = self.relations[idx]

            source = self.entity_by_id.get(rel.source_id)
            target = self.entity_by_id.get(rel.target_id)

            # 脏关系数据不让接口崩溃
            if source is None or target is None:
                continue

            node_map[source.id] = GraphNode(
                id=source.id,
                label=source.name,
                type=source.type,
            )
            node_map[target.id] = GraphNode(
                id=target.id,
                label=target.name,
                type=target.type,
            )

            key = (rel.source_id, rel.target_id, rel.relation)
            edge_map[key] = GraphEdge(
                source=rel.source_id,
                target=rel.target_id,
                label=rel.relation,
            )

        return GraphData(
            nodes=list(node_map.values()),
            edges=list(edge_map.values()),
        )
