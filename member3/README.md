# 中医药 GraphRAG —— 成员 3 

## 目录

```text
tcm_graphrag_member3_minimal/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── graph_search.py
│   ├── vector_search.py
│   ├── llm_client.py
│   └── graphrag_service.py
├── data/
│   ├── entities.json
│   ├── relations.json
│   └── docs/
│       ├── 归脾汤方剂说明.txt
│       ├── 心脾两虚教学说明.txt
│       └── GraphRAG演示说明.txt
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 8 个核心 Python 文件作用

### `app/main.py`
FastAPI 入口。
提供：

- `GET /api/graphrag/health`
- `POST /api/graphrag/query`

后续成员 4 Agent、成员 5 前端直接调用接口。

### `app/config.py`
统一读取 `.env` 与项目路径。
避免把 API Key 和路径写死。

### `app/schemas.py`
最重要的接口契约文件。
严格定义组长要求的：

1. 实体格式；
2. 关系格式；
3. 图谱 nodes / edges；
4. 统一问答结果格式。

### `app/graph_search.py`
负责：

- 读取实体；
- 读取关系；
- 从用户问题中识别实体；
- BFS 搜索 1~N 跳图谱路径；
- 返回统一 `GraphData`。

### `app/vector_search.py`
负责 RAG 文本支路：

- 读取 `data/docs/*.txt`；
- 文本分块；
- 开发期向量化；
- 余弦相似度；
- 返回 Top-K 文本片段。

当前是无外部依赖的开发期方案，后续可替换 Milvus。

### `app/llm_client.py`
负责调用 DeepSeek / OpenAI-compatible Chat Completions。
默认关闭，没有 Key 也能运行。

### `app/graphrag_service.py`
整个成员 3 模块的核心总控：

```text
用户问题
   ├─ 文本检索
   └─ 图谱路径检索
         ↓
      证据融合
         ↓
   LLM / 本地降级回答
         ↓
   统一 QAResult JSON
```

### `app/__init__.py`
告诉 Python：`app` 是一个包。
不需要写业务逻辑。

---

## 运行

### 1. 进入目录

```powershell
cd 你的路径\tcm_graphrag_member3_minimal
```

### 2. 创建虚拟环境

```powershell
python -m venv .venv
```

### 3. 激活

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. 安装依赖

```powershell
pip install -r requirements.txt
```

### 5. 创建 `.env`

```powershell
Copy-Item .env.example .env
```

### 6. 启动

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

### 7. 打开 Swagger

```text
http://127.0.0.1:8003/docs
```

---

## 测试问题

```text
心脾两虚有哪些相关方剂和药材？
```

```text
失眠可能关联哪些证候？
```

```text
归脾汤包含哪些药材？
```

---

## 接入 HKCMMS 药典资料库

HKCMMS 清洗后的安全入库集位于：

```text
data/pharmacopoeia/processed/hkcmms/index_ready/chunks_for_index.jsonl
```

先转换为当前 Milvus RAG schema 可导入的统一 chunk：

```powershell
python scripts/build_hkcmms_rag_corpus.py
```

转换后会生成：

```text
data/pharmacopoeia/processed/hkcmms/index_ready/chunks_for_milvus.jsonl
```

先做字段校验，不连接 Milvus：

```powershell
python scripts/milvus_insert.py `
  --input data/pharmacopoeia/processed/hkcmms/index_ready/chunks_for_milvus.jsonl `
  --limit 0 `
  --check-only
```

确认 Milvus、Embedding API 和 `.env` 配置可用后，导入 HKCMMS 增量语料：

```powershell
python scripts/milvus_insert.py `
  --input data/pharmacopoeia/processed/hkcmms/index_ready/chunks_for_milvus.jsonl `
  --limit 0
```

导入后可做不联网验证：

```powershell
python scripts/verify_hkcmms_milvus.py --skip-search
```

当前 HKCMMS 可入库 chunk 数为 1094 条。每条 evidence 中保留：

- HKCMMS 资料库名称；
- 药材名、简繁检索别名、拉丁/正名、拼音；
- 章节、页码、引用；
- 原始 PDF 相对路径；
- 官方来源 URL。

注意：当前 Milvus schema 不按 `chunk_id` 自动去重，重复运行同一个增量导入文件会产生重复数据。

---

## 轻量 GraphRAG 社区摘要

按老师课件中的 GraphRAG 思路，成员 3 增加了轻量版社区发现与社区摘要：

- 社区发现：基于已加载的实体和关系做无依赖连通社区划分；
- 社区摘要：按实体类型、主要关系、核心实体、代表路径生成规则摘要；
- 检索策略：具体事实问题仍优先走局部文本检索和图谱路径；概览、总结、知识结构类问题会补充社区摘要；
- 接口保持不变：仍返回统一 `QAResult`，社区摘要放入 `evidence`，不新增前端字段。

本功能只消费现有图谱数据，不改写成员 1 的实体关系设计，也不替代成员 2 的图谱管理接口。

离线验证：

```powershell
python scripts/smoke_community_graphrag.py
```

---

## 说明

当前成员 3 模块保留 Mock 图谱兼容，同时已经接入正式 Milvus 文本检索链路：

- 原始课程/问答语料：`data/processed/rag_corpus_clean.jsonl`；
- HKCMMS 药典增量语料：`data/pharmacopoeia/processed/hkcmms/index_ready/chunks_for_milvus.jsonl`；
- 图谱实体/关系格式仍遵守组内统一 JSON 契约；
- 问答结果仍输出统一 `QAResult`，不影响成员 4 Agent 和成员 5 前端联调。

所有回答仅用于中医药知识学习和教学辅助，不构成医疗诊断或用药建议。
