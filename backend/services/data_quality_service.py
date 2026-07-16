from __future__ import annotations

from collections import Counter, defaultdict

from backend.db.database import get_connection
from backend.services.kg_data_quality import audit_kg
from backend.services.local_graphrag_service import get_local_graphrag_service
from backend.services.rag_runtime_service import REQUIRED_CATEGORIES, runtime_report


class DataQualityService:
    def report(self) -> dict:
        graph = get_local_graphrag_service()
        file_audit = audit_kg()
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
        runtime = runtime_report()
        qdrant = runtime["qdrant"]
        local_ready = runtime["sqlite"]["ready"]
        vector_status = {**qdrant, "status": "ready" if local_ready else qdrant["status"],
                         "active_backend": "qdrant" if qdrant["status"] == "ready" else "sqlite-local-vector",
                         "external_backends": {"qdrant": qdrant, "milvus": runtime["milvus"]}}
        return {
            "quality_gate": {
                "passed": file_audit["passed"],
                "critical": file_audit["critical"],
                "warnings": file_audit["warnings"],
                "summary": file_audit["summary"],
            },
            "kg": {"entities": len(graph.entities), "relations": len(graph.relations),
                   "entities_with_relations": len(degree),
                   "relation_coverage": round(len(degree) / max(1, len(graph.entities)), 4),
                   "relations_with_evidence": evidenced,
                   "evidence_coverage": round(evidenced / max(1, len(graph.relations)), 4),
                   "by_type": dict(by_type)},
            "corpus": {"categories": docs, "required_categories": list(REQUIRED_CATEGORIES),
                       "source_corpora": runtime["source_corpora"], "ready": runtime["sqlite"]["ready"]},
            "vector_database": vector_status,
            "runtime": {"llm": runtime["llm"], "milvus": runtime["milvus"], "qdrant": qdrant},
            "known_data_limits": [
                "疾病、药材与证候关系以根目录正式图谱中可验证的数据为准，不能据此宣称覆盖全部临床关联。",
                "药典资料为项目整理的来源索引，不等同于《中国药典》全文授权数据库。",
                "系统对缺少有依据关系的查询执行证据不足提示，不自动编造关系。",
            ],
        }
