from fastapi import APIRouter, HTTPException, Query

from backend.services.history_service import HistoryService


router = APIRouter(prefix="/api/history", tags=["History"])


@router.get("")
def list_history(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    service = HistoryService()
    return {"items": service.list_history(limit=limit, offset=offset)}


@router.get("/{history_id}")
def get_history(history_id: int) -> dict:
    service = HistoryService()
    history = service.get_history(history_id)
    if history is None:
        raise HTTPException(status_code=404, detail="History not found")
    return history


@router.delete("/{history_id}")
def delete_history(history_id: int) -> dict:
    service = HistoryService()
    deleted = service.delete_history(history_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="History not found")
    return {"deleted": True, "id": history_id}
