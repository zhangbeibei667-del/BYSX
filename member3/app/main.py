"""成员 3 兼容入口。

正式运行时只调用 backend 的统一 RAGService，member3 保留语料处理、Milvus
导入与评测脚本，不再维护第二套在线 GraphRAG 业务逻辑。
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.rag_service import RAGService
from backend.services.rag_runtime_service import runtime_report
from member3.app.schemas import GraphRAGQueryRequest


app = FastAPI(
    title="TCM GraphRAG - compatibility adapter",
    version="1.0.0",
    description="兼容旧成员 3 路由；核心检索已统一到 backend.services.rag_service.RAGService。",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/api/graphrag/health")
def health() -> dict:
    report = runtime_report()
    return {"status": "ok" if report["passed"] else "degraded", "adapter": True,
            "primary_service": report["primary_service"], "runtime": report}


@app.get("/api/graphrag/config")
def runtime_config() -> dict:
    report = runtime_report()
    return {"primary_service": report["primary_service"], "qdrant": report["qdrant"],
            "milvus": report["milvus"], "llm": report["llm"]}


@app.post("/api/graphrag/query")
def graphrag_query(request: GraphRAGQueryRequest) -> dict:
    return RAGService().search(query=request.query, top_k=request.top_k)
