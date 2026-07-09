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

## 说明

当前 `data/` 中都是教学模拟 Mock 数据：

- 不冒充真实医学数据；
- 用于先把成员 3 的 GraphRAG 代码和接口跑通；
- 后续真实数据到位后替换即可。

当前不包含：

- Milvus 预留脚本；
- 复杂 Repository / Adapter；
- tests；
- scripts；
- docs；
- 多层小文件夹；
- Python 缓存文件。

这样更适合 4 周课程项目和多人 Git 分支协作。
