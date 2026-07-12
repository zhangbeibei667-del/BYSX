from __future__ import annotations

import json

from backend.db.database import get_connection, init_db
from backend.services.document_service import DocumentService
from backend.services.local_graphrag_service import get_local_graphrag_service


PREFIX = "managed-corpus:"


def build() -> dict:
    init_db()
    service = DocumentService()
    graph = get_local_graphrag_service()
    with get_connection() as conn:
        old_ids = [row[0] for row in conn.execute("SELECT id FROM documents WHERE identifier LIKE ?", (PREFIX + "%",))]
    for document_id in old_ids:
        service.delete_document(document_id)

    entities = {entity.id: entity for entity in graph.entities}
    outgoing: dict[str, list] = {}
    for relation in graph.relations:
        outgoing.setdefault(relation.source_id, []).append(relation)

    formula_entries = []
    for entity in graph.entities:
        if entity.type != "方剂":
            continue
        edges = outgoing.get(entity.id, [])
        relations = "；".join(f"{edge.relation}：{edge.target_name}（依据：{edge.evidence or '图谱数据'}）" for edge in edges)
        formula_entries.append(f"## {entity.name}\n{entity.description}\n{relations}")

    herb_entries = []
    for entity in graph.entities:
        if entity.type != "药材":
            continue
        source = str((entity.properties or {}).get("source", ""))
        if "SymMap" not in source and not entity.description:
            continue
        edges = outgoing.get(entity.id, [])
        relations = "；".join(f"{edge.relation}：{edge.target_name}（{edge.evidence}）" for edge in edges[:20])
        herb_entries.append(f"## {entity.name}\n{entity.description}\n{relations}")

    syndrome_entries = []
    for entity in graph.entities:
        if entity.type not in {"证候", "功效", "禁忌"}:
            continue
        edges = outgoing.get(entity.id, [])
        relations = "；".join(f"{edge.relation}：{edge.target_name}（{edge.evidence}）" for edge in edges[:20])
        syndrome_entries.append(f"## {entity.name}\n{entity.description}\n{relations}")

    specs = [
        ("方剂学教材知识条目", "教材", "《方剂学》教材与图谱整理", "方剂学", formula_entries,
         "managed-corpus:textbook-formulas"),
        ("中药与药典来源索引", "药典", "SymMap v2（数据源含《中国药典》2015/2020）", "中药条目", herb_entries,
         "managed-corpus:pharmacopoeia-index"),
        ("方剂组成与主治说明", "方剂说明", "方剂学关系数据", "方剂说明", formula_entries,
         "managed-corpus:formula-guide"),
        ("中医药证候功效科普知识卡", "科普资料", "基于可追溯知识图谱生成的科普知识卡", "证候、功效与禁忌", syndrome_entries,
         "managed-corpus:popular-science"),
    ]
    created = []
    for title, category, source, chapter, entries, identifier in specs:
        document = service.create_document(
            title=title, category=category, source=source, chapter=chapter,
            edition="项目交付版 1.0", publisher="本项目资料库", identifier=identifier,
            license="仅用于项目内知识学习与研究", content="\n\n".join(entries),
        )
        created.append({"id": document["id"], "title": title, "category": category,
                        "chunks": document["indexed_chunks"], "entries": len(entries)})
    return {"documents": created, "total_chunks": sum(item["chunks"] for item in created)}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
