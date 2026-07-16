"""中医药知识图谱的统一数据契约与严格关系约束。"""

from __future__ import annotations

import re
import sys
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


ENTITY_TYPE_PREFIX: Dict[str, str] = {
    "药材": "H",
    "方剂": "F",
    "症状": "S",
    "证候": "Z",
    "功效": "G",
    "禁忌": "J",
    "文献": "L",
    "疾病": "D",
    "归经": "M",
    "性味": "T",
}

# 方向固定。严格模式下，不在此表中的关系或端点组合一律拒绝。
RELATION_SCHEMA: Dict[str, List[tuple[str, str]]] = {
    "包含": [("方剂", "药材")],
    "主治": [
        ("方剂", "症状"), ("方剂", "证候"), ("方剂", "疾病"),
        ("药材", "症状"), ("药材", "证候"), ("药材", "疾病"),
    ],
    "提示": [("症状", "证候")],
    "对应": [("证候", "方剂")],
    "常见证候": [("疾病", "证候")],
    "具有": [("药材", "功效"), ("方剂", "功效"), ("药材", "性味")],
    "性味": [("药材", "性味")],
    "归经": [("药材", "归经"), ("方剂", "归经")],
    "禁忌": [
        ("药材", "禁忌"), ("药材", "证候"), ("药材", "症状"),
        ("方剂", "禁忌"), ("方剂", "证候"), ("方剂", "症状"),
    ],
    "来源于": [
        ("药材", "文献"), ("方剂", "文献"), ("症状", "文献"),
        ("证候", "文献"), ("功效", "文献"), ("禁忌", "文献"),
        ("疾病", "文献"), ("归经", "文献"), ("性味", "文献"),
    ],
    "记载": [
        ("文献", "方剂"), ("文献", "药材"), ("文献", "证候"),
        ("文献", "症状"), ("文献", "功效"), ("文献", "禁忌"),
        ("文献", "疾病"),
    ],
}

EvidenceLevel = Literal["A_权威教材", "B_药典标准", "C_研究文献", "D_经验总结", "E_待验证"]
ReviewStatus = Literal["draft", "reviewed", "approved"]


def _not_blank(value: str, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} 不能为空")
    return value


class Entity(BaseModel):
    id: str = Field(..., min_length=2, max_length=32, examples=["F001"])
    name: str = Field(..., min_length=1, max_length=200, examples=["归脾汤"])
    type: str = Field(..., min_length=1, max_length=50, examples=["方剂"])
    alias: str = Field(default="", max_length=500)
    description: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        value = _not_blank(value, "id")
        if not re.fullmatch(r"[A-Z][A-Z0-9_-]{1,31}", value):
            raise ValueError("id 必须以大写英文字母开头，且只能包含大写字母、数字、下划线或连字符")
        return value

    @field_validator("name", "type")
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        return _not_blank(value, info.field_name)

    @model_validator(mode="after")
    def validate_prefix(self):
        prefix = ENTITY_TYPE_PREFIX.get(self.type)
        if prefix and not self.id.startswith(prefix):
            raise ValueError(f"{self.type}实体 ID 必须以 {prefix} 开头")
        return self


class EntityCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., min_length=1, max_length=50)
    alias: str = Field(default="", max_length=500)
    description: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "type")
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        return _not_blank(value, info.field_name)


class EntityUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    alias: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class Relation(BaseModel):
    source_id: str = Field(..., min_length=2, max_length=32)
    source_name: str = ""
    relation: str = Field(..., min_length=1, max_length=50)
    target_id: str = Field(..., min_length=2, max_length=32)
    target_name: str = ""
    evidence: str = ""
    evidence_level: EvidenceLevel = "E_待验证"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    locator: Dict[str, str] = Field(default_factory=dict)
    excerpt: str = ""
    version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    review_status: ReviewStatus = "draft"

    @field_validator("source_id", "target_id", "relation")
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        return _not_blank(value, info.field_name)

    @model_validator(mode="after")
    def validate_relation_record(self):
        if self.source_id == self.target_id:
            raise ValueError("不允许自环关系")
        if self.review_status in {"reviewed", "approved"} and not self.evidence.strip():
            raise ValueError(f"{self.review_status} 关系必须填写 evidence")
        return self


class RelationCreate(BaseModel):
    source_id: Optional[str] = None
    source_name: Optional[str] = None
    relation: str = Field(..., min_length=1, max_length=50)
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    evidence: str = ""
    evidence_level: EvidenceLevel = "E_待验证"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    locator: Dict[str, str] = Field(default_factory=dict)
    excerpt: str = ""
    version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    review_status: ReviewStatus = "draft"

    @field_validator("relation")
    @classmethod
    def validate_relation_name(cls, value: str) -> str:
        return _not_blank(value, "relation")

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.review_status in {"reviewed", "approved"} and not self.evidence.strip():
            raise ValueError(f"{self.review_status} 关系必须填写 evidence")
        if not (self.source_id or self.source_name):
            raise ValueError("source_id 和 source_name 至少填写一个")
        if not (self.target_id or self.target_name):
            raise ValueError("target_id 和 target_name 至少填写一个")
        return self


class GraphNode(BaseModel):
    id: str
    label: str
    type: str


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str


class GraphData(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class ApiResponse(BaseModel):
    code: int = 0
    msg: str = "ok"
    data: Any = None


class ImportError_(BaseModel):
    row: int
    reason: str


class ImportResult(BaseModel):
    total: int = 0
    success: int = 0
    failed: int = 0
    errors: List[ImportError_] = Field(default_factory=list)


def get_type_prefixes() -> Dict[str, str]:
    result = dict(ENTITY_TYPE_PREFIX)
    try:
        from server.config import get_store
        store = get_store()
        if hasattr(store, "list_type_prefixes"):
            for item in store.list_type_prefixes():
                result.setdefault(item["type"], item["prefix"])
    except Exception:
        pass
    return result


def auto_prefix(type_name: str) -> str:
    existing = set(get_type_prefixes().values())
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if letter not in existing:
            return letter
    for first in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        for second in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            prefix = first + second
            if prefix not in existing:
                return prefix
    return "XX"


def get_entity_types() -> List[str]:
    return sorted(ENTITY_TYPE_PREFIX)


def get_relation_types() -> List[str]:
    return sorted(RELATION_SCHEMA)


def get_relation_schema() -> Dict[str, List[tuple[str, str]]]:
    return {name: list(pairs) for name, pairs in RELATION_SCHEMA.items()}


def validate_entity_type(entity_type: str, strict: bool = False) -> None:
    entity_type = _not_blank(entity_type, "type")
    if entity_type in ENTITY_TYPE_PREFIX:
        return
    message = f"未知实体类型：{entity_type}"
    if strict:
        raise ValueError(message)
    print(f"[schemas] {message}，非严格模式下接受", file=sys.stderr)


def validate_relation(
    relation: str,
    source_type: str,
    target_type: str,
    strict: bool = False,
) -> None:
    relation = _not_blank(relation, "relation")
    allowed = RELATION_SCHEMA.get(relation)
    if allowed is None:
        message = f"未知关系类型：{relation}"
    elif (source_type, target_type) not in allowed:
        message = f"关系“{relation}”不允许 {source_type} → {target_type}"
    else:
        return
    if strict:
        raise ValueError(message)
    print(f"[schemas] {message}，非严格模式下接受", file=sys.stderr)
