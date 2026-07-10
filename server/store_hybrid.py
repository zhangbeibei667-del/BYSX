"""
混合存储：写操作同时写入 MySQL + Neo4j，读操作 Neo4j 负责图查询，MySQL 负责实体检索。
两个库始终保持同步，改一处另一处自动更新。
"""
from typing import List, Optional, Tuple

try:
    from .store_base import GraphStore
    from .schemas import Entity, Relation
except ImportError:
    from store_base import GraphStore
    from schemas import Entity, Relation


class HybridStore(GraphStore):
    """双写存储：所有增删改同步到两个后端。

    USAGE:
        export STORE_BACKEND=hybrid
        export MYSQL_PASSWORD=xxx
        export NEO4J_PASSWORD=yyy
    """

    def __init__(self, mysql_store: GraphStore, neo4j_store: GraphStore):
        self.mysql = mysql_store
        self.neo4j = neo4j_store

    # ========== 实体 → 双写 ==========
    def upsert_entity(self, e: Entity) -> Entity:
        self.mysql.upsert_entity(e)
        self.neo4j.upsert_entity(e)
        return e

    def get_entity(self, eid: str) -> Optional[Entity]:
        return self.mysql.get_entity(eid)

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        return self.mysql.get_entity_by_name(name)

    def delete_entity(self, eid: str) -> bool:
        a = self.mysql.delete_entity(eid)
        b = self.neo4j.delete_entity(eid)
        return a or b

    def list_entities(self, type_, keyword, page, size) -> Tuple[int, List[Entity]]:
        return self.mysql.list_entities(type_, keyword, page, size)

    def next_id(self, type_: str) -> str:
        return self.mysql.next_id(type_)

    # ========== 关系 → 双写 ==========
    def upsert_relation(self, r: Relation) -> Relation:
        self.mysql.upsert_relation(r)
        self.neo4j.upsert_relation(r)
        return r

    def delete_relation(self, source_id, relation, target_id) -> bool:
        a = self.mysql.delete_relation(source_id, relation, target_id)
        b = self.neo4j.delete_relation(source_id, relation, target_id)
        return a or b

    def list_relations(self, source_id, target_id, relation, page, size):
        return self.mysql.list_relations(source_id, target_id, relation, page, size)

    # ========== 图查询 → Neo4j（图数据库专长）==========
    def neighbors(self, eid, relation, limit) -> Tuple[List[Entity], List[Relation]]:
        return self.neo4j.neighbors(eid, relation, limit)

    def subgraph(self, eid, depth, limit) -> Tuple[List[Entity], List[Relation]]:
        return self.neo4j.subgraph(eid, depth, limit)

    def find_paths(self, source_id, target_id, max_depth, limit=5):
        return self.neo4j.find_paths(source_id, target_id, max_depth, limit)

    # ========== 管理 ==========
    def clear(self) -> None:
        self.mysql.clear()
        self.neo4j.clear()

    def stats(self) -> dict:
        return self.mysql.stats()
