from fastapi import APIRouter

from backend.schemas.rag import RAGSearchRequest
from backend.services.rag_service import RAGService


router = APIRouter(prefix="/api/rag", tags=["RAG"])


@router.post("/search")
def search_documents(request: RAGSearchRequest) -> dict:
    service = RAGService()
    return service.search(
        query=request.query,
        case_text=request.case_text,
        syndromes=request.syndromes,
        formulas=request.formulas,
        top_k=request.top_k,
    )
