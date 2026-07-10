"""
统一数据契约 —— 严格对应小组约定的四张图。
任务 1/3/4/5 都可直接 import 这个文件
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# ---------- 1. 固定词表 ----------
ENTITY_TYPES: List[str] = ["药材", "方剂", "症状", "证候", "功效", "禁忌", "文献"]
RELATION_TYPES: List[str] = ["包含", "主治", "提示", "对应", "具有", "禁忌", "来源于", "记载"]

# ID 前缀约定（图里已出现 H/F/S/Z，其余三类由本模块补齐，全组沿用）
TYPE_PREFIX: Dict[str, str] = {
    "药材": "H",   # Herb
    "方剂": "F",   # Formula
    "症状": "S",   # Symptom
    "证候": "Z",   # Zhenghou
    "功效": "G",   # Gongxiao
    "禁忌": "J",   # Jinji
    "文献": "W",   # Wenxian
}
PREFIX_TYPE: Dict[str, str] = {v: k for k, v in TYPE_PREFIX.items()}

# 关系的 定义域 -> 值域 约束。录入/导入时校验，防止脏数据。
RELATION_SCHEMA: Dict[str, List[tuple]] = {
    "包含":   [("方剂", "药材")],
    "主治":   [("方剂", "症状"), ("方剂", "证候"), ("药材", "症状"), ("药材", "证候")],
    "提示":   [("症状", "证候")],
    "对应":   [("证候", "方剂")],
    "具有":   [("药材", "功效"), ("方剂", "功效")],
    "禁忌":   [("药材", "禁忌"), ("方剂", "禁忌")],
    "来源于": [("方剂", "文献"), ("药材", "文献")],
    "记载":   [("文献", "方剂"), ("文献", "药材"), ("文献", "证候"), ("文献", "症状")],
}


# ---------- 2. 实体（图 1） ----------
class Entity(BaseModel):
    id: str = Field(..., examples=["F001"])
    name: str = Field(..., examples=["归脾汤"])
    type: str = Field(..., examples=["方剂"])
    alias: str = ""
    description: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)


class EntityCreate(BaseModel):
    """id 可不传，由后端按类型前缀自动分配。"""
    id: Optional[str] = None
    name: str
    type: str
    alias: str = ""
    description: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    alias: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


# ---------- 3. 关系（图 2） ----------
class Relation(BaseModel):
    source_id: str
    source_name: str = ""
    relation: str
    target_id: str
    target_name: str = ""
    evidence: str = ""


class RelationCreate(BaseModel):
    """source/target 允许只给 name，后端按名字解析成 id。"""
    source_id: Optional[str] = None
    source_name: Optional[str] = None
    relation: str
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    evidence: str = ""


# ---------- 4. 图谱返回（图 3） ----------
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


# ---------- 5. 问答返回（图 4）—— 任务 3/4 用，放这里保证全组一致 ----------
class EvidenceItem(BaseModel):
    title: str
    content: str



class QAResult(BaseModel):
    answer: str = ""
    symptoms: List[str] = Field(default_factory=list)
    syndromes: List[str] = Field(default_factory=list)
    formulas: List[str] = Field(default_factory=list)
    herbs: List[str] = Field(default_factory=list)
    graph: GraphData = Field(default_factory=GraphData)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    safety_notice: str = "本结果仅用于中医药知识学习和教学辅助，不构成医疗诊断或用药建议。"


# ---------- 6. 统一 HTTP 响应外壳 ----------
class ApiResponse(BaseModel):
    code: int = 0          # 0 = 成功，非 0 = 业务错误
    msg: str = "ok"
    data: Any = None


class PageData(BaseModel):
    total: int
    page: int
    size: int
    items: List[Any]


class ImportError_(BaseModel):
    row: int
    reason: str


class ImportResult(BaseModel):
    total: int = 0
    success: int = 0
    failed: int = 0
    errors: List[ImportError_] = Field(default_factory=list)


# ---------- 7. 校验工具 ----------
def validate_entity_type(t: str) -> None:
    if t not in ENTITY_TYPES:
        raise ValueError(f"实体类型必须是 {ENTITY_TYPES} 之一，收到：{t}")


def validate_relation(rel: str, src_type: str, tgt_type: str) -> None:
    if rel not in RELATION_TYPES:
        raise ValueError(f"关系类型必须是 {RELATION_TYPES} 之一，收到：{rel}")
    allowed = RELATION_SCHEMA[rel]
    if (src_type, tgt_type) not in allowed:
        raise ValueError(
            f"关系「{rel}」不允许 {src_type} → {tgt_type}；允许：" +
            "、".join(f"{a}→{b}" for a, b in allowed)
        )
