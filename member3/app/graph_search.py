from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas import (
    EntityRecord,
    RelationRecord,
    GraphData,
    GraphNode,
    GraphEdge,
)


class GraphSearch:
    """
    TCM GraphRAG 图谱检索模块。

    当前支持两种数据组织方式：

    1. 单文件模式
       entities.json
       relations.json

    2. 多文件目录模式
       entities/
           entities_syndromes.json
           entities_symptoms.json
           entities_formulas.json
           ...

       relations/
           relations_syndrome_symptom.json
           relations_syndrome_formula.json
           relations_formula_herb.json
           ...

    搜索流程：
    1. 加载并合并实体；
    2. 加载并合并关系；
    3. 自动去重；
    4. 从 Query 中识别实体；
    5. 从种子实体出发进行单向 1~N 跳 BFS；
    6. 返回统一 GraphData(nodes, edges)。

    后续与成员 2 的图数据库 / HTTP API 对接时，
    可以替换数据加载层，但保持：
        extract_entities()
        search_paths()
        GraphData
    这些外部接口不变。
    """

    def __init__(
        self,
        entities_path: Path,
        relations_path: Path,
    ) -> None:
        """
        参数既可以是文件，也可以是目录。

        单文件：
            entities_path = data/entities.json
            relations_path = data/relations.json

        多文件目录：
            entities_path = data/graph/entities/
            relations_path = data/graph/relations/
        """
        self.entities_path = Path(entities_path)
        self.relations_path = Path(relations_path)

        # 加载实体和关系
        self.entities = self._load_entities(
            self.entities_path
        )

        self.relations = self._load_relations(
            self.relations_path
        )

        # 实体 ID -> EntityRecord
        self.entity_by_id: dict[str, EntityRecord] = {
            entity.id: entity
            for entity in self.entities
        }

        # 名称索引。
        # 当前主要用于后续扩展和调试，
        # 不改变已有 extract_entities() 行为。
        self.entities_by_name: dict[
            str,
            list[EntityRecord],
        ] = {}

        for entity in self.entities:
            self.entities_by_name.setdefault(
                entity.name.lower(),
                [],
            ).append(entity)

        # 预构建单向邻接表。
        # 后续每次 search_paths() 不需要重复扫描全部关系。
        self._adjacency = self._build_adjacency()

    # ========================================================
    # 1. 文件发现
    # ========================================================
    @staticmethod
    def _discover_json_files(
        source: Path,
    ) -> list[Path]:
        """
        接收：
        - 单个 .json 文件
        - 包含多个 .json 的目录

        返回稳定排序后的 JSON 文件列表。
        """
        if not source.exists():
            raise FileNotFoundError(
                f"图谱数据路径不存在: {source}"
            )

        # 单文件
        if source.is_file():
            if source.suffix.lower() != ".json":
                raise ValueError(
                    "图谱数据文件必须是 JSON: "
                    f"{source}"
                )

            return [source]

        # 目录
        if source.is_dir():
            files = sorted(
                (
                    path
                    for path in source.rglob("*.json")
                    if path.is_file()
                ),
                key=lambda path: str(path).lower(),
            )

            if not files:
                raise FileNotFoundError(
                    "目录中未找到 JSON 文件: "
                    f"{source}"
                )

            return files

        raise ValueError(
            f"无法识别图谱数据路径: {source}"
        )

    # ========================================================
    # 2. JSON 读取
    # ========================================================
    @staticmethod
    def _read_json_file(
        path: Path,
    ) -> Any:
        """
        读取单个 JSON 文件，
        提供更明确的错误位置。
        """
        try:
            text = path.read_text(
                encoding="utf-8-sig"
            )

            return json.loads(text)

        except json.JSONDecodeError as exc:
            raise ValueError(
                "JSON 解析失败: "
                f"{path}\n"
                f"第 {exc.lineno} 行，"
                f"第 {exc.colno} 列："
                f"{exc.msg}"
            ) from exc

        except OSError as exc:
            raise OSError(
                f"读取 JSON 文件失败: {path}"
            ) from exc

    # ========================================================
    # 3. 解包实体 JSON
    # ========================================================
    @staticmethod
    def _unwrap_entity_items(
        raw: Any,
        path: Path,
    ) -> list[dict]:
        """
        支持：

        形式 A：
        [
            {...},
            {...}
        ]

        形式 B：
        {
            "entities": [
                {...},
                {...}
            ]
        }
        """
        if isinstance(raw, list):
            items = raw

        elif isinstance(raw, dict):
            entities = raw.get("entities")

            if not isinstance(entities, list):
                raise ValueError(
                    "实体 JSON 顶层必须是数组，"
                    "或包含 entities 数组字段: "
                    f"{path}"
                )

            items = entities

        else:
            raise ValueError(
                "实体 JSON 顶层格式错误: "
                f"{path}"
            )

        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(
                    "实体记录必须是 JSON 对象: "
                    f"{path}，索引 {index}"
                )

        return items

    # ========================================================
    # 4. 解包关系 JSON
    # ========================================================
    @staticmethod
    def _unwrap_relation_items(
        raw: Any,
        path: Path,
    ) -> list[dict]:
        """
        支持：

        形式 A：
        [
            {...},
            {...}
        ]

        形式 B：
        {
            "relations": [
                {...},
                {...}
            ]
        }
        """
        if isinstance(raw, list):
            items = raw

        elif isinstance(raw, dict):
            relations = raw.get("relations")

            if not isinstance(relations, list):
                raise ValueError(
                    "关系 JSON 顶层必须是数组，"
                    "或包含 relations 数组字段: "
                    f"{path}"
                )

            items = relations

        else:
            raise ValueError(
                "关系 JSON 顶层格式错误: "
                f"{path}"
            )

        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(
                    "关系记录必须是 JSON 对象: "
                    f"{path}，索引 {index}"
                )

        return items

    # ========================================================
    # 5. 加载多个实体文件 + 自动去重
    # ========================================================
    @classmethod
    def _load_entities(
        cls,
        source: Path,
    ) -> list[EntityRecord]:
        """
        加载单个实体文件或实体目录。

        去重规则：
        - entity.id 相同视为同一实体；
        - 首次加载的数据保留；
        - 后续重复 ID 不重复加入。

        文件按路径名称排序，因此结果稳定可复现。
        """
        files = cls._discover_json_files(
            source
        )

        entity_map: dict[
            str,
            EntityRecord,
        ] = {}

        for path in files:
            raw = cls._read_json_file(path)

            items = cls._unwrap_entity_items(
                raw=raw,
                path=path,
            )

            for index, item in enumerate(items):
                try:
                    entity = (
                        EntityRecord.model_validate(
                            item
                        )
                    )

                except ValidationError as exc:
                    raise ValueError(
                        "实体数据校验失败:\n"
                        f"文件: {path}\n"
                        f"索引: {index}\n"
                        f"数据: {item}\n"
                        f"错误: {exc}"
                    ) from exc

                # 按 ID 去重。
                # 首次出现的实体保留。
                if entity.id not in entity_map:
                    entity_map[entity.id] = entity

        return list(entity_map.values())

    # ========================================================
    # 6. 加载多个关系文件 + 自动去重
    # ========================================================
    @classmethod
    def _load_relations(
        cls,
        source: Path,
    ) -> list[RelationRecord]:
        """
        加载单个关系文件或关系目录。

        去重键：
        (
            source_id,
            target_id,
            relation
        )

        相同三元组只保留一次。
        """
        files = cls._discover_json_files(
            source
        )

        relation_map: dict[
            tuple[str, str, str],
            RelationRecord,
        ] = {}

        for path in files:
            raw = cls._read_json_file(path)

            items = cls._unwrap_relation_items(
                raw=raw,
                path=path,
            )

            for index, item in enumerate(items):
                try:
                    relation = (
                        RelationRecord.model_validate(
                            item
                        )
                    )

                except ValidationError as exc:
                    raise ValueError(
                        "关系数据校验失败:\n"
                        f"文件: {path}\n"
                        f"索引: {index}\n"
                        f"数据: {item}\n"
                        f"错误: {exc}"
                    ) from exc

                key = (
                    relation.source_id,
                    relation.target_id,
                    relation.relation,
                )

                # 相同三元组只保留第一次
                if key not in relation_map:
                    relation_map[key] = relation

        return list(relation_map.values())

    # ========================================================
    # 7. 构建单向邻接表
    # ========================================================
    def _build_adjacency(
        self,
    ) -> dict[
        str,
        list[tuple[str, int]],
    ]:
        """
        只按照图谱原始方向构建邻接表。

        source_id
            ↓
        target_id

        不自动建立：
        target_id
            ↓
        source_id

        保留当前已经验证过的单向 BFS 设计。
        """
        adjacency: dict[
            str,
            list[tuple[str, int]],
        ] = {}

        for index, relation in enumerate(
            self.relations
        ):
            adjacency.setdefault(
                relation.source_id,
                [],
            ).append(
                (
                    relation.target_id,
                    index,
                )
            )

        return adjacency

    # ========================================================
    # 8. Query 实体识别
    # ========================================================
    def extract_entities(
        self,
        query: str,
    ) -> list[EntityRecord]:
        """
        当前开发期轻量实体识别：

        - 标准名出现在 Query 中 -> 命中；
        - alias 出现在 Query 中 -> 命中；
        - 同一实体只返回一次；
        - 长实体名优先。

        示例：
            Query:
            风寒袭肺证有哪些症状？

            如果图谱存在：
            风寒袭肺证

            则命中该实体。

        暂时不依赖 LLM，
        保证没有额外 API 调用也能稳定运行。
        """
        query_text = query.strip().lower()

        if not query_text:
            return []

        matched_map: dict[
            str,
            EntityRecord,
        ] = {}

        for entity in self.entities:
            candidates = [
                entity.name,
                entity.alias,
            ]

            matched = any(
                candidate
                and candidate.strip()
                and candidate.lower()
                in query_text
                for candidate in candidates
            )

            if matched:
                matched_map[entity.id] = entity

        matched = list(
            matched_map.values()
        )

        # 长实体名优先。
        # 同长度时按名称排序，
        # 保证结果稳定。
        matched.sort(
            key=lambda entity: (
                -len(entity.name),
                entity.name,
            )
        )

        return matched

    # ========================================================
    # 9. BFS 图路径搜索
    # ========================================================
    def search_paths(
        self,
        seed_entities: list[EntityRecord],
        max_hops: int = 2,
    ) -> GraphData:
        """
        从命中实体出发，
        沿原始关系方向进行 1~N 跳 BFS。

        设计原则：
        - 单向；
        - 动态 max_hops；
        - 不写死 allowed_relations；
        - 不限制某类关系；
        - 保留完整正向候选子图。
        """
        if not seed_entities:
            return GraphData()

        if max_hops < 0:
            raise ValueError(
                "max_hops 不能小于 0"
            )

        queue: deque[
            tuple[str, int]
        ] = deque()

        visited_depth: dict[
            str,
            int,
        ] = {}

        # 初始化种子实体
        for entity in seed_entities:
            queue.append(
                (
                    entity.id,
                    0,
                )
            )

            visited_depth[entity.id] = 0

        selected_relation_indexes: set[
            int
        ] = set()

        # ----------------------------------------------------
        # 单向 BFS
        # ----------------------------------------------------
        while queue:
            current_id, depth = (
                queue.popleft()
            )

            if depth >= max_hops:
                continue

            for (
                next_id,
                relation_index,
            ) in self._adjacency.get(
                current_id,
                [],
            ):
                selected_relation_indexes.add(
                    relation_index
                )

                next_depth = depth + 1

                old_depth = visited_depth.get(
                    next_id
                )

                if (
                    old_depth is None
                    or next_depth < old_depth
                ):
                    visited_depth[
                        next_id
                    ] = next_depth

                    queue.append(
                        (
                            next_id,
                            next_depth,
                        )
                    )

        # ----------------------------------------------------
        # GraphData 去重容器
        # ----------------------------------------------------
        node_map: dict[
            str,
            GraphNode,
        ] = {}

        edge_map: dict[
            tuple[str, str, str],
            GraphEdge,
        ] = {}

        # ----------------------------------------------------
        # 即使种子实体没有出边，
        # 也返回种子节点。
        # ----------------------------------------------------
        for entity in seed_entities:
            node_map[entity.id] = GraphNode(
                id=entity.id,
                label=entity.name,
                type=entity.type,
            )

        # ----------------------------------------------------
        # 关系 -> nodes / edges
        # ----------------------------------------------------
        for relation_index in sorted(
            selected_relation_indexes
        ):
            relation = self.relations[
                relation_index
            ]

            source = self.entity_by_id.get(
                relation.source_id
            )

            target = self.entity_by_id.get(
                relation.target_id
            )

            # 脏关系：
            # source / target 实体不存在时，
            # 不让整个 GraphRAG 接口崩溃。
            if (
                source is None
                or target is None
            ):
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

            edge_key = (
                relation.source_id,
                relation.target_id,
                relation.relation,
            )

            edge_map[edge_key] = GraphEdge(
                source=relation.source_id,
                target=relation.target_id,
                label=relation.relation,
            )

        return GraphData(
            nodes=list(
                node_map.values()
            ),
            edges=list(
                edge_map.values()
            ),
        )

    # ========================================================
    # 10. 调试信息
    # ========================================================
    def get_stats(
        self,
    ) -> dict[str, int]:
        """
        返回当前图谱加载统计。

        后续可用于：
        - health API
        - 页面调试
        - 团队数据整合检查
        """
        valid_relation_count = 0
        dangling_relation_count = 0

        for relation in self.relations:
            source_exists = (
                relation.source_id
                in self.entity_by_id
            )

            target_exists = (
                relation.target_id
                in self.entity_by_id
            )

            if (
                source_exists
                and target_exists
            ):
                valid_relation_count += 1
            else:
                dangling_relation_count += 1

        return {
            "entity_count": len(
                self.entities
            ),
            "relation_count": len(
                self.relations
            ),
            "valid_relation_count": (
                valid_relation_count
            ),
            "dangling_relation_count": (
                dangling_relation_count
            ),
        }