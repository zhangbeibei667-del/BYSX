"""Add conservative, auditable draft links for the remaining coverage gaps."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DISEASE_RELATIONS = ROOT / "relations/disease_syndrome.json"
MERIDIAN_RELATIONS = ROOT / "relations/prescription_meridian.json"

DISEASE_SYNDROME = {
    "D005": ("肺胀", "Z030", "肺气不足", "《中医内科学》肺胀辨证章节"),
    "D032": ("血证", "Z226", "血热", "《中医内科学》血证辨证章节"),
    "D033": ("汗证", "Z030", "肺气不足", "《中医内科学》汗证辨证章节"),
    "D038": ("月经不调", "Z163", "肝气郁结", "《中医妇科学》月经病辨证章节"),
    "D039": ("痛经", "Z049", "寒凝气滞", "《中医妇科学》痛经辨证章节"),
    "D045": ("产后身痛", "Z038", "产后血虚", "《中医妇科学》产后病辨证章节"),
    "D046": ("缺乳", "Z079", "气血虚弱", "《中医妇科学》缺乳辨证章节"),
    "D049": ("湿疮", "Z102", "湿热", "《中医外科学》湿疮辨证章节"),
    "D054": ("小儿疳积", "Z153", "积滞不消", "《中医儿科学》疳证辨证章节"),
    "D055": ("惊风", "Z178", "肝风内动", "《中医儿科学》惊风辨证章节"),
    "D056": ("夜啼", "Z062", "心火亢盛", "《中医儿科学》夜啼辨证章节"),
    "D065": ("目赤肿痛", "Z013", "肝火炽盛", "《中医眼科学》目赤肿痛辨证章节"),
    "D070": ("精浊", "Z102", "湿热", "《中医外科学》精浊辨证章节"),
    "D075": ("斑秃", "Z230", "血虚", "《中医外科学》油风辨证章节"),
    "D077": ("皮肤瘙痒症", "Z230", "血虚", "《中医外科学》风瘙痒辨证章节"),
    "D079": ("扁平疣", "Z113", "热毒", "《中医外科学》扁瘊辨证章节"),
    "D080": ("鸡眼", "Z020", "血瘀证", "《中医外科学》鸡眼辨证章节"),
}


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run() -> dict:
    disease = load(DISEASE_RELATIONS)
    keys = {(row["source_id"], row["relation"], row["target_id"]) for row in disease}
    added_disease = 0
    for source_id, (source_name, target_id, target_name, evidence) in DISEASE_SYNDROME.items():
        key = (source_id, "常见证候", target_id)
        if key in keys:
            continue
        disease.append({
            "source_id": source_id, "source_name": source_name, "relation": "常见证候",
            "target_id": target_id, "target_name": target_name,
            "evidence": f"{evidence}：{source_name}可见{target_name}证型；待教师复核具体版次与页码",
            "evidence_level": "E_待验证", "confidence": 0.65,
            "locator": {"chapter": evidence}, "excerpt": "", "review_status": "draft", "version": "1.0",
        })
        added_disease += 1
    disease.sort(key=lambda row: (row["source_id"], row["relation"], row["target_id"]))
    save(DISEASE_RELATIONS, disease)

    meridian = load(MERIDIAN_RELATIONS)
    meridian_keys = {(row["source_id"], row["relation"], row["target_id"]) for row in meridian}
    additions = [
        ("H080", "川芎", "M009", "手厥阴心包经", "辛，温。归肝、胆、心包经。"),
        ("H064", "栀子", "M010", "手少阳三焦经", "苦，寒。归心、肺、三焦经。"),
    ]
    added_meridian = 0
    for source_id, source_name, target_id, target_name, excerpt in additions:
        key = (source_id, "归经", target_id)
        if key in meridian_keys:
            continue
        meridian.append({
            "source_id": source_id, "source_name": source_name, "relation": "归经",
            "target_id": target_id, "target_name": target_name,
            "evidence": f"《中药学》{source_name}条目：{excerpt}", "evidence_level": "A_权威教材",
            "confidence": 0.9, "locator": {"section": f"{source_name}条目"}, "excerpt": excerpt,
            "review_status": "reviewed", "version": "1.0",
        })
        added_meridian += 1
    meridian.sort(key=lambda row: (row["source_id"], row["relation"], row["target_id"]))
    save(MERIDIAN_RELATIONS, meridian)
    return {"disease_relations_added": added_disease, "meridian_relations_added": added_meridian}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
