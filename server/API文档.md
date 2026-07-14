# 中医药知识图谱管理模块 · API 文档

> Base URL: `http://localhost:8000/api`  
> 统一响应格式: `{"code": 0, "msg": "ok", "data": ...}` — code=0 表示成功  
> 所有接口(除 /auth/login 和 /auth/register)都需要 Header: `Authorization: Bearer <token>`

---

## 1. 认证

### 登录
```
POST /auth/login
```
请求: `{"username": "admin", "password": "admin123"}`
返回:
```json
{"code": 0, "msg": "ok", "data": {
  "token": "eyJhbGciOi...",
  "user": {"id": 1, "username": "admin", "role": "admin"}
}}
```

### 注册
```
POST /auth/register
```
请求: `{"username": "xxx", "password": "123456"}` — 密码至少 4 位，注册后角色为 `user`
返回: `{"code": 0, "data": {"id": 2, "username": "xxx", "role": "user"}}`

### 当前用户
```
GET /auth/me
```
返回: `{"code": 0, "data": {"id": 1, "username": "admin", "role": "admin", "last_login": "..."}}`

### 修改密码
```
POST /auth/change-password
```
请求: `{"old_password": "...", "new_password": "..."}`

---

## 2. 元数据 & 统计

### 实体类型 / 关系类型 / 关系域约束
```
GET /meta
```
返回:
```json
{"code": 0, "data": {
  "entity_types": ["药材","方剂","症状","证候","功效","禁忌","文献", ...],
  "relation_types": ["包含","主治","提示","对应","具有","禁忌","来源于","记载", ...],
  "relation_schema": {
    "包含": [["方剂","药材"]],
    "主治": [["方剂","症状"],["方剂","证候"],["药材","症状"],["药材","证候"]],
    "提示": [["症状","证候"]],
    "对应": [["证候","方剂"]],
    "具有": [["药材","功效"],["方剂","功效"]],
    "禁忌": [["药材","禁忌"],["方剂","禁忌"]],
    "来源于": [["药材","文献"],["方剂","文献"],["症状","文献"],["证候","文献"],["功效","文献"],["禁忌","文献"]],
    "记载": [["文献","方剂"],["文献","药材"],["文献","证候"],["文献","症状"],["文献","功效"],["文献","禁忌"]]
  }
}}
```

### 平台统计
```
GET /stats
```
返回: `{"code": 0, "data": {"entity_count": 382, "relation_count": 1236, "entity_by_type": {...}, "relation_by_type": {...}}}`

---

## 3. 实体 CRUD

### 列表
```
GET /entities?type=药材&keyword=人参&page=1&size=20
```
返回: `{"code": 0, "data": {"total": 1, "page": 1, "size": 20, "items": [{...}]}}`

### 详情
```
GET /entities/{id}
```

### 创建（需 admin）
```
POST /entities
```
请求:
```json
{
  "name": "实体名称",
  "type": "药材",
  "alias": "别名",
  "description": "描述",
  "properties": {"source": "来源", "note": "备注"}
}
```
- `id` 可选，不传则自动分配（按类型前缀，如 H001、F002）
- `name` 和 `type` 不能为空
- 同名同类型不可重复
- 新实体类型自动接受，自动生成 ASCII 字母前缀

### 更新（需 admin）
```
PUT /entities/{id}
```
请求（只传要改的字段即可）:
```json
{"name": "新名称", "alias": "新别名", "description": "新描述", "properties": {"source": "新来源"}}
```
可单独改任意字段（name / alias / description / properties），不传的保持不变。

### 单条删除（需 admin）
```
DELETE /entities/{id}
```
级联删除关联的所有关系。

### 批量删除（需 admin）
```
DELETE /entities/batch
```
请求: `{"ids": ["H001", "H002", "F003"]}`
返回: `{"code": 0, "data": {"deleted": 3, "total": 3}}`

---

## 4. 关系 CRUD

### 列表
```
GET /relations?source_id=F001&relation=包含&page=1&size=20
```
返回: `{"code": 0, "data": {"total": N, "page": 1, "size": 20, "items": [{...}]}}`

### 创建（需 admin）
```
POST /relations
```
请求（支持名字或 ID，名字优先）:
```json
{
  "source_name": "归脾汤",
  "relation": "包含",
  "target_name": "酸枣仁",
  "evidence": "方剂学教材"
}
```
- `source_name` + `source_id` 二选一，name 优先
- `target_name` + `target_id` 二选一，name 优先
- 关系端点必须存在，不允许自环

### 更新（需 admin）
```
PUT /relations?old_source=H001&old_relation=具有&old_target=G001
```
请求（不传的保持原值）:
```json
{"source_id": "H002", "target_id": "G003", "relation": "主治", "evidence": "新依据"}
```
可改 source/target/relation/evidence 任意组合。

### 单条删除（需 admin）
```
DELETE /relations?source_id=H001&relation=具有&target_id=G001
```

### 批量删除（需 admin）
```
DELETE /relations/batch
```
请求:
```json
{"items": [
  {"source_id": "H001", "relation": "主治", "target_id": "S001"},
  {"source_id": "H001", "relation": "主治", "target_id": "S002"}
]}
```

---

## 5. 图谱检索

### 子图（从实体展开）
```
GET /graph/subgraph?id=H001&depth=2&limit=100
```
返回: `{"code": 0, "data": {"nodes": [...], "edges": [...]}}`

### 邻居
```
GET /graph/neighbors?id=H001&relation=包含&limit=50
```

### 关键词搜索
```
GET /graph/search?keyword=人参&type=药材&depth=2
```
返回格式同子图。

### 路径查询
```
GET /graph/path?source_id=S001&target_id=F001&max_depth=6&limit=5
```
返回:
```json
{"code": 0, "data": {"paths": [
  {"length": 3, "readable": "失眠 -提示-> 心脾两虚 -对应-> 归脾汤 -包含-> 酸枣仁", "graph": {"nodes": [...], "edges": [...]}}
]}}
```

---

## 6. 教学问答（已删除）

`GET /qa/ask` 已移除。图谱查询请用第 5 节 `/graph/*` 接口。智能问答请用 backend `POST /api/agent/case`。

---

## 7. 导入导出（需 admin）

### 模板下载
```
GET /import/template?kind=entity    → CSV 实体模板
GET /import/template?kind=relation  → CSV 关系模板
```

### 导入（支持 CSV 和 Excel .xlsx）
```
POST /import/entities   Content-Type: multipart/form-data, file=<文件>
POST /import/relations  Content-Type: multipart/form-data, file=<文件>
```
返回:
```json
{"code": 0, "data": {"total": 100, "success": 98, "failed": 2, "errors": [{"row": 5, "reason": "..."}]}}
```

---

## 8. 审计 & 回滚

### 操作日志
```
GET /admin/audit-log?user_id=1&action=create&target_type=药材&page=1&size=20
```
筛选参数均可选。每条日志含 `before_snapshot` 和 `after_snapshot`。

### 单条回滚（需 admin）
```
POST /admin/rollback/{log_id}
```
根据日志 ID 回滚该条操作（create→删，update→恢复旧值，delete→重建）。

### 批量回滚（需 admin）
```
POST /admin/rollback-batch
```
两种方式二选一:
```json
{"before_log_id": 15}                          → 撤销 id>15 的所有操作
{"before_time": "2026-07-13 15:30:00"}         → 撤销此时间之后的所有操作
```
倒序执行，返回: `{"total": 10, "rolled_back": 9, "skipped": 1, "failed": 0, "results": [...]}`

### 导入历史
```
GET /admin/import-batches?page=1&size=20
```

---

## 9. 用户管理（需 admin）

```
GET  /admin/users              → 用户列表
POST /admin/users              → 创建用户 {"username":"xxx","password":"xxx","role":"user"}
```
角色: `admin`（管理员）或 `user`（普通用户）

---

## 10. SQL Agent（已迁移至 backend）

> SQL Agent 端点已统一迁移至 backend 模块（同一端口，路径不变）。  
> 旧版原始 SQL 直传接口已废弃，替换为 LLM 驱动的 NL→SQL 接口 + 直接 SQL 双模式。

### NL→SQL 自然语言查询
```
POST /sql/query
```
请求:
```json
{
  "question": "归脾汤由哪些药材组成？",
  "syndromes": ["心脾两虚"],
  "formulas": ["归脾汤"]
}
```
- `question`: 自然语言查询问题
- `syndromes` / `formulas`: 可选，已知的证候/方剂上下文
- 优先 LLM（DeepSeek）生成 SQL，LLM 不可用时 fallback 到模板规则

返回:
```json
{
  "question": "...",
  "generated_sql": "SELECT ...",
  "sql_result": {"rows": [...], "row_count": 5, "status": "success"},
  "generator": "llm",
  "model_used": "deepseek-v4-flash",
  "mode": "mysql",
  "error": null
}
```

### 直接 SQL（调试用）
```
POST /sql/direct
```
请求: `{"sql": "SELECT type, COUNT(*) AS cnt FROM entities GROUP BY type", "params": []}`
只允许 SELECT/WITH，INSERT/UPDATE/DELETE 会被拦截。

### 表结构
```
GET /sql/schema
```
返回 entities 和 relations 的字段列表、类型枚举值、行数统计。

### 统计
```
GET /sql/statistics?refresh=true
```
返回图谱统计 + schema 信息。`refresh=true` 强制重新同步数据库。

### 强制刷新
```
POST /sql/refresh
```
从 MySQL（或 JSON 文件）重新同步 kg.sqlite。

---

## 附录 A: 角色权限

| 角色 | 如何获取 | 权限 |
|------|---------|------|
| admin | 管理员创建 | 全部操作 |
| user | 自行注册 | 只读（GET 全部接口） |

## 附录 B: 实体类型颜色

| 类型 | ID前缀 | 颜色 |
|------|--------|------|
| 药材 | H | `#5e8c61` |
| 方剂 | F | `#b4763f` |
| 症状 | S | `#a8443a` |
| 证候 | Z | `#4a6fa5` |
| 功效 | G | `#7a6ba8` |
| 禁忌 | J | `#3f4a52` |
| 文献 | W | `#8a8256` |
| 新增类型 | 自动分配 | 自动分配 |

## 附录 C: OpenAPI JSON

`http://localhost:8000/openapi.json` — 可导入 Apifox / Postman
