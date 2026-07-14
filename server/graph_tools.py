"""
任务 2 对内暴露的「图谱查询工具」。
任务 3 (RAG) 和任务 4 (Agent) 直接 import 这里的函数，
或者用文件底部的 HTTP 版本跨进程调用，两者返回结构完全一样。

Agent 侧可以把这四个函数直接注册成 tool：
    search_entities / get_entity_detail / get_subgraph / explain_path
"""
from typing import Any, Dict, List, Optional

import requests

try:
    from .config import get_store
    from .service import GraphService
except ImportError:
    from config import get_store
    from service import GraphService


def _svc() -> GraphService:
    return GraphService(get_store())


# ---------------- 进程内调用（推荐，最快） ----------------
def search_entities(keyword: str, type_: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
    """按关键词找实体。用于把用户问句里的『失眠』『归脾汤』对齐到图谱节点。"""
    _, items = _svc().list_entities(type_, keyword, 1, top_k)
    return [e.model_dump() for e in items]


def get_entity_detail(entity_id: str) -> Optional[Dict[str, Any]]:
    e = _svc().get_entity(entity_id)
    return e.model_dump() if e else None


def get_subgraph(entity_id: str, depth: int = 2) -> Dict[str, Any]:
    """返回图 3 格式 {nodes, edges}，可以直接塞进 QAResult.graph。"""
    return _svc().subgraph(entity_id, depth).model_dump()


def explain_path(source_id: str, target_id: str, max_depth: int = 4) -> List[Dict[str, Any]]:
    """
    返回可读推理路径，例如：
      "失眠 -提示-> 心脾两虚 -对应-> 归脾汤 -包含-> 酸枣仁"
    这段字符串就是 RAG 提示词里的『关系路径依据』。
    """
    return _svc().find_paths(source_id, target_id, max_depth)


def symptom_to_formula(symptom_name: str) -> Dict[str, Any]:
    """
    教学场景最常用的一条链：症状 → 证候 → 方剂 → 药材。
    直接产出 QAResult 需要的四个列表 + graph。
    """
    s = _svc()
    hits = search_entities(symptom_name, "症状", 1)
    if not hits:
        return {"symptoms": [], "syndromes": [], "formulas": [], "herbs": [],
                "graph": {"nodes": [], "edges": []}, "paths": []}
    sid = hits[0]["id"]
    g = s.subgraph(sid, depth=3).model_dump()
    by_type = lambda t: [n["label"] for n in g["nodes"] if n["type"] == t]
    paths = []
    for f in [n for n in g["nodes"] if n["type"] == "方剂"]:
        paths += [p["readable"] for p in s.find_paths(sid, f["id"], 3, 2)]
    return {"symptoms": by_type("症状"), "syndromes": by_type("证候"),
            "formulas": by_type("方剂"), "herbs": by_type("药材"),
            "graph": g, "paths": paths}


# ---------------- HTTP 调用（任务3/4 单独部署时用） ----------------
class GraphClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base = base_url.rstrip("/")

    def _get(self, path: str, **params):
        r = requests.get(f"{self.base}/api{path}", params=params, timeout=10)
        r.raise_for_status()
        body = r.json()
        if body.get("code") != 0:
            raise RuntimeError(body.get("msg"))
        return body["data"]

    def search_entities(self, keyword, type_=None, top_k=5):
        return self._get("/entities", keyword=keyword, type=type_, size=top_k)["items"]

    def get_entity_detail(self, entity_id):
        return self._get(f"/entities/{entity_id}")

    def get_subgraph(self, entity_id, depth=2):
        return self._get("/graph/subgraph", id=entity_id, depth=depth)

    def explain_path(self, source_id, target_id, max_depth=4):
        return self._get("/graph/path", source_id=source_id,
                         target_id=target_id, max_depth=max_depth)["paths"]
