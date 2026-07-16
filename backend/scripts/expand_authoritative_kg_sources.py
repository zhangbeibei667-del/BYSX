"""Expand literature entities from the local HKCMMS official-source dataset.

The script is deterministic and idempotent. It never invents a herb match:
only exact names after an explicit Traditional-to-Simplified mapping are linked.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HKCMMS = ROOT / "member3/data/pharmacopoeia/processed/hkcmms/index_ready/chunks_for_index.jsonl"
LITERATURE = ROOT / "entities/literature.json"
HERBS = ROOT / "entities/herb.json"
SOURCE_RELATIONS = ROOT / "relations/source.json"

PUBLISHER = "香港特别行政区政府卫生署中医药规管办公室"
LICENSE_NOTE = "官方公开网页/PDF；版权归发布机构，课程项目仅作检索与引用"
NAME_MAP = {
    "一枝黃花": "一枝黄花", "瓜蔞皮": "瓜蒌皮", "黑種草子": "黑种草子",
    "黃芩": "黄芩", "黃藤": "黄藤", "田基黃": "田基黄", "佩蘭": "佩兰",
    "浙貝母": "浙贝母", "人參葉": "人参叶", "黃芪": "黄芪", "龍脷葉": "龙脷叶",
    "何首烏": "何首乌", "魚腥草": "鱼腥草", "鬱金": "郁金", "紅豆蔻": "红豆蔻",
    "靈芝": "灵芝", "龍膽": "龙胆", "北沙參": "北沙参", "": "泽泻",
}


def load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build() -> dict:
    chunks = [json.loads(line) for line in HKCMMS.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    by_document: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        by_document[chunk["document_id"]].append(chunk)
    documents = [sorted(rows, key=lambda row: (row.get("page_start") or 0, row["chunk_id"]))
                 for _, rows in sorted(by_document.items())]

    herbs = load_json(HERBS)
    herb_by_name = {row["name"]: row for row in herbs}
    literature = [row for row in load_json(LITERATURE) if not row["id"].startswith("LHK")]
    relations = [row for row in load_json(SOURCE_RELATIONS)
                 if not str(row["source_id"]).startswith("LHK")]

    source_url = "https://www.cmro.gov.hk/html/eng/useful_information/hkcmms/cmmlist.html"
    collection = {
        "id": "LHK001", "name": "香港中药材标准（HKCMMS）", "type": "文献", "alias": "HKCMMS",
        "description": "香港特别行政区政府发布的中药材质量与鉴别标准资料集。",
        "properties": {"publisher": PUBLISHER, "source_url": source_url, "license": LICENSE_NOTE,
                       "source_type": "public_government_standard"},
    }
    literature.append(collection)

    # Two volume-level publications are retained as independent, citable sources.
    chosen_volumes = sorted({int(rows[0]["volume"]) for rows in documents})[:2]
    for volume in chosen_volumes:
        literature.append({
            "id": f"LHKV{volume:02d}", "name": f"《香港中药材标准》第{volume}册", "type": "文献", "alias": "",
            "description": f"HKCMMS 第{volume}册官方中药材标准汇编。",
            "properties": {"publisher": PUBLISHER, "edition": f"第{volume}册", "source_url": source_url,
                           "license": LICENSE_NOTE, "source_type": "public_government_standard"},
        })

    matched = 0
    for index, rows in enumerate(documents, 1):
        first = rows[0]
        raw_name = str(first.get("chinese_name") or first.get("title") or "").strip()
        herb_name = NAME_MAP.get(raw_name, raw_name)
        literature_id = f"LHKM{index:03d}"
        page_start = min(int(row.get("page_start") or 1) for row in rows)
        page_end = max(int(row.get("page_end") or page_start) for row in rows)
        literature.append({
            "id": literature_id, "name": f"HKCMMS《{raw_name or herb_name}》", "type": "文献",
            "alias": str(first.get("official_name") or ""),
            "description": f"HKCMMS 第{first['volume']}册中药材标准条目，覆盖第{page_start}—{page_end}页。",
            "properties": {
                "publisher": PUBLISHER, "edition": f"第{first['volume']}册", "chapter": raw_name or herb_name,
                "page_start": page_start, "page_end": page_end, "source_url": first.get("source_url") or "",
                "identifier": first["document_id"], "license": LICENSE_NOTE,
                "original_excerpt": rows[0].get("text", "")[:500],
            },
        })
        herb = herb_by_name.get(herb_name)
        if not herb:
            continue
        matched += 1
        citation = f"HKCMMS 第{first['volume']}册《{raw_name or herb_name}》第{page_start}—{page_end}页"
        locator = {"url": first.get("source_url") or "", "pages": f"{page_start}-{page_end}"}
        for source_id, source_name in [(literature_id, f"HKCMMS《{raw_name or herb_name}》"),
                                       ("LHK001", "香港中药材标准（HKCMMS）")]:
            relations.append({
                "source_id": source_id, "source_name": source_name, "relation": "记载",
                "target_id": herb["id"], "target_name": herb["name"], "evidence": citation,
                "evidence_level": "B_药典标准", "confidence": 0.95, "locator": locator,
                "excerpt": rows[0].get("text", "")[:300], "review_status": "reviewed", "version": "1.0",
            })
        if int(first["volume"]) in chosen_volumes:
            relations.append({
                "source_id": f"LHKV{int(first['volume']):02d}",
                "source_name": f"《香港中药材标准》第{first['volume']}册", "relation": "记载",
                "target_id": herb["id"], "target_name": herb["name"], "evidence": citation,
                "evidence_level": "B_药典标准", "confidence": 0.95, "locator": locator,
                "excerpt": rows[0].get("text", "")[:300], "review_status": "reviewed", "version": "1.0",
            })

    literature.sort(key=lambda row: row["id"])
    relations.sort(key=lambda row: (row["source_id"], row["relation"], row["target_id"]))
    write_json(LITERATURE, literature)
    write_json(SOURCE_RELATIONS, relations)
    return {"literature_entities": len(literature), "hkcmms_monographs": len(documents),
            "matched_herbs": matched, "source_relations": len(relations)}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
