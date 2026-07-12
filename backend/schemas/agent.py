from pydantic import BaseModel, Field


class CaseAnalyzeRequest(BaseModel):
    case_text: str = Field(..., min_length=1, description="病例文本或症状描述")
