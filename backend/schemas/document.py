from pydantic import BaseModel, Field


class DocumentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    source: str = ""
    content: str = ""
    category: str = Field("未分类", pattern="^(教材|药典|方剂说明|科普资料|论文|未分类)$")
    edition: str = ""
    chapter: str = ""
    section: str = ""
    publisher: str = ""
    identifier: str = ""
    source_url: str = ""
    license: str = ""


class DocumentUpdateRequest(BaseModel):
    title: str | None = None
    source: str | None = None
    content: str | None = None
    category: str | None = None
    edition: str | None = None
    chapter: str | None = None
    section: str | None = None
    publisher: str | None = None
    identifier: str | None = None
    source_url: str | None = None
    license: str | None = None
