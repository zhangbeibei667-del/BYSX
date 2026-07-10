"""HTTP 接口层。所有响应统一包 {code, msg, data}；图谱接口的 data 就是 {nodes, edges}。"""
from typing import Optional

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import PlainTextResponse

try:
    from .config import get_store
    from .schemas import (ApiResponse, ENTITY_TYPES, EntityCreate, EntityUpdate,
                           RELATION_SCHEMA, RELATION_TYPES, RelationCreate)
    from .service import GraphService
except ImportError:
    from config import get_store
    from schemas import (ApiResponse, ENTITY_TYPES, EntityCreate, EntityUpdate,
                          RELATION_SCHEMA, RELATION_TYPES, RelationCreate)
    from service import GraphService

router = APIRouter(prefix="/api")


def svc() -> GraphService:
    return GraphService(get_store())


def ok(data=None):
    return ApiResponse(code=0, msg="ok", data=data)


def fail(msg: str, code: int = 400):
    return ApiResponse(code=code, msg=msg, data=None)


# ---------- 元数据：前端下拉框直接读这个，不要写死 ----------
@router.get("/meta", response_model=ApiResponse)
def meta():
    return ok({
        "entity_types": ENTITY_TYPES,
        "relation_types": RELATION_TYPES,
        "relation_schema": {k: [list(p) for p in v] for k, v in RELATION_SCHEMA.items()},
    })


@router.get("/stats", response_model=ApiResponse)
def stats():
    return ok(svc().stats())


# ---------- 实体 ----------
@router.post("/entities", response_model=ApiResponse)
def create_entity(payload: EntityCreate):
    try:
        return ok(svc().create_entity(payload).model_dump())
    except Exception as e:
        return fail(str(e))


@router.get("/entities", response_model=ApiResponse)
def list_entities(type: Optional[str] = None, keyword: Optional[str] = None,
                  page: int = 1, size: int = 20):
    try:
        total, items = svc().list_entities(type, keyword, page, size)
        return ok({"total": total, "page": page, "size": size,
                   "items": [i.model_dump() for i in items]})
    except Exception as e:
        return fail(str(e))


@router.get("/entities/{eid}", response_model=ApiResponse)
def get_entity(eid: str):
    e = svc().get_entity(eid)
    return ok(e.model_dump()) if e else fail(f"实体不存在：{eid}", 404)


@router.put("/entities/{eid}", response_model=ApiResponse)
def update_entity(eid: str, payload: EntityUpdate):
    try:
        return ok(svc().update_entity(eid, payload).model_dump())
    except Exception as e:
        return fail(str(e))


@router.delete("/entities/{eid}", response_model=ApiResponse)
def delete_entity(eid: str):
    return ok({"deleted": svc().delete_entity(eid)})


# ---------- 关系 ----------
@router.post("/relations", response_model=ApiResponse)
def create_relation(payload: RelationCreate):
    try:
        return ok(svc().create_relation(payload).model_dump())
    except Exception as e:
        return fail(str(e))


@router.get("/relations", response_model=ApiResponse)
def list_relations(source_id: Optional[str] = None, target_id: Optional[str] = None,
                   relation: Optional[str] = None, page: int = 1, size: int = 20):
    total, items = svc().list_relations(source_id, target_id, relation, page, size)
    return ok({"total": total, "page": page, "size": size,
               "items": [i.model_dump() for i in items]})


@router.delete("/relations", response_model=ApiResponse)
def delete_relation(source_id: str, relation: str, target_id: str):
    return ok({"deleted": svc().delete_relation(source_id, relation, target_id)})


# ---------- 批量导入 ----------
@router.get("/import/template", response_class=PlainTextResponse)
def import_template(kind: str = Query("entity", pattern="^(entity|relation)$")):
    if kind == "entity":
        return ("id,name,type,alias,description,source,note\n"
                "F001,归脾汤,方剂,归脾汤,\"益气补血，健脾养心\",方剂学资料,\n")
    return ("source_id,source_name,relation,target_id,target_name,evidence\n"
            "F001,归脾汤,包含,H001,酸枣仁,方剂组成资料\n")


@router.post("/import/entities", response_model=ApiResponse)
async def import_entities(file: UploadFile = File(...)):
    s = svc()
    rows = s.parse_csv(await file.read())
    return ok(s.import_entities(rows).model_dump())


@router.post("/import/relations", response_model=ApiResponse)
async def import_relations(file: UploadFile = File(...)):
    s = svc()
    rows = s.parse_csv(await file.read())
    return ok(s.import_relations(rows).model_dump())


# ---------- 图谱检索：data 一律是 {nodes, edges} ----------
@router.get("/graph/subgraph", response_model=ApiResponse)
def subgraph(id: str, depth: int = 2, limit: int = 100):
    return ok(svc().subgraph(id, depth, limit).model_dump())


@router.get("/graph/neighbors", response_model=ApiResponse)
def neighbors(id: str, relation: Optional[str] = None, limit: int = 50):
    return ok(svc().neighbors(id, relation, limit).model_dump())


@router.get("/graph/search", response_model=ApiResponse)
def search_graph(keyword: str, type: Optional[str] = None, depth: int = 1, limit: int = 100):
    return ok(svc().search_graph(keyword, type, depth, limit).model_dump())


@router.get("/graph/path", response_model=ApiResponse)
def find_path(source_id: str, target_id: str, max_depth: int = 4, limit: int = 5):
    return ok({"paths": svc().find_paths(source_id, target_id, max_depth, limit)})


# ---------- 教学问答：data 就是 QAResult（图 4 格式） ----------
@router.get("/qa/ask", response_model=ApiResponse)
def qa_ask(keyword: str = Query(..., description="症状名、方剂名或药材名，如 失眠 / 归脾汤")):
    """输入实体名称，返回完整 QAResult。任务 3/4 可替换内部实现，API 契约不变。"""
    try:
        return ok(svc().qa_ask(keyword).model_dump())
    except Exception as e:
        return fail(str(e))
