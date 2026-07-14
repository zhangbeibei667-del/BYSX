"""
内存 + JSON 落盘实现。零依赖，Neo4j 装不上时直接用它，接口完全一致。
数据文件：data/store.json
"""
import json
import os
import threading
from collections import deque
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

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "entities": [e.model_dump() for e in self.entities.values()],
                "relations": [r.model_dump() for r in self.relations.values()],
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
