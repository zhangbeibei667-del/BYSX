"""
统一数据契约 —— 类型/前缀/关系域全部从数据动态发现，不硬编码。
任务 1 新增类型只需放数据文件，零协调成本。
"""
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

# ---------- 已知的基础关系约束（自动扩展，新组合只警告不拒绝） ----------
_BASE_RELATION_SCHEMA: Dict[str, List[tuple]] = {
    "包含":   [("方剂", "药材")],
    "主治":   [("方剂", "症状"), ("方剂", "证候"), ("药材", "症状"), ("药材", "证候")],
    "提示":   [("症状", "证候")],
    "对应":   [("证候", "方剂")],
    "具有":   [("药材", "功效"), ("方剂", "功效")],
    "禁忌":   [("药材", "禁忌"), ("方剂", "禁忌")],
    "来源于": [
        ("药材", "文献"), ("方剂", "文献"),
        ("症状", "文献"), ("证候", "文献"),
        ("功效", "文献"), ("禁忌", "文献"),
    ],
    "记载": [
        ("文献", "方剂"), ("文献", "药材"),
        ("文献", "证候"), ("文献", "症状"),
        ("文献", "功效"), ("文献", "禁忌"),
    ],
}


# ---------- 已知类型前缀（新增类型自动生成） ----------
_BASE_TYPE_PREFIX: Dict[str, str] = {
    "药材": "H", "方剂": "F", "症状": "S", "证候": "Z",
    "功效": "G", "禁忌": "J", "文献": "W",
}


def get_type_prefixes() -> Dict[str, str]:
    """返回当前所有类型→前缀映射。先取已知，再从数据库补。"""
    result = dict(_BASE_TYPE_PREFIX)
    try:
        from config import get_store  # 懒加载避免循环导入
        store = get_store()
        if hasattr(store, "list_type_prefixes"):
            for tp in store.list_type_prefixes():
                result.setdefault(tp["type"], tp["prefix"])
    except Exception:
        pass
    return result


def auto_prefix(type_name: str) -> str:
    """根据类型名自动生成 ASCII 字母前缀。永不会返回中文。"""
    existing = set(get_type_prefixes().values())
    # 26 个字母中未被占用的
    free_letters = [chr(c) for c in range(ord('A'), ord('Z') + 1)
                    if chr(c) not in existing]
    # 拼音映射（按类型名的字顺序尝试）
    pinyin_map = {
        "疾": "J", "病": "B", "治": "Z", "法": "F", "经": "J",
        "络": "L", "归": "G", "性": "X", "味": "W", "剂": "J",
        "量": "L", "配": "P", "角": "J", "色": "S",
    }
    # ① 按类型名逐字尝试拼音映射
    for char in type_name:
        letter = pinyin_map.get(char)
        if letter and letter in free_letters:
            return letter
    # ② 映射命中了但被占用 → 从 free_letters 里挑第一个
    if free_letters:
        return free_letters[0]
    # ③ 全部 26 个字母被占用 → 双字母
    for a in range(ord('A'), ord('Z') + 1):
        for b in range(ord('A'), ord('Z') + 1):
            prefix = chr(a) + chr(b)
            if prefix not in existing:
                return prefix
    return "XX"  # 理论上不可能走到这里


_RELATION_CONFIDENCE_LEVELS = ["A_权威教材", "B_药典标准", "C_研究文献", "D_经验总结", "E_待验证"]
_REVIEW_STATUSES = ["draft", "reviewed", "approved"]


# ---------- 实体 ----------
class Entity(BaseModel):
    id: str = Field(..., examples=["F001"])
    name: str = Field(..., examples=["归脾汤"])
    type: str = Field(..., examples=["方剂"])
    alias: str = ""
    description: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)


class EntityCreate(BaseModel):
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


# ---------- 关系（含组长要求的置信度/证据等级/版本/审核字段） ----------
class Relation(BaseModel):
    source_id: str
    source_name: str = ""
    relation: str
    target_id: str
    target_name: str = ""
    evidence: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_level: str = Field(default="C_研究文献")
    version: str = Field(default="1.0")
    review_status: str = Field(default="draft")


class RelationCreate(BaseModel):
    source_id: Optional[str] = None
    source_name: Optional[str] = None
    relation: str
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    evidence: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_level: str = Field(default="C_研究文献")
    version: str = Field(default="1.0")
    review_status: str = Field(default="draft")


# ---------- 图谱 ----------
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


# ---------- 问答（已删除，图谱查询请用 GraphData） ----------


# ---------- 统一 HTTP 响应 ----------
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


# ---------- 动态校验（不再拒绝未知类型） ----------
def _discovered_entity_types() -> List[str]:
    """从数据库中自动发现所有实体类型。"""
    try:
        from config import get_store
        store = get_store()
        stats = store.stats()
        return sorted(stats.get("entity_by_type", {}).keys())
    except Exception:
        return list(_BASE_TYPE_PREFIX.keys())


def _discovered_relation_types() -> List[str]:
    """从数据库中自动发现所有关系类型。"""
    try:
        from config import get_store
        store = get_store()
        stats = store.stats()
        return sorted(stats.get("relation_by_type", {}).keys())
    except Exception:
        return list(_BASE_RELATION_SCHEMA.keys())


def get_entity_types() -> List[str]:
    """实体类型：数据库中已有 + 已知基础。"""
    return sorted(set(_discovered_entity_types()) | set(_BASE_TYPE_PREFIX.keys()))


def get_relation_types() -> List[str]:
    """关系类型：数据库中已有 + 已知基础。"""
    return sorted(set(_discovered_relation_types()) | set(_BASE_RELATION_SCHEMA.keys()))


def get_relation_schema() -> Dict[str, List[tuple]]:
    """关系域约束：已知 + 动态扩展。未知组合自动加入并标记来源。"""
    result = dict(_BASE_RELATION_SCHEMA)
    discovered_src_types = set(_discovered_entity_types())
    discovered_tgt_types = set(_discovered_entity_types())
    # 为所有已知关系类型，把未覆盖的 (src_type, tgt_type) 加入为允许
    for rel in list(result.keys()):
        existing_pairs = set(result[rel])
        for st in discovered_src_types:
            for tt in discovered_tgt_types:
                if (st, tt) not in existing_pairs:
                    result[rel].append((st, tt))
    return result


def validate_entity_type(t: str) -> None:
    """校验实体类型，未知类型只警告不拒绝。"""
    known = set(get_entity_types())
    if t not in known:
        import sys
        print(f"[schemas] 新实体类型「{t}」未在已知列表中，自动接受", file=sys.stderr)


def validate_relation(rel: str, src_type: str, tgt_type: str, strict: bool = False) -> None:
    """校验关系域。strict=False 时未知组合只警告不拒绝。"""
    known_rels = set(get_relation_types())
    if rel not in known_rels:
        # 新关系类型 → 自动接受
        import sys
        print(f"[schemas] 新关系类型「{rel}」未在已知列表中，自动接受", file=sys.stderr)
        return
    schema = get_relation_schema()
    allowed = schema.get(rel, [])
    if not allowed:
        return  # 没有约束，全接受
    if (src_type, tgt_type) not in allowed:
        msg = (
            f"关系「{rel}」: {src_type} → {tgt_type} 不在已知约束中"
        )
        if strict:
            raise ValueError(msg)
        import sys
        print(f"[schemas] {msg}，自动接受", file=sys.stderr)
