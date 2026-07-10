from pydantic import BaseModel, Field


class HistoryListQuery(BaseModel):
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
