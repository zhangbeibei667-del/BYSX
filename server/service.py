"""
业务层：所有校验、ID 分配、批量导入、图谱格式转换、审计日志。
API 层只负责收发 HTTP，不写业务逻辑。
"""
import csv
import io
from typing import Any, Dict, List, Optional, Tuple

try:
    from .schemas import (Entity, EntityCreate, EntityUpdate,
                           GraphData, GraphEdge, GraphNode, ImportError_,
                           ImportResult, Relation, RelationCreate,
                           validate_entity_type, validate_relation)
    from .store_base import GraphStore
except ImportError:
    from schemas import (Entity, EntityCreate, EntityUpdate,
                          GraphData, GraphEdge, GraphNode, ImportError_,
                          ImportResult, Relation, RelationCreate,
                          validate_entity_type, validate_relation)
    from store_base import GraphStore

RESERVED_ENTITY_COLS = {"id", "name", "type", "alias", "description"}
RELATION_COLS = ["source_id", "source_name", "relation", "target_id", "target_name", "evidence"]


class GraphService:
    def __init__(self, store: GraphStore):
        self.store = store
        self._current_user: Optional[dict] = None   # {id, username, role}

    def set_user(self, user: Optional[dict]) -> None:
        """设置当前操作用户，用于审计日志。"""
        self._current_user = user

    @property
    def _uid(self) -> int:
        return int(self._current_user["sub"]) if self._current_user else 0

    @property
    def _uname(self) -> str:
        return self._current_user.get("username", "") if self._current_user else ""

    def _log(self, action: str, target_type: str, target_id: str,
             target_name: str = "", before: dict | None = None,
             after: dict | None = None) -> None:
        """记录操作日志（静默，失败不抛异常）。"""
        try:
            self.store.insert_operation_log(
                user_id=self._uid, username=self._uname,
                action=action, target_type=target_type,
                target_id=target_id, target_name=target_name,
                before_snapshot=before, after_snapshot=after,
            )
        except Exception:
            pass   # 审计记录失败不应阻断主流程

    # ==================== 实体 ====================
    def create_entity(self, payload: EntityCreate) -> Entity:
        validate_entity_type(payload.type)
        if not payload.name.strip():
            raise ValueError("name 不能为空")
        if not payload.type.strip():
            raise ValueError("type 不能为空")
        exist = self.store.get_entity_by_name(payload.name)
        if exist and exist.type == payload.type:
            raise ValueError(f"同名同类型实体已存在：{exist.id} {exist.name}")
        eid = payload.id or self.store.next_id(payload.type)
        if payload.id and self.store.get_entity(payload.id):
            raise ValueError(f"id 已存在：{payload.id}")
        e = Entity(id=eid, name=payload.name.strip(), type=payload.type,
                   alias=payload.alias, description=payload.description,
                   properties=payload.properties)
        result = self.store.upsert_entity(e)
        self._log("create", e.type, e.id, e.name, after=e.model_dump())
        return result

    def update_entity(self, eid: str, payload: EntityUpdate) -> Entity:
        e = self.store.get_entity(eid)
        if not e:
            raise ValueError(f"实体不存在：{eid}")
        before = e.model_dump()
        data = payload.model_dump(exclude_none=True)
        for k, v in data.items():
            setattr(e, k, v)
        result = self.store.upsert_entity(e)
        self._log("update", e.type, e.id, e.name, before=before, after=e.model_dump())
        return result

    def delete_entity(self, eid: str) -> bool:
        e = self.store.get_entity(eid)
        if e:
            self._log("delete", e.type, e.id, e.name, before=e.model_dump())
        return self.store.delete_entity(eid)

    def get_entity(self, eid: str) -> Optional[Entity]:
        return self.store.get_entity(eid)

    def list_entities(self, type_=None, keyword=None, page=1, size=20):
        if type_:
            validate_entity_type(type_)
        return self.store.list_entities(type_, keyword, page, size)

    # ==================== 关系 ====================
    def _resolve(self, eid: Optional[str], name: Optional[str], role: str) -> Entity:
        """解析关系端点。名字优先：如果名字和 ID 指向不同实体，以名字为准。"""
        name_entity = self.store.get_entity_by_name(name) if name else None
        id_entity = self.store.get_entity(eid) if eid else None

        if name_entity and id_entity and name_entity.id != id_entity.id:
            # ID 与名字不匹配 → 以名字为准，纠正 ID
            return name_entity

        if name_entity:
            return name_entity
        if id_entity:
            return id_entity

        raise ValueError(f"{role} 实体不存在：id={eid} name={name}")

    def create_relation(self, payload: RelationCreate) -> Relation:
        src = self._resolve(payload.source_id, payload.source_name, "source")
        tgt = self._resolve(payload.target_id, payload.target_name, "target")
        if src.id == tgt.id:
            raise ValueError("不允许自环关系")
        validate_relation(payload.relation, src.type, tgt.type)
        r = Relation(source_id=src.id, source_name=src.name, relation=payload.relation,
                     target_id=tgt.id, target_name=tgt.name, evidence=payload.evidence)
        result = self.store.upsert_relation(r)
        self._log("create", "relation", f"{src.id}|{r.relation}|{tgt.id}",
                  f"{src.name}-{r.relation}->{tgt.name}", after=r.model_dump())
        return result

    def update_relation(self, old_source: str, old_relation: str, old_target: str,
                        new_data: dict) -> Relation:
        """原子更新关系。键不变时走 upsert；键变化时走 replace_relation
        （单事务删旧+建新，HybridStore 下两侧同时成功或同时回滚）。"""
        # 解析新端点（名字优先）
        new_src_id = new_data.get("source_id", old_source)
        new_tgt_id = new_data.get("target_id", old_target)
        new_src_name = new_data.get("source_name")
        new_tgt_name = new_data.get("target_name")

        src = self._resolve(new_src_id, new_src_name, "source")
        tgt = self._resolve(new_tgt_id, new_tgt_name, "target")
        if src.id == tgt.id:
            raise ValueError("不允许自环关系")

        new_rel = new_data.get("relation", old_relation)
        validate_relation(new_rel, src.type, tgt.type)
        new_ev = new_data.get("evidence", "")

        r = Relation(source_id=src.id, source_name=src.name, relation=new_rel,
                     target_id=tgt.id, target_name=tgt.name, evidence=new_ev)

        key_changed = (old_source != src.id or old_relation != new_rel
                       or old_target != tgt.id)
        if key_changed:
            result = self.store.replace_relation(
                old_source, old_relation, old_target, r)
            self._log("update", "relation",
                      f"{old_source}|{old_relation}|{old_target}",
                      f"{src.name}-{new_rel}->{tgt.name}",
                      before={"source_id": old_source, "relation": old_relation,
                              "target_id": old_target},
                      after=r.model_dump())
        else:
            result = self.store.upsert_relation(r)
            self._log("update", "relation",
                      f"{src.id}|{new_rel}|{tgt.id}",
                      f"{src.name}-{new_rel}->{tgt.name}",
                      after=r.model_dump())
        return result

    def delete_relation(self, source_id: str, relation: str, target_id: str) -> bool:
        # 查询删除前的关系用于审计
        _, rels = self.store.list_relations(source_id, target_id, relation, 1, 1)
        if rels:
            self._log("delete", "relation",
                      f"{source_id}|{relation}|{target_id}",
                      f"{rels[0].source_name}-{relation}->{rels[0].target_name}",
                      before=rels[0].model_dump())
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
        if not ents:
            return ""
        if not rels:
            return ents[0].name
        name = {e.id: e.name for e in ents}
        cur = ents[0].id
        parts = [name.get(cur, cur)]
        for r in rels:
            nxt = r.target_id if r.source_id == cur else r.source_id
            arrow = f" -{r.relation}-> " if r.source_id == cur else f" <-{r.relation}- "
            parts.append(arrow + name.get(nxt, nxt))
            cur = nxt
        return "".join(parts)

    # ==================== 批量导入（事务模式） ====================
    def import_entities(self, rows: List[Dict[str, str]],
                         strict: bool = False) -> ImportResult:
        """导入实体：先逐行校验+合并，再单事务批量写入。"""
        res = ImportResult(total=len(rows))
        resolved: List[Entity] = []
        for i, row in enumerate(rows, start=2):
            try:
                row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
                if not row.get("name") or not row.get("type"):
                    raise ValueError("name 和 type 不能为空")
                props = {k: v for k, v in row.items()
                         if k not in RESERVED_ENTITY_COLS and v != ""}
                payload = EntityCreate(
                    id=row.get("id") or None, name=row["name"], type=row["type"],
                    alias=row.get("alias", ""), description=row.get("description", ""),
                    properties=props)

                # 同 ID 已存在 → 直接覆盖
                if payload.id and self.store.get_entity(payload.id):
                    resolved.append(Entity(**payload.model_dump()))
                    res.success += 1
                    continue

                # 同名同类型 → 合并属性
                exist = self.store.get_entity_by_name(payload.name)
                if exist and exist.type == payload.type:
                    exist_aliases = set(a.strip() for a in exist.alias.split("/") if a.strip())
                    new_aliases = [a.strip() for a in payload.alias.split("/") if a.strip()
                                   and a.strip() not in exist_aliases]
                    merged = Entity(
                        id=exist.id, name=exist.name, type=exist.type,
                        alias="/".join(list(exist_aliases) + new_aliases),
                        description=exist.description or payload.description,
                        properties={**(payload.properties or {}), **(exist.properties or {})},
                    )
                    resolved.append(merged)
                    res.success += 1
                    continue

                # 无 ID → 自动分配
                if not payload.id:
                    payload.id = self.store.next_id(payload.type)

                validate_entity_type(payload.type)
                resolved.append(Entity(**payload.model_dump()))
                res.success += 1
            except Exception as ex:
                res.failed += 1
                res.errors.append(ImportError_(row=i, reason=str(ex)))

        # 单事务批量写入
        written = self.store.bulk_upsert_entities(resolved)
        if written < len(resolved):
            diff = len(resolved) - written
            res.success -= diff
            res.failed += diff

        # 汇总操作日志（批量导入只记一条）
        self._log("import", "entity", f"batch:{res.total}",
                  f"导入实体 {res.total} 条, 成功 {res.success}, 失败 {res.failed}")
        return res

    def import_relations(self, rows: List[Dict[str, str]],
                          strict: bool = False) -> ImportResult:
        """导入关系：先逐行校验+解析，再单事务批量写入。"""
        res = ImportResult(total=len(rows))
        resolved: List[Relation] = []
        for i, row in enumerate(rows, start=2):
            try:
                row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
                source_id = row.get("source_id") or None
                target_id = row.get("target_id") or None
                source_name = row.get("source_name") or None
                target_name = row.get("target_name") or None
                rel_type = row["relation"]
                evidence = row.get("evidence", "")

                src = self._resolve(source_id, source_name, "source")
                tgt = self._resolve(target_id, target_name, "target")
                if src.id == tgt.id:
                    raise ValueError("不允许自环关系")
                validate_relation(rel_type, src.type, tgt.type)

                resolved.append(Relation(
                    source_id=src.id, source_name=src.name,
                    relation=rel_type, target_id=tgt.id, target_name=tgt.name,
                    evidence=evidence))
                res.success += 1
            except Exception as ex:
                res.failed += 1
                res.errors.append(ImportError_(row=i, reason=str(ex)))

        # 单事务批量写入
        written = self.store.bulk_upsert_relations(resolved)
        if written < len(resolved):
            diff = len(resolved) - written
            res.success -= diff
            res.failed += diff

        # 汇总操作日志（批量导入只记一条）
        self._log("import", "relation", f"batch:{res.total}",
                  f"导入关系 {res.total} 条, 成功 {res.success}, 失败 {res.failed}")
        return res

    @staticmethod
    def parse_csv(content: bytes) -> List[Dict[str, str]]:
        text = content.decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))

    @staticmethod
    def parse_excel(content: bytes) -> List[Dict[str, str]]:
        """解析 .xlsx 文件，取第一个 sheet 的第一行作为表头。"""
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        headers = [str(h or "").strip() for h in next(rows_iter, [])]
        if not headers:
            return []
        result = []
        for row in rows_iter:
            d = {}
            for i, h in enumerate(headers):
                val = row[i] if i < len(row) else ""
                d[h] = str(val).strip() if val is not None else ""
            result.append(d)
        wb.close()
        return result

    @staticmethod
    def parse_file(filename: str, content: bytes) -> List[Dict[str, str]]:
        """根据文件名自动选择解析方式。"""
        if filename.lower().endswith(".xlsx"):
            return GraphService.parse_excel(content)
        return GraphService.parse_csv(content)

    # ==================== 图谱查询请用 subgraph / neighbors / search_graph / find_paths ====================

    def stats(self) -> dict:
        return self.store.stats()
