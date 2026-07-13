"""
混合存储：MySQL（实体检索 + 关系查询 + 审计）+ Neo4j（图遍历）。
所有增删改在两阶段提交内执行：两边同时成功或同时回滚，保证一致性。

USAGE:
    export STORE_BACKEND=hybrid    # 默认
    export MYSQL_PASSWORD=xxx
    export NEO4J_PASSWORD=yyy
"""
from contextlib import contextmanager
from typing import List, Optional, Tuple

try:
    from .store_base import GraphStore
    from .schemas import Entity, Relation
except ImportError:
    from store_base import GraphStore
    from schemas import Entity, Relation


class HybridStore(GraphStore):
    """双写存储：写操作使用两阶段提交（先 MySQL 后 Neo4j，失败全回滚）。

    读操作：
      - 实体检索 → MySQL（索引 + 分页更高效）
      - 图查询   → Neo4j（原生图遍历最优）
      - 审计/用户 → MySQL
    """

    def __init__(self, mysql_store: GraphStore, neo4j_store: GraphStore):
        self.mysql = mysql_store
        self.neo4j = neo4j_store

    @contextmanager
    def _write_transaction(self):
        """两阶段提交上下文。任一环节失败则两边都回滚。
        提交成功后自动同步 kg.sqlite 供组员 SQL Agent 查询。"""
        self.mysql.begin()
        self.neo4j.begin_write_transaction()
        try:
            yield
            self.mysql.commit()
            self.neo4j.commit_write_transaction()
            # 自动同步 SQLite
            try:
                self.mysql.sync_to_sqlite()
            except Exception:
                pass  # 同步失败不影响主流程
        except Exception:
            self.mysql.rollback()
            self.neo4j.rollback_write_transaction()
            raise

    # ========== 实体（双写） ==========
    def upsert_entity(self, e: Entity) -> Entity:
        with self._write_transaction():
            self.mysql.upsert_entity(e)
            self.neo4j.upsert_entity(e)
        return e

    def get_entity(self, eid: str) -> Optional[Entity]:
        return self.mysql.get_entity(eid)

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        return self.mysql.get_entity_by_name(name)

    def delete_entity(self, eid: str) -> bool:
        with self._write_transaction():
            a = self.mysql.delete_entity(eid)
            b = self.neo4j.delete_entity(eid)
        return a or b

    def list_entities(self, type_, keyword, page, size) -> Tuple[int, List[Entity]]:
        return self.mysql.list_entities(type_, keyword, page, size)

    def next_id(self, type_: str) -> str:
        return self.mysql.next_id(type_)

    # ========== 关系（双写） ==========
    def upsert_relation(self, r: Relation) -> Relation:
        with self._write_transaction():
            self.mysql.upsert_relation(r)
            self.neo4j.upsert_relation(r)
        return r

    def delete_relation(self, source_id, relation, target_id) -> bool:
        with self._write_transaction():
            a = self.mysql.delete_relation(source_id, relation, target_id)
            b = self.neo4j.delete_relation(source_id, relation, target_id)
        return a or b

    def list_relations(self, source_id, target_id, relation, page, size):
        return self.mysql.list_relations(source_id, target_id, relation, page, size)

    # ========== 图查询 → Neo4j（最优路径） ==========
    def neighbors(self, eid, relation, limit) -> Tuple[List[Entity], List[Relation]]:
        return self.neo4j.neighbors(eid, relation, limit)

    def subgraph(self, eid, depth, limit) -> Tuple[List[Entity], List[Relation]]:
        return self.neo4j.subgraph(eid, depth, limit)

    def find_paths(self, source_id, target_id, max_depth, limit=5):
        return self.neo4j.find_paths(source_id, target_id, max_depth, limit)

    # ========== 管理 ==========
    def clear(self) -> None:
        with self._write_transaction():
            self.mysql.clear()
            self.neo4j.clear()

    def stats(self) -> dict:
        return self.mysql.stats()

    # ========== 审计 & 用户（仅 MySQL） ==========
    def insert_operation_log(self, user_id=0, username="", action="",
                              target_type="", target_id="", target_name="",
                              before_snapshot=None, after_snapshot=None,
                              ip_address=""):
        return self.mysql.insert_operation_log(
            user_id=user_id, username=username, action=action,
            target_type=target_type, target_id=target_id, target_name=target_name,
            before_snapshot=before_snapshot, after_snapshot=after_snapshot,
            ip_address=ip_address,
        )

    def list_operation_log(self, user_id=None, action=None, target_type=None,
                            target_id=None, page=1, size=20):
        return self.mysql.list_operation_log(
            user_id=user_id, action=action, target_type=target_type,
            target_id=target_id, page=page, size=size,
        )

    def get_operation_log(self, log_id: int):
        return self.mysql.get_operation_log(log_id)

    def insert_import_batch(self, user_id=0, username="", kind="entity",
                             file_name="", total=0, success=0, failed=0,
                             errors=None):
        return self.mysql.insert_import_batch(
            user_id=user_id, username=username, kind=kind, file_name=file_name,
            total=total, success=success, failed=failed, errors=errors,
        )

    def list_import_batches(self, page=1, size=20):
        return self.mysql.list_import_batches(page=page, size=size)

    def create_user(self, username, password_hash, role="viewer"):
        return self.mysql.create_user(username, password_hash, role)

    def get_user_by_username(self, username):
        return self.mysql.get_user_by_username(username)

    def get_user_by_id(self, user_id):
        return self.mysql.get_user_by_id(user_id)

    def update_last_login(self, user_id):
        return self.mysql.update_last_login(user_id)

    def list_users(self):
        return self.mysql.list_users()

    def change_password(self, user_id, password_hash):
        return self.mysql.change_password(user_id, password_hash)

    # ========== 类型前缀 ==========
    def list_type_prefixes(self):
        return self.mysql.list_type_prefixes()

    # ========== SQL 只读查询（供 SQL Agent） ==========
    def execute_readonly_sql(self, sql, params=None, max_rows=200):
        return self.mysql.execute_readonly_sql(sql, params, max_rows)
