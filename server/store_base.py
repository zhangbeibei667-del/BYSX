"""存储层接口。上层 service 只依赖这个接口，换 Neo4j / 内存实现互不影响。"""
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

try:
    from .schemas import Entity, Relation
except ImportError:
    from schemas import Entity, Relation


class GraphStore(ABC):
    # --- 实体 ---
    @abstractmethod
    def upsert_entity(self, e: Entity) -> Entity: ...

    @abstractmethod
    def get_entity(self, eid: str) -> Optional[Entity]: ...

    @abstractmethod
    def get_entity_by_name(self, name: str) -> Optional[Entity]: ...

    @abstractmethod
    def delete_entity(self, eid: str) -> bool: ...

    @abstractmethod
    def list_entities(self, type_: Optional[str], keyword: Optional[str],
                      page: int, size: int) -> Tuple[int, List[Entity]]: ...

    @abstractmethod
    def next_id(self, type_: str) -> str: ...

    # --- 关系 ---
    @abstractmethod
    def upsert_relation(self, r: Relation) -> Relation: ...

    @abstractmethod
    def delete_relation(self, source_id: str, relation: str, target_id: str) -> bool: ...

    @abstractmethod
    def list_relations(self, source_id: Optional[str], target_id: Optional[str],
                       relation: Optional[str], page: int, size: int) -> Tuple[int, List[Relation]]: ...

    # --- 图查询：统一返回 (实体集, 关系集)，由 service 转成 {nodes, edges} ---
    @abstractmethod
    def neighbors(self, eid: str, relation: Optional[str], limit: int) -> Tuple[List[Entity], List[Relation]]: ...

    @abstractmethod
    def subgraph(self, eid: str, depth: int, limit: int) -> Tuple[List[Entity], List[Relation]]: ...

    @abstractmethod
    def find_paths(self, source_id: str, target_id: str, max_depth: int,
                   limit: int) -> List[Tuple[List[Entity], List[Relation]]]: ...

    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def stats(self) -> dict: ...
