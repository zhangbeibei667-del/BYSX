from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    APP_HOST,
    APP_PORT,
    DOCS_DIR,
    ENTITIES_PATH,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_ENABLED,
    LLM_MODEL,
    RELATIONS_PATH,
)
from app.graph_search import GraphSearch
from app.graphrag_service import GraphRAGService
from app.llm_client import LLMClient
from app.schemas import GraphRAGQueryRequest, QAResult
from app.vector_search import VectorSearch


app = FastAPI(
    title="TCM GraphRAG - Member 3",
    version="0.1.0",
    description="成员 3 精简版 GraphRAG：文本检索 + 图谱路径 + 证据融合",
)

# 联调阶段允许跨域，方便成员 5 前端直接访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 在应用启动时一次性创建核心组件
# 项目规模较小，不再单独拆 dependencies.py
# ============================================================
graph_search = GraphSearch(
    entities_path=ENTITIES_PATH,
    relations_path=RELATIONS_PATH,
)

vector_search = VectorSearch(
    docs_dir=DOCS_DIR,
)

llm_client = None

if LLM_ENABLED:
    llm_client = LLMClient(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
    )

graphrag_service = GraphRAGService(
    vector_search=vector_search,
    graph_search=graph_search,
    llm_client=llm_client,
)


@app.get("/api/graphrag/health")
def health() -> dict:
    """成员 4/5 联调前可先检查服务是否正常。"""
    return {
        "status": "ok",
        "llm_enabled": LLM_ENABLED,
        "host": APP_HOST,
        "port": APP_PORT,
    }


@app.post(
    "/api/graphrag/query",
    response_model=QAResult,
)
def graphrag_query(
    request: GraphRAGQueryRequest,
) -> QAResult:
    """
    成员 3 核心接口。

    输入：
    - query
    - top_k
    - max_hops

    输出：
    - 严格使用组长统一问答结果格式
    """
    return graphrag_service.query(request)
