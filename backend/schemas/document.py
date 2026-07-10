from pydantic import BaseModel, Field


class DocumentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    source: str = ""
    content: str = ""


class DocumentUpdateRequest(BaseModel):
    title: str | None = None
    source: str | None = None
    content: str | None = None
