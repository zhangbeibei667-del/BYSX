"""Build many independently traceable documents instead of four giant logical files."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from backend.db.database import get_connection, init_db
from backend.services.document_service import DocumentService
from backend.services.local_graphrag_service import get_local_graphrag_service


ROOT = Path(__file__).resolve().parents[2]
PREFIX = "managed-corpus:"
HKCMMS = ROOT / "member3/data/pharmacopoeia/processed/hkcmms/index_ready/chunks_for_index.jsonl"
PROJECT_LICENSE = "项目整理内容；仅用于课程知识学习，引用时须回溯底层证据来源"
HK_PUBLISHER = "香港特别行政区政府卫生署中医药规管办公室"
HK_LICENSE = "官方公开网页/PDF；版权归发布机构，课程项目仅作检索与引用"


def relation_text(entity, edges: list) -> str:
    rows = []
    for edge in edges:
        rows.append(f"- {edge.relation}：{edge.target_name}\n  依据：{edge.evidence or '待补充来源'}")
    return "\n".join(rows)


def build() -> dict:
    init_db()
    service = DocumentService()
    graph = get_local_graphrag_service()
    with get_connection() as conn:
        old_ids = [row[0] for row in conn.execute(
            "SELECT id FROM documents WHERE identifier LIKE ?", (PREFIX + "%",)
        )]
    for document_id in old_ids:
        service.delete_document(document_id)

    outgoing: dict[str, list] = defaultdict(list)
    for relation in graph.relations:
        outgoing[relation.source_id].append(relation)

    created: list[dict] = []

    def create(*, identifier: str, title: str, category: str, source: str, content: str,
               edition: str, chapter: str, section: str, publisher: str,
               source_url: str = "", license_text: str = PROJECT_LICENSE) -> None:
        document = service.create_document(
            title=title, category=category, source=source, content=content,
            edition=edition, chapter=chapter, section=section, publisher=publisher,
            identifier=PREFIX + identifier, source_url=source_url, license=license_text,
        )
        created.append({"id": document["id"], "identifier": PREFIX + identifier,
                        "category": category, "chunks": document["indexed_chunks"]})

    # Each graph entity becomes its own citable document. Metadata is deliberately
    # labelled as a project compilation rather than pretending to be a licensed textbook scan.
    for entity in graph.entities:
        edges = outgoing.get(entity.id, [])
        body = f"## {entity.name}\n{entity.description}\n\n{relation_text(entity, edges)}".strip()
        if entity.type == "方剂":
            create(identifier=f"textbook-formula:{entity.id}", title=f"方剂学知识条目：{entity.name}",
                   category="教材", source="项目方剂学知识图谱整理",
                   content=body, edition="项目整理版 1.0", chapter="方剂条目", section=entity.name,
                   publisher="本项目资料库")
            create(identifier=f"formula-guide:{entity.id}", title=f"方剂说明：{entity.name}",
                   category="方剂说明", source="项目方剂组成与主治关系整理",
                   content=body, edition="项目整理版 1.0", chapter="方剂说明", section=entity.name,
                   publisher="本项目资料库")
        elif entity.type == "药材" and (entity.description or edges):
            create(identifier=f"pharmacopoeia-index:{entity.id}", title=f"中药来源索引：{entity.name}",
                   category="药典", source="项目中药知识图谱来源索引",
                   content=body, edition="项目整理版 1.0", chapter="中药条目", section=entity.name,
                   publisher="本项目资料库")
        elif entity.type in {"证候", "功效", "禁忌"}:
            create(identifier=f"popular-science:{entity.id}", title=f"中医药知识卡：{entity.name}",
                   category="科普资料", source="基于可追溯知识图谱生成的知识卡",
                   content=body, edition="项目整理版 1.0", chapter=entity.type, section=entity.name,
                   publisher="本项目资料库")

    # Add independently published HKCMMS monographs with real page ranges and URLs.
    if HKCMMS.exists():
        rows = [json.loads(line) for line in HKCMMS.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            groups[row["document_id"]].append(row)
        for document_id, chunks in sorted(groups.items()):
            chunks.sort(key=lambda row: (row.get("page_start") or 0, row["chunk_id"]))
            first = chunks[0]
            title = str(first.get("chinese_name") or first.get("title") or first.get("official_name"))
            content = "\n\n".join(
                f"[PAGE {row.get('page_start') or ''}]\n## {row.get('section_title') or '文档正文'}\n{row['text']}"
                for row in chunks
            )
            create(identifier=f"hkcmms:{document_id}", title=f"HKCMMS《{title}》", category="药典",
                   source="香港中药材标准（HKCMMS）", content=content,
                   edition=f"第{first['volume']}册", chapter=title, section="完整标准条目",
                   publisher=HK_PUBLISHER, source_url=first.get("source_url") or "", license_text=HK_LICENSE)

    counts: dict[str, int] = defaultdict(int)
    for item in created:
        counts[item["category"]] += 1
    return {"documents": len(created), "documents_by_category": dict(counts),
            "total_chunks": sum(item["chunks"] for item in created)}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
