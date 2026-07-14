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

    # --- 批量导入（子类应在单事务内实现，避免逐条提交） ---
    def bulk_upsert_entities(self, entities: List[Entity]) -> int:
        """批量写入实体，返回成功数。默认逐条 upsert。"""
        count = 0
        for e in entities:
            try:
                self.upsert_entity(e)
                count += 1
            except Exception:
                pass
        return count

    def bulk_upsert_relations(self, relations: List[Relation]) -> int:
        """批量写入关系，返回成功数。默认逐条 upsert。"""
        count = 0
        for r in relations:
            try:
                self.upsert_relation(r)
                count += 1
            except Exception:
                pass
        return count

    # --- 关系 ---
    @abstractmethod
    def upsert_relation(self, r: Relation) -> Relation: ...

    @abstractmethod
    def delete_relation(self, source_id: str, relation: str, target_id: str) -> bool: ...

    def replace_relation(self, old_source: str, old_relation: str, old_target: str,
                         new_relation: Relation) -> Relation:
        """原子替换关系。默认：删旧 + 建新（子类可在单事务中覆写）。"""
        self.delete_relation(old_source, old_relation, old_target)
        return self.upsert_relation(new_relation)

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
