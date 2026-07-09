from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    APP_HOST,
    APP_PORT,
    DOCS_DIR,
    ENTITIES_PATH,
    GRAPH_SOURCE,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_ENABLED,
    LLM_MODEL,
    MILVUS_COLLECTION,
    MILVUS_URI,
    RELATIONS_PATH,
    VECTOR_BACKEND,
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
from app.vector_search import VectorSearch


# ============================================================
# 1. FastAPI 应用
# ============================================================

app = FastAPI(
    title="TCM GraphRAG - Member 3",
    version="0.2.0",
    description=(
        "成员 3 GraphRAG："
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

# 新版 GraphSearch 已支持：
#
# 1. 单个 entities.json / relations.json
# 2. 多 JSON 文件目录
#
# 实际数据源由 config.py 和 .env 决定。

graph_search = GraphSearch(
    entities_path=ENTITIES_PATH,
    relations_path=RELATIONS_PATH,
)


# ============================================================
# 4. Vector Search Backend
# ============================================================

# 用户配置希望使用的后端：
#
# milvus
# hash

VECTOR_BACKEND_REQUESTED = VECTOR_BACKEND

# 实际成功启动的后端
VECTOR_BACKEND_ACTIVE = ""

# 如果发生自动降级，
# 记录错误供 health 接口调试
VECTOR_BACKEND_ERROR: str | None = None


def _build_vector_search() -> Any:
    """
    根据 VECTOR_BACKEND 创建文本检索器。

    milvus:
        正式后端
        7951 条清洗语料
        text-embedding-v4
        1024 维向量

    hash:
        开发期 fallback
        data/docs 下 Mock 文本

    当配置为 milvus，
    但 Milvus 临时不可访问时：
        自动降级为 hash

    这样可以避免：
        Docker 未启动
        19530 不通
        Collection 不存在

    导致整个 FastAPI 服务直接无法启动。
    """
    global VECTOR_BACKEND_ACTIVE
    global VECTOR_BACKEND_ERROR

    # --------------------------------------------------------
    # 正式 Milvus
    # --------------------------------------------------------
    if VECTOR_BACKEND_REQUESTED == "milvus":
        try:
            searcher = MilvusVectorSearch()

            VECTOR_BACKEND_ACTIVE = "milvus"
            VECTOR_BACKEND_ERROR = None

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
                f"Collection: "
                f"{MILVUS_COLLECTION}"
            )

            return searcher

        except Exception as exc:
            VECTOR_BACKEND_ERROR = (
                f"{type(exc).__name__}: {exc}"
            )

            print(
                "[VectorSearch] "
                "Milvus 后端启动失败"
            )

            print(
                "[VectorSearch] "
                f"错误: {VECTOR_BACKEND_ERROR}"
            )

            print(
                "[VectorSearch] "
                "自动降级为 Hash VectorSearch"
            )

            searcher = VectorSearch(
                docs_dir=DOCS_DIR,
            )

            VECTOR_BACKEND_ACTIVE = "hash"

            return searcher

    # --------------------------------------------------------
    # Hash fallback
    # --------------------------------------------------------
    searcher = VectorSearch(
        docs_dir=DOCS_DIR,
    )

    VECTOR_BACKEND_ACTIVE = "hash"
    VECTOR_BACKEND_ERROR = None

    print(
        "[VectorSearch] "
        "Hash 后端启动成功"
    )

    print(
        "[VectorSearch] "
        f"Docs: {DOCS_DIR}"
    )

    return searcher


vector_search = _build_vector_search()


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
    - Vector Backend
    - Milvus 配置
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
            "version": "0.2.0",
        },

        # --------------------------------
        # Graph
        # --------------------------------
        "graph": {
            "source": GRAPH_SOURCE,
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
            "requested_backend": (
                VECTOR_BACKEND_REQUESTED
            ),
            "active_backend": (
                VECTOR_BACKEND_ACTIVE
            ),
            "fallback_occurred": (
                VECTOR_BACKEND_REQUESTED
                != VECTOR_BACKEND_ACTIVE
            ),
            "error": (
                VECTOR_BACKEND_ERROR
            ),
        },

        # --------------------------------
        # Milvus
        # --------------------------------
        "milvus": {
            "uri": MILVUS_URI,
            "collection": (
                MILVUS_COLLECTION
            ),
            "active": (
                VECTOR_BACKEND_ACTIVE
                == "milvus"
            ),
        },

        # --------------------------------
        # LLM
        # --------------------------------
        "llm": {
            "enabled": LLM_ENABLED,
            "model": LLM_MODEL,
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

    主要用于：
    - 团队联调
    - 页面调试
    - 环境确认
    """
    config = get_runtime_config()

    config.update(
        {
            "vector_backend_requested": (
                VECTOR_BACKEND_REQUESTED
            ),
            "vector_backend_active": (
                VECTOR_BACKEND_ACTIVE
            ),
            "vector_backend_error": (
                VECTOR_BACKEND_ERROR
            ),
        }
    )

    return config


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
          ├───────────────┐
          ↓               ↓
      GraphSearch     VectorSearch
          ↓               ↓
      Graph Paths     Milvus Top-K
          │               │
          └───────┬───────┘
                  ↓
          Evidence Fusion
                  ↓
              DeepSeek
                  ↓
              QAResult

    输出严格遵守组长统一问答格式。
    """
    return graphrag_service.query(
        request
    )