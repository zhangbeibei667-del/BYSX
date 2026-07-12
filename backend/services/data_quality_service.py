from __future__ import annotations

from collections import Counter, defaultdict

from backend.db.database import get_connection
from backend.services.local_graphrag_service import get_local_graphrag_service


class DataQualityService:
    def report(self) -> dict:
        graph = get_local_graphrag_service()
        degree = Counter()
        evidenced = 0
        for relation in graph.relations:
            degree[relation.source_id] += 1
            degree[relation.target_id] += 1
            evidenced += bool(relation.evidence)
        by_type: dict[str, dict] = defaultdict(lambda: {"entities": 0, "related": 0})
        for entity in graph.entities:
            by_type[entity.type]["entities"] += 1
            by_type[entity.type]["related"] += int(degree[entity.id] > 0)
        for stats in by_type.values():
            stats["coverage"] = round(stats["related"] / max(1, stats["entities"]), 4)
        with get_connection() as conn:
            docs = [dict(row) for row in conn.execute(
                """SELECT d.category, COUNT(DISTINCT d.id) AS documents, COUNT(c.id) AS chunks
                   FROM documents d LEFT JOIN document_chunks c ON c.document_id=d.id GROUP BY d.category""")]
        qdrant = {"status": "unavailable", "points": 0}
        try:
            from backend.services.qdrant_vector_store import get_qdrant_vector_store
            store = get_qdrant_vector_store()
            qdrant = {"status": "ready", "collection": store.collection,
                      "model": store.model_name, "points": store.client.get_collection(store.collection).points_count}
        except Exception as exc:
            qdrant["error"] = str(exc)
        return {
            "kg": {"entities": len(graph.entities), "relations": len(graph.relations),
                   "entities_with_relations": len(degree),
                   "relation_coverage": round(len(degree) / max(1, len(graph.entities)), 4),
                   "relations_with_evidence": evidenced,
                   "evidence_coverage": round(evidenced / max(1, len(graph.relations)), 4),
                   "by_type": dict(by_type)},
            "corpus": {"categories": docs, "required_categories": ["教材", "药典", "方剂说明", "科普资料"]},
            "vector_database": qdrant,
            "known_data_limits": [
                "已从 SymMap related_components 导入药材—中医症状/证候关系，并从补充表 S5 导入可匹配的药材—疾病关系。",
                "疾病实体覆盖很大，但当前疾病关系只覆盖 SymMap S5 可验证子集；不能据此宣称覆盖全部疾病关联。",
                "药典资料为带来源标记的 SymMap 药典索引，不等同于《中国药典》全文授权数据库。",
                "系统对缺少有依据关系的查询执行证据不足提示，不自动编造关系。",
            ],
        }
