"""
内存 + JSON 落盘实现。零依赖，Neo4j 装不上时直接用它，接口完全一致。
数据文件：data/store.json
"""
import json
import os
import threading
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    from .schemas import Entity, Relation
    from .store_base import GraphStore
except ImportError:
    from schemas import Entity, Relation
    from store_base import GraphStore


class MemoryStore(GraphStore):
    def __init__(self, path: str = "data/store.json"):
        self.path = path
        self._lock = threading.RLock()
        self.entities: Dict[str, Entity] = {}
        self.relations: Dict[Tuple[str, str, str], Relation] = {}
        self.users: List[dict] = []
        self.operation_logs: List[dict] = []
        self.import_batches: List[dict] = []
        self._load()

    # ---------- 持久化 ----------
    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for e in raw.get("entities", []):
            self.entities[e["id"]] = Entity(**e)
        for r in raw.get("relations", []):
            rel = Relation(**r)
            self.relations[(rel.source_id, rel.relation, rel.target_id)] = rel
        self.users = raw.get("users", [])
        self.operation_logs = raw.get("operation_logs", [])
        self.import_batches = raw.get("import_batches", [])

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "entities": [e.model_dump() for e in self.entities.values()],
                "relations": [r.model_dump() for r in self.relations.values()],
                "users": self.users,
                "operation_logs": self.operation_logs,
                "import_batches": self.import_batches,
            }, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    # ---------- 实体 ----------
    def upsert_entity(self, e: Entity) -> Entity:
        with self._lock:
            self.entities[e.id] = e
            # 名字改了，同步关系里的冗余名字
            for r in self.relations.values():
                if r.source_id == e.id:
                    r.source_name = e.name
                if r.target_id == e.id:
                    r.target_name = e.name
            self._save()
        return e

    def bulk_upsert_entities(self, entities: List[Entity]) -> int:
        with self._lock:
            for entity in entities:
                self.entities[entity.id] = entity
            self._save()
        return len(entities)

    def get_entity(self, eid: str) -> Optional[Entity]:
        return self.entities.get(eid)

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        for e in self.entities.values():
            if e.name == name:
                return e
        for e in self.entities.values():          # 再退一步匹配别名
            if e.alias and name in [a.strip() for a in e.alias.split("/")]:
                return e
        return None

    def delete_entity(self, eid: str) -> bool:
        with self._lock:
            if eid not in self.entities:
                return False
            del self.entities[eid]
            for k in [k for k in self.relations if eid in (k[0], k[2])]:
                del self.relations[k]          # 级联删除挂着的关系
            self._save()
        return True

    def list_entities(self, type_, keyword, page, size) -> Tuple[int, List[Entity]]:
        items = list(self.entities.values())
        if type_:
            items = [e for e in items if e.type == type_]
        if keyword:
            k = keyword.strip()
            items = [e for e in items if k in e.name or k in e.alias or k in e.description]
        items.sort(key=lambda e: e.id)
        return len(items), items[(page - 1) * size: page * size]

    def next_id(self, type_: str) -> str:
        from server.schemas import auto_prefix, get_type_prefixes
        known = get_type_prefixes()
        prefix = known.get(type_) or auto_prefix(type_)
        nums = [int(e.id[len(prefix):]) for e in self.entities.values()
                if e.id.startswith(prefix) and e.id[len(prefix):].isdigit()]
        return f"{prefix}{(max(nums) + 1 if nums else 1):03d}"

    # ---------- 关系 ----------
    def upsert_relation(self, r: Relation) -> Relation:
        with self._lock:
            self.relations[(r.source_id, r.relation, r.target_id)] = r
            self._save()
        return r

    def bulk_upsert_relations(self, relations: List[Relation]) -> int:
        with self._lock:
            for relation in relations:
                self.relations[(relation.source_id, relation.relation, relation.target_id)] = relation
            self._save()
        return len(relations)

    def delete_relation(self, source_id: str, relation: str, target_id: str) -> bool:
        with self._lock:
            key = (source_id, relation, target_id)
            if key not in self.relations:
                return False
            del self.relations[key]
            self._save()
        return True

    def list_relations(self, source_id, target_id, relation, page, size) -> Tuple[int, List[Relation]]:
        items = list(self.relations.values())
        if source_id:
            items = [r for r in items if r.source_id == source_id]
        if target_id:
            items = [r for r in items if r.target_id == target_id]
        if relation:
            items = [r for r in items if r.relation == relation]
        items.sort(key=lambda r: (r.source_id, r.relation, r.target_id))
        return len(items), items[(page - 1) * size: page * size]

    # ---------- 图查询 ----------
    def _incident(self, eid: str) -> List[Relation]:
        return [r for r in self.relations.values() if eid in (r.source_id, r.target_id)]

    def neighbors(self, eid, relation, limit) -> Tuple[List[Entity], List[Relation]]:
        rels = [r for r in self._incident(eid) if not relation or r.relation == relation][:limit]
        ids = {eid} | {r.source_id for r in rels} | {r.target_id for r in rels}
        return [self.entities[i] for i in ids if i in self.entities], rels

    def subgraph(self, eid, depth, limit) -> Tuple[List[Entity], List[Relation]]:
        if eid not in self.entities:
            return [], []
        seen_nodes, seen_rels = {eid}, {}
        q = deque([(eid, 0)])
        while q:
            cur, d = q.popleft()
            if d >= depth:
                continue
            for r in self._incident(cur):
                seen_rels[(r.source_id, r.relation, r.target_id)] = r
                other = r.target_id if r.source_id == cur else r.source_id
                if other not in seen_nodes and len(seen_nodes) < limit:
                    seen_nodes.add(other)
                    q.append((other, d + 1))
        rels = [r for r in seen_rels.values()
                if r.source_id in seen_nodes and r.target_id in seen_nodes]
        return [self.entities[i] for i in seen_nodes if i in self.entities], rels

    def find_paths(self, source_id, target_id, max_depth, limit=5):
        results, stack = [], [(source_id, [source_id], [])]
        while stack and len(results) < limit:
            cur, nodes, rels = stack.pop()
            if cur == target_id and len(nodes) > 1:
                results.append(
                    ([self.entities[i] for i in nodes if i in self.entities], list(rels))
                )
                continue
            if len(nodes) - 1 >= max_depth:
                continue
            for r in self._incident(cur):
                other = r.target_id if r.source_id == cur else r.source_id
                if other in nodes:
                    continue
                stack.append((other, nodes + [other], rels + [r]))
        return results

    def clear(self) -> None:
        with self._lock:
            self.entities.clear()
            self.relations.clear()
            self._save()

    def stats(self) -> dict:
        by_type: Dict[str, int] = {}
        for e in self.entities.values():
            by_type[e.type] = by_type.get(e.type, 0) + 1
        by_rel: Dict[str, int] = {}
        for r in self.relations.values():
            by_rel[r.relation] = by_rel.get(r.relation, 0) + 1
        return {"entity_count": len(self.entities), "relation_count": len(self.relations),
                "entity_by_type": by_type, "relation_by_type": by_rel}

    # ---------- 用户、审计与导入批次 ----------
    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _next_record_id(records: List[dict]) -> int:
        return max((int(item.get("id", 0)) for item in records), default=0) + 1

    def create_user(self, username: str, password_hash: str, role: str = "user") -> int:
        with self._lock:
            uid = self._next_record_id(self.users)
            self.users.append({"id": uid, "username": username, "password_hash": password_hash,
                               "role": role, "is_active": 1, "created_at": self._now(),
                               "last_login": None})
            self._save()
            return uid

    def get_user_by_username(self, username: str) -> Optional[dict]:
        return next((dict(u) for u in self.users
                     if u.get("username") == username and u.get("is_active", 1)), None)

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        return next((dict(u) for u in self.users if int(u.get("id", 0)) == user_id), None)

    def update_last_login(self, user_id: int) -> None:
        with self._lock:
            for user in self.users:
                if int(user.get("id", 0)) == user_id:
                    user["last_login"] = self._now()
                    self._save()
                    return

    def list_users(self) -> List[dict]:
        return [{k: v for k, v in user.items() if k != "password_hash"}
                for user in sorted(self.users, key=lambda item: int(item.get("id", 0)))]

    def change_password(self, user_id: int, password_hash: str) -> bool:
        with self._lock:
            for user in self.users:
                if int(user.get("id", 0)) == user_id:
                    user["password_hash"] = password_hash
                    self._save()
                    return True
        return False

    def insert_operation_log(self, user_id: int = 0, username: str = "", action: str = "",
                             target_type: str = "", target_id: str = "", target_name: str = "",
                             before_snapshot: dict | None = None,
                             after_snapshot: dict | None = None, ip_address: str = "") -> int:
        with self._lock:
            log_id = self._next_record_id(self.operation_logs)
            self.operation_logs.append({"id": log_id, "user_id": user_id, "username": username,
                "action": action, "target_type": target_type, "target_id": target_id,
                "target_name": target_name, "before_snapshot": before_snapshot,
                "after_snapshot": after_snapshot, "ip_address": ip_address,
                "created_at": self._now()})
            self._save()
            return log_id

    def list_operation_log(self, user_id: int | None = None, action: str | None = None,
                           target_type: str | None = None, target_id: str | None = None,
                           page: int = 1, size: int = 20) -> Tuple[int, List[dict]]:
        items = list(self.operation_logs)
        if user_id is not None:
            items = [item for item in items if int(item.get("user_id", 0)) == user_id]
        if action:
            items = [item for item in items if item.get("action") == action]
        if target_type:
            items = [item for item in items if item.get("target_type") == target_type]
        if target_id:
            items = [item for item in items if item.get("target_id") == target_id]
        items.sort(key=lambda item: (item.get("created_at", ""), item.get("id", 0)), reverse=True)
        return len(items), [dict(item) for item in items[(page - 1) * size:page * size]]

    def get_operation_log(self, log_id: int) -> Optional[dict]:
        return next((dict(item) for item in self.operation_logs
                     if int(item.get("id", 0)) == log_id), None)

    def insert_import_batch(self, user_id: int = 0, username: str = "",
                            kind: str = "entity", file_name: str = "", total: int = 0,
                            success: int = 0, failed: int = 0,
                            errors: list | None = None) -> int:
        with self._lock:
            batch_id = self._next_record_id(self.import_batches)
            self.import_batches.append({"id": batch_id, "user_id": user_id,
                "username": username, "kind": kind, "file_name": file_name,
                "total": total, "success": success, "failed": failed,
                "errors_json": errors or [], "created_at": self._now()})
            self._save()
            return batch_id

    def list_import_batches(self, page: int = 1, size: int = 20) -> Tuple[int, List[dict]]:
        items = sorted(self.import_batches,
                       key=lambda item: (item.get("created_at", ""), item.get("id", 0)),
                       reverse=True)
        return len(items), [dict(item) for item in items[(page - 1) * size:page * size]]
