"""Graph SQL Agent API — unified NL→SQL and direct-SQL endpoint.

Replaces the old server-side /api/sql/* endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.schemas.sql import SQLAgentRequest, SQLDirectRequest
from backend.services.sql_service import SQLService

router = APIRouter(prefix="/api/sql", tags=["Graph SQL Agent"])


# ---------------------------------------------------------------------------
# Natural-language → SQL
# ---------------------------------------------------------------------------

@router.post("/query")
def query_graph_data(request: SQLAgentRequest) -> dict:
    """Translate a natural-language question into SQL, execute it, and return results.

    Supports questions like:
    - "归脾汤由哪些药材组成？"
    - "治疗失眠的方剂有哪些？"
    - "具有清热功效的药材有哪些？"
    - "人参有哪些禁忌？"
    """
    service = SQLService()
    return service.query(
        question=request.question,
        syndromes=request.syndromes,
        formulas=request.formulas,
    )


# ---------------------------------------------------------------------------
# Direct SQL execution (admin / debug)
# ---------------------------------------------------------------------------

@router.post("/direct")
def execute_direct_sql(request: SQLDirectRequest) -> dict:
    """Execute a hand-written SQL statement directly (read-only, safety-validated).

    The SQL is still validated by the same safety layer as the NL path.
    """
    service = SQLService()
    try:
        result = service.execute_direct_sql(request.sql, request.params)
        return result
    except ValueError as exc:
        return {"status": "rejected", "error": str(exc)}


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

@router.get("/schema")
def get_schema() -> dict:
    """Return the current knowledge-graph database schema.

    Includes table structures, entity/relation type enumerations, and row counts.
    """
    service = SQLService()
    return service.get_schema()


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

@router.get("/statistics")
def get_graph_statistics(refresh: bool = Query(False)) -> dict:
    """Return knowledge-graph statistics (entity counts, relation counts, etc.).

    Set refresh=true to force a database re-sync before gathering stats.
    """
    service = SQLService()
    return service.get_statistics(refresh=refresh)


@router.post("/refresh")
def refresh_database() -> dict:
    """Force a full database re-sync and schema cache refresh."""
    service = SQLService()
    return service.refresh()
