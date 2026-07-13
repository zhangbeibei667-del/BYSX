"""HTTP 接口层。统一响应格式 {code, msg, data}。
鉴权：读操作需登录（user/admin），写操作需管理员（admin）。
"""
import json
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse

try:
    from .auth import (create_token, decode_token, get_current_user, hash_password,
                        require_admin, verify_password)
    from .config import get_store
    from .schemas import (ApiResponse, EntityCreate, EntityUpdate,
                           RelationCreate, get_entity_types, get_relation_types,
                           get_relation_schema)
    from .service import GraphService
except ImportError:
    from auth import (create_token, decode_token, get_current_user, hash_password,
                       require_admin, verify_password)
    from config import get_store
    from schemas import (ApiResponse, EntityCreate, EntityUpdate,
                          RelationCreate, get_entity_types, get_relation_types,
                          get_relation_schema)
    from service import GraphService

router = APIRouter(prefix="/api")


def svc() -> GraphService:
    return GraphService(get_store())


def ok(data=None):
    return ApiResponse(code=0, msg="ok", data=data)


def fail(msg: str, code: int = 400):
    return ApiResponse(code=code, msg=msg, data=None)


# ============================================================
# 认证（无需登录）
# ============================================================
@router.post("/auth/register", response_model=ApiResponse)
def register(payload: dict = Body(...)):
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()
    if not username or not password:
        return fail("用户名和密码不能为空")
    if len(password) < 4:
        return fail("密码至少 4 位")
    store = get_store()
    if store.get_user_by_username(username):
        return fail("用户名已存在")
    uid = store.create_user(username, hash_password(password), "user")
    return ok({"id": uid, "username": username, "role": "user"})


@router.post("/auth/login", response_model=ApiResponse)
def login(payload: dict = Body(...)):
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "")
    if not username or not password:
        return fail("用户名和密码不能为空")
    store = get_store()
    user = store.get_user_by_username(username)
    if not user:
        return fail("用户名或密码错误", 401)
    if not user.get("is_active"):
        return fail("账号已被禁用", 403)
    if not verify_password(password, user["password_hash"]):
        return fail("用户名或密码错误", 401)
    store.update_last_login(user["id"])
    token = create_token(user["id"], user["username"], user["role"])
    return ok({
        "token": token,
        "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
    })


# ============================================================
# 个人信息（需登录）
# ============================================================
@router.post("/auth/change-password", response_model=ApiResponse)
def change_password(payload: dict = Body(...),
                     user: dict = Depends(get_current_user)):
    store = get_store()
    db_user = store.get_user_by_id(int(user["sub"]))
    if not db_user:
        return fail("用户不存在", 404)
    old = payload.get("old_password", "")
    new = payload.get("new_password", "")
    if not verify_password(old, db_user["password_hash"]):
        return fail("原密码错误", 403)
    store.change_password(int(user["sub"]), hash_password(new))
    return ok({"changed": True})


@router.get("/auth/me", response_model=ApiResponse)
def me(user: dict = Depends(get_current_user)):
    store = get_store()
    db_user = store.get_user_by_id(int(user["sub"]))
    if not db_user:
        return fail("用户不存在", 404)
    return ok({
        "id": db_user["id"], "username": db_user["username"],
        "role": db_user["role"], "last_login": str(db_user.get("last_login", "")),
    })


# ============================================================
# 元数据 & 统计（需登录）
# ============================================================
@router.get("/meta", response_model=ApiResponse)
def meta(user: dict = Depends(get_current_user)):
    return ok({
        "entity_types": get_entity_types(),
        "relation_types": get_relation_types(),
        "relation_schema": {k: [list(p) for p in v] for k, v in get_relation_schema().items()},
    })


@router.get("/stats", response_model=ApiResponse)
def stats(user: dict = Depends(get_current_user)):
    return ok(svc().stats())


# ============================================================
# 实体 CRUD
# ============================================================
@router.post("/entities", response_model=ApiResponse)
def create_entity(payload: EntityCreate, user: dict = Depends(require_admin)):
    s = svc(); s.set_user(user)
    try:
        return ok(s.create_entity(payload).model_dump())
    except Exception as e:
        return fail(str(e))


@router.get("/entities", response_model=ApiResponse)
def list_entities(type: Optional[str] = None, keyword: Optional[str] = None,
                  page: int = 1, size: int = 20,
                  user: dict = Depends(get_current_user)):
    try:
        total, items = svc().list_entities(type, keyword, page, size)
        return ok({"total": total, "page": page, "size": size,
                   "items": [i.model_dump() for i in items]})
    except Exception as e:
        return fail(str(e))


@router.get("/entities/{eid}", response_model=ApiResponse)
def get_entity(eid: str, user: dict = Depends(get_current_user)):
    e = svc().get_entity(eid)
    return ok(e.model_dump()) if e else fail(f"实体不存在：{eid}", 404)


@router.put("/entities/{eid}", response_model=ApiResponse)
def update_entity(eid: str, payload: EntityUpdate,
                   user: dict = Depends(require_admin)):
    s = svc(); s.set_user(user)
    try:
        return ok(s.update_entity(eid, payload).model_dump())
    except Exception as e:
        return fail(str(e))


@router.delete("/entities/batch", response_model=ApiResponse)
def delete_entities_batch(payload: dict = Body(...),
                           user: dict = Depends(require_admin)):
    ids = payload.get("ids", [])
    if not ids:
        return fail("ids 不能为空")
    s = svc(); s.set_user(user)
    deleted = 0
    for eid in ids:
        if s.delete_entity(eid):
            deleted += 1
    return ok({"deleted": deleted, "total": len(ids)})


@router.delete("/entities/{eid}", response_model=ApiResponse)
def delete_entity(eid: str, user: dict = Depends(require_admin)):
    s = svc(); s.set_user(user)
    return ok({"deleted": s.delete_entity(eid)})


# ============================================================
# 关系 CRUD
# ============================================================
@router.post("/relations", response_model=ApiResponse)
def create_relation(payload: RelationCreate, user: dict = Depends(require_admin)):
    s = svc(); s.set_user(user)
    try:
        return ok(s.create_relation(payload).model_dump())
    except Exception as e:
        return fail(str(e))


@router.get("/relations", response_model=ApiResponse)
def list_relations(source_id: Optional[str] = None, target_id: Optional[str] = None,
                   relation: Optional[str] = None, page: int = 1, size: int = 20,
                   user: dict = Depends(get_current_user)):
    total, items = svc().list_relations(source_id, target_id, relation, page, size)
    return ok({"total": total, "page": page, "size": size,
               "items": [i.model_dump() for i in items]})


@router.put("/relations", response_model=ApiResponse)
def update_relation(old_source: str = Query(...), old_relation: str = Query(...),
                     old_target: str = Query(...),
                     payload: dict = Body(...),
                     user: dict = Depends(require_admin)):
    """更新关系：source/relation/target/evidence 均可修改。
    查询参数标识旧关系，body 传新值。"""
    s = svc(); s.set_user(user)
    # 解析新值（没传就用旧的）
    new_src_id = payload.get("source_id", old_source)
    new_tgt_id = payload.get("target_id", old_target)
    new_rel = payload.get("relation", old_relation)
    new_ev = payload.get("evidence", "")
    # 删旧 + 建新（在同一 store 连接上，自然在一个事务里）
    s.delete_relation(old_source, old_relation, old_target)
    r = s.create_relation(RelationCreate(
        source_id=new_src_id, target_id=new_tgt_id,
        relation=new_rel, evidence=new_ev,
    ))
    return ok(r.model_dump())


@router.delete("/relations", response_model=ApiResponse)
def delete_relation(source_id: str, relation: str, target_id: str,
                    user: dict = Depends(require_admin)):
    s = svc(); s.set_user(user)
    return ok({"deleted": s.delete_relation(source_id, relation, target_id)})


@router.delete("/relations/batch", response_model=ApiResponse)
def delete_relations_batch(payload: dict = Body(...),
                            user: dict = Depends(require_admin)):
    items = payload.get("items", [])
    if not items:
        return fail("items 不能为空")
    s = svc(); s.set_user(user)
    deleted = 0
    for r in items:
        if s.delete_relation(r.get("source_id", ""), r.get("relation", ""),
                              r.get("target_id", "")):
            deleted += 1
    return ok({"deleted": deleted, "total": len(items)})


# ============================================================
# 批量导入（需管理员）
# ============================================================
@router.get("/import/template", response_class=PlainTextResponse)
def import_template(kind: str = Query("entity", pattern="^(entity|relation)$"),
                    user: dict = Depends(get_current_user)):
    if kind == "entity":
        return ("id,name,type,alias,description,source,note\n"
                "F001,归脾汤,方剂,归脾汤,\"益气补血，健脾养心\",方剂学资料,\n")
    return ("source_id,source_name,relation,target_id,target_name,evidence\n"
            "F001,归脾汤,包含,H001,酸枣仁,方剂组成资料\n")


@router.post("/import/entities", response_model=ApiResponse)
async def import_entities(file: UploadFile = File(...),
                           strict: bool = Query(False),
                           user: dict = Depends(require_admin)):
    s = svc(); s.set_user(user)
    rows = s.parse_file(file.filename or "", await file.read())
    res = s.import_entities(rows, strict=strict)
    try:
        get_store().insert_import_batch(
            user_id=int(user["sub"]), username=user.get("username", ""),
            kind="entity", file_name=file.filename or "",
            total=res.total, success=res.success, failed=res.failed,
            errors=[e.model_dump() for e in res.errors],
        )
    except Exception:
        pass
    return ok(res.model_dump())


@router.post("/import/relations", response_model=ApiResponse)
async def import_relations(file: UploadFile = File(...),
                            strict: bool = Query(False),
                            user: dict = Depends(require_admin)):
    s = svc(); s.set_user(user)
    rows = s.parse_file(file.filename or "", await file.read())
    res = s.import_relations(rows, strict=strict)
    try:
        get_store().insert_import_batch(
            user_id=int(user["sub"]), username=user.get("username", ""),
            kind="relation", file_name=file.filename or "",
            total=res.total, success=res.success, failed=res.failed,
            errors=[e.model_dump() for e in res.errors],
        )
    except Exception:
        pass
    return ok(res.model_dump())


# ============================================================
# 图谱检索（需登录）
# ============================================================
@router.get("/graph/subgraph", response_model=ApiResponse)
def subgraph(id: str, depth: int = 2, limit: int = 100,
             user: dict = Depends(get_current_user)):
    return ok(svc().subgraph(id, depth, limit).model_dump())


@router.get("/graph/neighbors", response_model=ApiResponse)
def neighbors(id: str, relation: Optional[str] = None, limit: int = 50,
              user: dict = Depends(get_current_user)):
    return ok(svc().neighbors(id, relation, limit).model_dump())


@router.get("/graph/search", response_model=ApiResponse)
def search_graph(keyword: str, type: Optional[str] = None, depth: int = 1,
                 limit: int = 100, user: dict = Depends(get_current_user)):
    return ok(svc().search_graph(keyword, type, depth, limit).model_dump())


@router.get("/graph/path", response_model=ApiResponse)
def find_path(source_id: str, target_id: str, max_depth: int = 4, limit: int = 5,
              user: dict = Depends(get_current_user)):
    return ok({"paths": svc().find_paths(source_id, target_id, max_depth, limit)})


# ============================================================
# 教学问答 — 已删除，图谱查询请用 Section 5 的 /graph/* 接口
# ============================================================


# ============================================================
# 审计日志（需登录）
# ============================================================
@router.get("/admin/audit-log", response_model=ApiResponse)
def list_audit_log(user_id: Optional[int] = None, action: Optional[str] = None,
                    target_type: Optional[str] = None, target_id: Optional[str] = None,
                    page: int = 1, size: int = 20,
                    user: dict = Depends(get_current_user)):
    total, items = get_store().list_operation_log(
        user_id=user_id, action=action, target_type=target_type,
        target_id=target_id, page=page, size=size,
    )
    return ok({"total": total, "page": page, "size": size, "items": items})


@router.get("/admin/audit-log/{log_id}", response_model=ApiResponse)
def get_audit_log(log_id: int, user: dict = Depends(get_current_user)):
    entry = get_store().get_operation_log(log_id)
    return ok(entry) if entry else fail("日志不存在", 404)


@router.post("/admin/rollback/{log_id}", response_model=ApiResponse)
def rollback(log_id: int, user: dict = Depends(require_admin)):
    store = get_store()
    entry = store.get_operation_log(log_id)
    if not entry:
        return fail("日志不存在", 404)
    before = entry.get("before_snapshot")
    if not before:
        return fail("该操作没有历史快照，无法回滚", 400)
    if isinstance(before, str):
        before = json.loads(before)
    action = entry["action"]
    target_type = entry["target_type"]
    s = svc(); s.set_user(user)
    if target_type == "relation":
        r = RelationCreate(
            source_id=before.get("source_id"), target_id=before.get("target_id"),
            relation=before.get("relation", ""), evidence=before.get("evidence", ""),
            source_name=before.get("source_name", ""), target_name=before.get("target_name", ""),
        )
        if action == "delete":
            s.create_relation(r)
        else:
            s.delete_relation(before.get("source_id", ""), before.get("relation", ""),
                              before.get("target_id", ""))
    else:
        if action == "delete":
            payload = EntityCreate(
                id=before.get("id"), name=before["name"], type=before["type"],
                alias=before.get("alias", ""), description=before.get("description", ""),
                properties=before.get("properties", {}),
            )
            s.create_entity(payload)
        elif action in ("create", "update"):
            s.delete_entity(before["id"])
    return ok({"rolled_back": True, "log_id": log_id})


@router.post("/admin/rollback-batch", response_model=ApiResponse)
def rollback_batch(before_log_id: int = Body(None, embed=True),
                    before_time: str = Body(None, embed=True),
                    user: dict = Depends(require_admin)):
    """批量回滚：撤销某条日志之后 / 某个时间之后的所有操作（倒序执行）。

    两种方式（二选一）：
      - before_log_id: 撤销 id > 此值之后的所有操作
      - before_time:   撤销此时间之后的所有操作（格式 "2026-07-13 15:30:00"）
    """
    if before_log_id is None and before_time is None:
        return fail("请提供 before_log_id 或 before_time")
    store = get_store()
    total_all, logs = store.list_operation_log(page=1, size=500)
    # 按条件筛选，按时间倒序
    if before_time is not None:
        to_rollback = [log for log in logs
                       if (log.get("created_at") or "") > before_time]
    else:
        to_rollback = [log for log in logs if log["id"] > before_log_id]
    to_rollback.sort(key=lambda l: l.get("created_at", ""), reverse=True)

    if not to_rollback:
        return ok({"rolled_back": 0, "message": "没有需要回滚的操作"})

    s = svc(); s.set_user(user)
    results = []
    for entry in to_rollback:
        log_id = entry["id"]
        before = entry.get("before_snapshot")
        target_type = entry["target_type"]
        action = entry["action"]
        target_name = entry.get("target_name", "") or entry.get("target_id", "")

        try:
            if not before and action != "create":
                results.append({"log_id": log_id, "status": "skipped", "reason": "无快照"})
                continue

            if isinstance(before, str):
                before = json.loads(before) if before else None

            if target_type == "relation":
                r = RelationCreate(
                    source_id=before.get("source_id"), target_id=before.get("target_id"),
                    relation=before.get("relation", ""), evidence=before.get("evidence", ""),
                    source_name=before.get("source_name", ""),
                    target_name=before.get("target_name", ""),
                )
                if action == "delete":
                    s.create_relation(r)
                else:
                    s.delete_relation(before.get("source_id", ""), before.get("relation", ""),
                                      before.get("target_id", ""))
            else:
                if action == "delete":
                    s.create_entity(EntityCreate(
                        id=before.get("id"), name=before["name"], type=before["type"],
                        alias=before.get("alias", ""), description=before.get("description", ""),
                        properties=before.get("properties", {}),
                    ))
                elif action in ("create", "update"):
                    s.delete_entity(before["id"])
                elif action == "import":
                    continue  # 导入批次不逐条回滚

            results.append({"log_id": log_id, "status": "ok", "action": action, "target": target_name})
        except Exception as ex:
            results.append({"log_id": log_id, "status": "failed", "reason": str(ex)})

    ok_count = sum(1 for r in results if r["status"] == "ok")
    return ok({
        "total": len(to_rollback),
        "rolled_back": ok_count,
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    })


# ============================================================
# 导入批次（需登录）
# ============================================================
@router.get("/admin/import-batches", response_model=ApiResponse)
def list_import_batches(page: int = 1, size: int = 20,
                         user: dict = Depends(get_current_user)):
    total, items = get_store().list_import_batches(page=page, size=size)
    return ok({"total": total, "page": page, "size": size, "items": items})


# ============================================================
# 用户管理（仅管理员）
# ============================================================
@router.get("/admin/users", response_model=ApiResponse)
def list_users(user: dict = Depends(require_admin)):
    return ok(get_store().list_users())


@router.post("/admin/users", response_model=ApiResponse)
def create_user(payload: dict = Body(...), user: dict = Depends(require_admin)):
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()
    role = payload.get("role", "user")
    if not username or not password:
        return fail("用户名和密码不能为空")
    if role not in ("admin", "user"):
        return fail("角色必须是 admin 或 user")
    if len(password) < 4:
        return fail("密码至少 4 位")
    if get_store().get_user_by_username(username):
        return fail("用户名已存在")
    uid = get_store().create_user(username, hash_password(password), role)
    return ok({"id": uid, "username": username, "role": role})


# ============================================================
# SQL Agent — 已统一迁移至 backend/api/sql_api.py
#   参见 POST /api/sql/query 和 GET /api/sql/schema
#   原始 SQL 只读执行能力保留在 MySQLStore.execute_readonly_sql()
#   供 backend tools 内部调用
# ============================================================
