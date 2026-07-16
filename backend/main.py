from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.agent_api import router as agent_router
from backend.api.document_api import router as document_router
from backend.api.health_api import router as health_router
from backend.api.history_api import router as history_router
from backend.api.frontend_compat_api import router as frontend_compat_router
from backend.api.rag_api import router as rag_router
from backend.api.sql_api import router as sql_router
from backend.db.database import init_db
from server.api import router as graph_management_router
from server.bootstrap import initialize_graph_management
from server.auth import decode_token
from backend.services.rag_runtime_service import ensure_rag_initialized


app = FastAPI(
    title="基于知识图谱的中医药诊疗智能体",
    description="FastAPI backend integration for existing TCM teaching multi-agent module.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def protect_management_apis(request: Request, call_next):
    """兼容管理接口也必须由后端验证管理员身份，不能只依赖 Vue 路由守卫。"""
    path = request.url.path
    if path.startswith("/api/admin/") or path.startswith("/api/documents"):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "请先登录"})
        try:
            user = decode_token(authorization[7:])
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        if user.get("role") != "admin":
            return JSONResponse(status_code=403, content={"detail": "权限不足，需要管理员"})
    return await call_next(request)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    initialize_graph_management()
    ensure_rag_initialized()


app.include_router(agent_router)
app.include_router(rag_router)
app.include_router(sql_router)
app.include_router(document_router)
app.include_router(history_router)
app.include_router(health_router)
app.include_router(frontend_compat_router)
app.include_router(graph_management_router)

GRAPH_VIEWER = Path(__file__).resolve().parent.parent / "view" / "graph_viewer.html"


@app.get("/kg-viewer", include_in_schema=False)
def graph_viewer() -> FileResponse:
    return FileResponse(GRAPH_VIEWER)

FRONTEND_SOURCE = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_DIR = FRONTEND_SOURCE / "dist" if (FRONTEND_SOURCE / "dist" / "index.html").exists() else FRONTEND_SOURCE
app.mount("/static", StaticFiles(directory=FRONTEND_SOURCE), name="static")
if (FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="frontend-assets")


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{spa_path:path}", include_in_schema=False)
def frontend_routes(spa_path: str) -> FileResponse:
    """支持 Vue history 路由刷新，同时不吞掉未知 API。"""
    if spa_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    candidate = FRONTEND_DIR / spa_path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(FRONTEND_DIR / "index.html")
