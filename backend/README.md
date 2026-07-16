# 基于知识图谱的中医药诊疗智能体后端

本目录是 FastAPI 后端集成层。已有 `backend/agents/` 和 `backend/tools/` 不需要重写，接口通过 service 层调用现有 `TCMTeachingOrchestratorAgent`。

## 调用链

```text
前端
  -> POST /api/agent/case
  -> backend/api/agent_api.py
  -> backend/services/agent_service.py
  -> 已有 TCMTeachingOrchestratorAgent
  -> 多个子 Agent
  -> 返回统一 JSON
  -> 保存 SQLite 历史记录
  -> 返回前端展示
```

## 启动

```bash
cd D:\UNIVERSITY\junior_second\BYSX
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

API 文档：

```text
http://127.0.0.1:8000/docs
```

## 主要接口

```text
GET  /api/health
POST /api/agent/case
POST /api/rag/search
POST /api/sql/query
GET  /api/sql/statistics
POST /api/documents
POST /api/documents/upload
GET  /api/documents
GET  /api/documents/{document_id}
PUT  /api/documents/{document_id}
DELETE /api/documents/{document_id}
GET  /api/history
GET  /api/history/{history_id}
DELETE /api/history/{history_id}
```

## 测试命令

病例分析：

```bash
curl -X POST "http://127.0.0.1:8000/api/agent/case" ^
  -H "Content-Type: application/json" ^
  -d "{\"case_text\":\"患者失眠多梦，心悸健忘，食少乏力，舌淡，脉细。\"}"
```

RAG 检索：

```bash
curl -X POST "http://127.0.0.1:8000/api/rag/search" ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"归脾汤\",\"formulas\":[\"归脾汤\"],\"top_k\":2}"
```

SQL Agent：

```bash
curl -X POST "http://127.0.0.1:8000/api/sql/query" ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"查询归脾汤相关结构化数据\",\"formulas\":[\"归脾汤\"]}"
```

新增文档资料：

```bash
curl -X POST "http://127.0.0.1:8000/api/documents" ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"归脾汤资料\",\"source\":\"方剂学课程资料\",\"content\":\"归脾汤用于课程设计资料管理测试。\"}"
```

查询历史：

```bash
curl "http://127.0.0.1:8000/api/history?limit=10"
```

## 数据库

第一版使用 SQLite：

```text
backend/data/tcm_agent.db
```

表：

- `qa_history`：保存病例问答历史和完整 JSON 结果
- `documents`：保存资料标题、来源、正文预览和上传文件路径

## 与已有 Agent 的合并方式

`backend/services/agent_service.py` 直接调用已有总控：

```python
from agents.orchestrator_agent import TCMTeachingOrchestratorAgent
```

为了兼容当前 `uvicorn backend.main:app` 的包路径，代码里保留了 `backend.agents...` fallback。业务逻辑仍然复用已有 Agent，不重新定义新的总控 Agent。

## 后续真实接口替换点

- `backend/services/rag_service.py`：替换真实向量库、GraphRAG 或文档检索服务。
- `backend/services/sql_service.py`：替换真实图谱数据 SQL Agent。
- `backend/services/document_service.py`：后续可接对象存储、文档解析、切片入库。
- `backend/services/agent_service.py`：保留统一入口，继续调用已有 Agent 总控。

当前 RAG 已统一接入正式知识图谱、SQLite 文档库和 Qdrant；SQL Agent 使用只读 MySQL/SQLite，图谱查询使用根目录正式实体与关系数据。
