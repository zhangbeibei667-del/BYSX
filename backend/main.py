from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.agent_api import router as agent_router
from backend.api.document_api import router as document_router
from backend.api.health_api import router as health_router
from backend.api.history_api import router as history_router
from backend.api.frontend_compat_api import router as frontend_compat_router
from backend.api.rag_api import router as rag_router
from backend.api.sql_api import router as sql_router
from backend.db.database import init_db


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


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(agent_router)
app.include_router(rag_router)
app.include_router(sql_router)
app.include_router(document_router)
app.include_router(history_router)
app.include_router(health_router)
app.include_router(frontend_compat_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
