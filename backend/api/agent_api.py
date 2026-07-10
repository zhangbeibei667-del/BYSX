from fastapi import APIRouter

from backend.schemas.agent import CaseAnalyzeRequest
from backend.services.agent_service import AgentService


router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post("/case")
def analyze_case(request: CaseAnalyzeRequest) -> dict:
    service = AgentService()
    return service.analyze_case(request.case_text)
