from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    APP_HOST,
    APP_PORT,
    ENTITIES_PATH,
    GRAPH_SOURCE,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_ENABLED,
    LLM_MODEL,
    MILVUS_COLLECTION,
    MILVUS_URI,
    RELATIONS_PATH,
    get_runtime_config,
)
from app.graph_search import GraphSearch
from app.graphrag_service import GraphRAGService
from app.llm_client import LLMClient
from app.milvus_search import MilvusVectorSearch
from app.schemas import (
    GraphRAGQueryRequest,
    QAResult,
)


# ============================================================
# 1. FastAPI 应用
# ============================================================

app = FastAPI(
    title="TCM GraphRAG - Member 3",
    version="0.3.0",
    description=(
        "成员 3 正式 GraphRAG："
        "Milvus 真实语义检索 + "
        "知识图谱路径搜索 + "
        "证据融合 + "
        "DeepSeek 生成"
    ),
)


# ============================================================
# 2. CORS
# ============================================================

# 联调阶段允许跨域，
# 方便成员 4 Agent 和成员 5 前端直接访问。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 3. GraphSearch
# ============================================================

# GraphSearch 支持：
#
# 1. 单个 entities.json / relations.json
# 2. 多 JSON 文件目录
#
# 实际图谱数据源由：
# GRAPH_SOURCE
# GRAPH_ENTITIES_PATH
# GRAPH_RELATIONS_PATH
# 决定。

graph_search = GraphSearch(
    entities_path=ENTITIES_PATH,
    relations_path=RELATIONS_PATH,
)


print(
    "[GraphSearch] 图谱加载成功"
)

print(
    "[GraphSearch] "
    f"Source: {GRAPH_SOURCE}"
)

print(
    "[GraphSearch] "
    f"Entities: {ENTITIES_PATH}"
)

print(
    "[GraphSearch] "
    f"Relations: {RELATIONS_PATH}"
)

print(
    "[GraphSearch] "
    f"Stats: {graph_search.get_stats()}"
)


# ============================================================
# 4. Milvus Vector Search
# ============================================================

# 正式项目固定使用：
# MilvusVectorSearch
#
# 不再自动降级到旧：
# data/docs
# Hash VectorSearch
#
# 原因：
# 1. 旧 3 篇 Mock TXT 已删除；
# 2. 正式 RAG 语料为 7951 chunks；
# 3. 隐式降级到小型 Mock 库会掩盖部署错误；
# 4. Milvus 不可用时应明确报错。

try:
    vector_search = (
        MilvusVectorSearch()
    )

except Exception as exc:
    raise RuntimeError(
        "Milvus 向量检索初始化失败。\n"
        f"URI: {MILVUS_URI}\n"
        f"Collection: {MILVUS_COLLECTION}\n"
        "请检查：\n"
        "1. Milvus Docker 服务是否启动；\n"
        "2. 127.0.0.1:19530 是否可访问；\n"
        "3. tcm_rag_chunks Collection 是否存在；\n"
        "4. 是否已经执行完整语料导入。"
    ) from exc


print(
    "[VectorSearch] "
    "Milvus 后端启动成功"
)

print(
    "[VectorSearch] "
    f"URI: {MILVUS_URI}"
)

print(
    "[VectorSearch] "
    f"Collection: {MILVUS_COLLECTION}"
)


# ============================================================
# 5. LLM Client
# ============================================================

llm_client: LLMClient | None = None


if LLM_ENABLED:
    llm_client = LLMClient(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
    )

    print(
        "[LLM] 已启用真实大模型"
    )

    print(
        "[LLM] "
        f"Model: {LLM_MODEL}"
    )

else:
    print(
        "[LLM] 未启用真实大模型，"
        "使用 GraphRAG fallback answer"
    )


# ============================================================
# 6. GraphRAG Service
# ============================================================

graphrag_service = GraphRAGService(
    vector_search=vector_search,
    graph_search=graph_search,
    llm_client=llm_client,
)


# ============================================================
# 7. Health API
# ============================================================

@app.get(
    "/api/graphrag/health"
)
def health() -> dict[str, Any]:
    """
    成员 4 / 5 联调前检查服务状态。

    返回：
    - FastAPI 状态
    - 图谱状态
    - Milvus 状态
    - LLM 状态

    不返回任何 API Key。
    """
    graph_stats = (
        graph_search.get_stats()
    )

    return {
        "status": "ok",

        # --------------------------------
        # App
        # --------------------------------
        "app": {
            "host": APP_HOST,
            "port": APP_PORT,
            "version": "0.3.0",
        },

        # --------------------------------
        # Graph
        # --------------------------------
        "graph": {
            "source": (
                GRAPH_SOURCE
            ),

            "entities_source": str(
                ENTITIES_PATH
            ),

            "relations_source": str(
                RELATIONS_PATH
            ),

            **graph_stats,
        },

        # --------------------------------
        # Vector Search
        # --------------------------------
        "vector_search": {
            "backend": "milvus",
            "active": True,
        },

        # --------------------------------
        # Milvus
        # --------------------------------
        "milvus": {
            "uri": (
                MILVUS_URI
            ),

            "collection": (
                MILVUS_COLLECTION
            ),

            "active": True,
        },

        # --------------------------------
        # LLM
        # --------------------------------
        "llm": {
            "enabled": (
                LLM_ENABLED
            ),

            "model": (
                LLM_MODEL
            ),
        },
    }


# ============================================================
# 8. Runtime Config API
# ============================================================

@app.get(
    "/api/graphrag/config"
)
def runtime_config() -> dict[str, Any]:
    """
    返回安全的运行配置摘要。

    不包含：
    - LLM_API_KEY
    - EMBEDDING_API_KEY

    用于：
    - 团队联调
    - 页面调试
    - 环境确认
    """
    return get_runtime_config()


# ============================================================
# 9. GraphRAG Query API
# ============================================================

@app.post(
    "/api/graphrag/query",
    response_model=QAResult,
)
def graphrag_query(
    request: GraphRAGQueryRequest,
) -> QAResult:
    """
    成员 3 核心 GraphRAG 接口。

    输入：
    - query
    - top_k
    - max_hops

    内部流程：

        Query
          │
          ├─────────────────┐
          ↓                 ↓
      GraphSearch       Milvus
          ↓                 ↓
      Entity Match      Dense Retrieval
          ↓                 ↓
      Graph BFS          Rerank
          │                 │
          └────────┬────────┘
                   ↓
           Evidence Fusion
                   ↓
               DeepSeek
                   ↓
               QAResult

    输出遵守团队统一问答格式。
    """
    return graphrag_service.query(
        request
    )