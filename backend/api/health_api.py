from fastapi import APIRouter

from backend.db.database import DB_PATH
from backend.services.llm_client import get_llm_client


router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "service": "tcm-kg-agent-backend",
        "database": str(DB_PATH),
        "llm": get_llm_client().status(),
    }
