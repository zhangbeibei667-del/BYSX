from __future__ import annotations

import json
import re

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.schemas.agent import AgentChatRequest, CaseAnalyzeRequest
from backend.services.agent_service import AgentService
from backend.services.conversation_service import ConversationService


router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post("/case")
def analyze_case(request: CaseAnalyzeRequest) -> dict:
    return AgentService().analyze_case(request.case_text)


@router.post("/chat")
def agent_chat(request: AgentChatRequest) -> dict:
    return AgentService().chat(request.question, request.session_id)


@router.get("/chat/stream")
def agent_chat_stream(question: str, session_id: str | None = None) -> StreamingResponse:
    result = AgentService().chat(question, session_id)
    answer = result.get("answer", "")

    def events():
        sentences = [item for item in re.split(r"(?<=[。！？!?])", answer) if item]
        yield f"data: {json.dumps({'type': 'meta', 'conversation': result.get('conversation', {}), 'agent_plan': result.get('agent_plan', {})}, ensure_ascii=False)}\n\n"
        for index, sentence in enumerate(sentences):
            yield f"data: {json.dumps({'type': 'chunk', 'index': index, 'content': sentence, 'speak': True}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'result', 'content': answer, 'result': result}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations")
def conversations(page: int = 1, page_size: int = 20) -> dict:
    return ConversationService().list(page, page_size)


@router.get("/conversations/{session_id}")
def conversation(session_id: str) -> dict:
    return ConversationService().load(session_id)


@router.delete("/conversations/{session_id}")
def delete_conversation(session_id: str) -> dict:
    return {"deleted": ConversationService().delete(session_id)}
