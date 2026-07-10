from pydantic import BaseModel, Field


class SQLAgentRequest(BaseModel):
    question: str = Field("查询图谱实体统计", description="结构化查询问题")
    syndromes: list[str] = Field(default_factory=list)
    formulas: list[str] = Field(default_factory=list)
