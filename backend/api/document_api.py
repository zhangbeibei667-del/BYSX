from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from backend.schemas.document import DocumentCreateRequest, DocumentUpdateRequest
from backend.services.document_service import DocumentService


router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("")
def create_document(request: DocumentCreateRequest) -> dict:
    service = DocumentService()
    return service.create_document(
        title=request.title,
        source=request.source,
        content=request.content,
    )


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), source: str = "") -> dict:
    service = DocumentService()
    return await service.upload_document(file=file, source=source)


@router.get("")
def list_documents(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    service = DocumentService()
    return {"items": service.list_documents(limit=limit, offset=offset)}


@router.get("/{document_id}")
def get_document(document_id: int) -> dict:
    service = DocumentService()
    document = service.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.put("/{document_id}")
def update_document(document_id: int, request: DocumentUpdateRequest) -> dict:
    service = DocumentService()
    document = service.update_document(
        document_id=document_id,
        title=request.title,
        source=request.source,
        content=request.content,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}")
def delete_document(document_id: int) -> dict:
    service = DocumentService()
    deleted = service.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "id": document_id}
