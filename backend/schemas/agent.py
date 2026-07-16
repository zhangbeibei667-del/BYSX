from pydantic import BaseModel, Field


class CaseAnalyzeRequest(BaseModel):
    case_text: str = Field(..., min_length=1, description="病例文本或症状描述")


class AgentChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
