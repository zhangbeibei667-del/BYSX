from pydantic import BaseModel, Field


class SQLAgentRequest(BaseModel):
    question: str = Field("查询图谱实体统计", description="自然语言查询问题")
    syndromes: list[str] = Field(default_factory=list, description="已知证候列表")
    formulas: list[str] = Field(default_factory=list, description="已知方剂列表")


class SQLDirectRequest(BaseModel):
    sql: str = Field(..., description="直接执行的 SQL 语句（只允许 SELECT/WITH）")
    params: list = Field(default_factory=list, description="SQL 参数绑定")
