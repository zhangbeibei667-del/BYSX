"""
业务层：所有校验、ID 分配、批量导入、以及「图 3 格式」的转换都在这里。
API 层只负责收发 HTTP，不写业务逻辑。
"""
import csv
import io
from typing import Any, Dict, List, Optional, Tuple

try:
    from .schemas import (Entity, EntityCreate, EntityUpdate, GraphData, GraphEdge,
                           GraphNode, ImportError_, ImportResult, Relation,
                           RelationCreate, validate_entity_type, validate_relation)
    from .store_base import GraphStore
except ImportError:
    from schemas import (Entity, EntityCreate, EntityUpdate, GraphData, GraphEdge,
                          GraphNode, ImportError_, ImportResult, Relation,
                          RelationCreate, validate_entity_type, validate_relation)
    from store_base import GraphStore

RESERVED_ENTITY_COLS = {"id", "name", "type", "alias", "description"}
RELATION_COLS = ["source_id", "source_name", "relation", "target_id", "target_name", "evidence"]


class GraphService:
    def __init__(self, store: GraphStore):
        self.store = store

    # ==================== 实体 ====================
    def create_entity(self, payload: EntityCreate) -> Entity:
        validate_entity_type(payload.type)
        if not payload.name.strip():
            raise ValueError("name 不能为空")
        exist = self.store.get_entity_by_name(payload.name)
        if exist and exist.type == payload.type:
            raise ValueError(f"同名同类型实体已存在：{exist.id} {exist.name}")
        eid = payload.id or self.store.next_id(payload.type)
        if payload.id and self.store.get_entity(payload.id):
            raise ValueError(f"id 已存在：{payload.id}")
        e = Entity(id=eid, name=payload.name.strip(), type=payload.type,
                   alias=payload.alias, description=payload.description,
                   properties=payload.properties)
        return self.store.upsert_entity(e)

    def update_entity(self, eid: str, payload: EntityUpdate) -> Entity:
        e = self.store.get_entity(eid)
        if not e:
            raise ValueError(f"实体不存在：{eid}")
        data = payload.model_dump(exclude_none=True)
        for k, v in data.items():
            setattr(e, k, v)
        return self.store.upsert_entity(e)

    def delete_entity(self, eid: str) -> bool:
        return self.store.delete_entity(eid)

    def get_entity(self, eid: str) -> Optional[Entity]:
        return self.store.get_entity(eid)

    def list_entities(self, type_=None, keyword=None, page=1, size=20):
        if type_:
            validate_entity_type(type_)
        return self.store.list_entities(type_, keyword, page, size)

    # ==================== 关系 ====================
    def _resolve(self, eid: Optional[str], name: Optional[str], role: str) -> Entity:
        e = self.store.get_entity(eid) if eid else (
            self.store.get_entity_by_name(name) if name else None)
        if not e:
            raise ValueError(f"{role} 实体不存在：id={eid} name={name}")
        return e

    def create_relation(self, payload: RelationCreate) -> Relation:
        src = self._resolve(payload.source_id, payload.source_name, "source")
        tgt = self._resolve(payload.target_id, payload.target_name, "target")
        if src.id == tgt.id:
            raise ValueError("不允许自环关系")
        validate_relation(payload.relation, src.type, tgt.type)
        r = Relation(source_id=src.id, source_name=src.name, relation=payload.relation,
                     target_id=tgt.id, target_name=tgt.name, evidence=payload.evidence)
        return self.store.upsert_relation(r)

    def delete_relation(self, source_id: str, relation: str, target_id: str) -> bool:
        return self.store.delete_relation(source_id, relation, target_id)

    def list_relations(self, source_id=None, target_id=None, relation=None, page=1, size=20):
        return self.store.list_relations(source_id, target_id, relation, page, size)

    # ==================== 图 3 格式转换 ====================
    @staticmethod
    def to_graph(entities: List[Entity], relations: List[Relation]) -> GraphData:
        node_ids = {e.id for e in entities}
        nodes = [GraphNode(id=e.id, label=e.name, type=e.type) for e in entities]
        edges = [GraphEdge(source=r.source_id, target=r.target_id, label=r.relation)
                 for r in relations
                 if r.source_id in node_ids and r.target_id in node_ids]
        # 去重（同一对节点同一 label 只留一条）
        seen, uniq = set(), []
        for e in edges:
            k = (e.source, e.target, e.label)
            if k not in seen:
                seen.add(k)
                uniq.append(e)
        return GraphData(nodes=nodes, edges=uniq)

    # ==================== 图检索 ====================
    def subgraph(self, eid: str, depth: int = 2, limit: int = 100) -> GraphData:
        return self.to_graph(*self.store.subgraph(eid, depth, limit))

    def neighbors(self, eid: str, relation: Optional[str] = None, limit: int = 50) -> GraphData:
        return self.to_graph(*self.store.neighbors(eid, relation, limit))

    def search_graph(self, keyword: str, type_: Optional[str] = None,
                     depth: int = 1, limit: int = 100) -> GraphData:
        _, hits = self.store.list_entities(type_, keyword, 1, 10)
        if not hits:
            return GraphData()
        ents: Dict[str, Entity] = {}
        rels: Dict[tuple, Relation] = {}
        for h in hits:
            es, rs = self.store.subgraph(h.id, depth, limit)
            for e in es:
                ents[e.id] = e
            for r in rs:
                rels[(r.source_id, r.relation, r.target_id)] = r
        return self.to_graph(list(ents.values()), list(rels.values()))

    def find_paths(self, source_id: str, target_id: str,
                   max_depth: int = 4, limit: int = 5) -> List[Dict[str, Any]]:
        out = []
        for ents, rels in self.store.find_paths(source_id, target_id, max_depth, limit):
            out.append({
                "length": len(rels),
                "readable": self._readable(ents, rels),
                "graph": self.to_graph(ents, rels).model_dump(),
            })
        out.sort(key=lambda p: p["length"])
        return out

    @staticmethod
    def _readable(ents: List[Entity], rels: List[Relation]) -> str:
        """把一条路径写成 '失眠 -提示-> 心脾两虚 -对应-> 归脾汤'，给 RAG/Agent 当证据文本。"""
        if not ents:
            return ""
        if not rels:
            return ents[0].name
        name = {e.id: e.name for e in ents}
        cur = ents[0].id                      # ents[0] 一定是路径起点
        parts = [name.get(cur, cur)]
        for r in rels:
            nxt = r.target_id if r.source_id == cur else r.source_id
            arrow = f" -{r.relation}-> " if r.source_id == cur else f" <-{r.relation}- "
            parts.append(arrow + name.get(nxt, nxt))
            cur = nxt
        return "".join(parts)

    # ==================== 批量导入 ====================
    def import_entities(self, rows: List[Dict[str, str]]) -> ImportResult:
        res = ImportResult(total=len(rows))
        for i, row in enumerate(rows, start=2):        # 第 1 行是表头
            try:
                row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
                props = {k: v for k, v in row.items()
                         if k not in RESERVED_ENTITY_COLS and v != ""}
                payload = EntityCreate(
                    id=row.get("id") or None, name=row["name"], type=row["type"],
                    alias=row.get("alias", ""), description=row.get("description", ""),
                    properties=props)
                # 幂等：id 已存在就更新，不报错
                if payload.id and self.store.get_entity(payload.id):
                    self.store.upsert_entity(Entity(**payload.model_dump()))
                else:
                    exist = self.store.get_entity_by_name(payload.name)
                    if exist and exist.type == payload.type:
                        raise ValueError(f"重复实体，已存在 {exist.id}")
                    self.create_entity(payload)
                res.success += 1
            except Exception as ex:
                res.failed += 1
                res.errors.append(ImportError_(row=i, reason=str(ex)))
        return res

    def import_relations(self, rows: List[Dict[str, str]]) -> ImportResult:
        res = ImportResult(total=len(rows))
        for i, row in enumerate(rows, start=2):
            try:
                row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
                self.create_relation(RelationCreate(
                    source_id=row.get("source_id") or None,
                    source_name=row.get("source_name") or None,
                    relation=row["relation"],
                    target_id=row.get("target_id") or None,
                    target_name=row.get("target_name") or None,
                    evidence=row.get("evidence", "")))
                res.success += 1
            except Exception as ex:
                res.failed += 1
                res.errors.append(ImportError_(row=i, reason=str(ex)))
        return res

    @staticmethod
    def parse_csv(content: bytes) -> List[Dict[str, str]]:
        text = content.decode("utf-8-sig")           # 兼容 Excel 导出的 BOM
        return list(csv.DictReader(io.StringIO(text)))

    def stats(self) -> dict:
        return self.store.stats()
