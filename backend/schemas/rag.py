from pydantic import BaseModel, Field


class RAGSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="检索关键词或问题")
    case_text: str = Field("", description="可选病例文本")
    syndromes: list[str] = Field(default_factory=list)
    formulas: list[str] = Field(default_factory=list)
    top_k: int = Field(5, ge=1, le=20)
