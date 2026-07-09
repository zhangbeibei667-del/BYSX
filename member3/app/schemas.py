from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# 1. 统一实体格式 
# ============================================================
class EntityRecord(BaseModel):
    id: str
    name: str
    type: str
    alias: str = ""
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# 2. 统一关系格式 
# ============================================================
class RelationRecord(BaseModel):
    source_id: str
    source_name: str
    relation: str
    target_id: str
    target_name: str
    evidence: str = ""


# ============================================================
# 3. 统一图谱返回格式 —— 前端直接读取 nodes / edges
# ============================================================
class GraphNode(BaseModel):
    id: str
    label: str
    type: str


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str


class GraphData(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# ============================================================
# 4. 统一问答结果格式 
# ============================================================
class EvidenceItem(BaseModel):
    title: str
    content: str


class QAResult(BaseModel):
    answer: str
    symptoms: list[str] = Field(default_factory=list)
    syndromes: list[str] = Field(default_factory=list)
    formulas: list[str] = Field(default_factory=list)
    herbs: list[str] = Field(default_factory=list)
    graph: GraphData = Field(default_factory=GraphData)
    evidence: list[EvidenceItem] = Field(default_factory=list)

    follow_up_questions: list[str] = Field(default_factory=list)

    safety_notice: str = (
        "本结果仅用于中医药知识学习和教学辅助，"
        "不构成医疗诊断或用药建议。"
    )


# GraphRAG 查询接口请求体
class GraphRAGQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=20)
    max_hops: int = Field(default=2, ge=1, le=3)
