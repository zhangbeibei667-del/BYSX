from fastapi import APIRouter

from backend.schemas.sql import SQLAgentRequest
from backend.services.sql_service import SQLService


router = APIRouter(prefix="/api/sql", tags=["Graph SQL Agent"])


@router.post("/query")
def query_graph_data(request: SQLAgentRequest) -> dict:
    service = SQLService()
    return service.query(
        question=request.question,
        syndromes=request.syndromes,
        formulas=request.formulas,
    )


@router.get("/statistics")
def get_graph_statistics() -> dict:
    service = SQLService()
    return service.query(question="查询图谱实体统计")
