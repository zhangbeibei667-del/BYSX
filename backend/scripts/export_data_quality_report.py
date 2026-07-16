import json
from pathlib import Path

from backend.db.database import init_db
from backend.services.data_quality_service import DataQualityService


if __name__ == "__main__":
    init_db()
    report = DataQualityService().report()
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    targets = [Path("backend/data/data_quality_report.json"), Path("docs/data_quality_report.json")]
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    gate = report["quality_gate"]
    summary = gate["summary"]
    critical = gate["critical"]
    lines = [
        "# 中医药知识图谱数据质量报告", "",
        f"- 质量门禁：{'通过' if gate['passed'] else '未通过'}",
        f"- 实体：{summary['entities']:,}", f"- 关系：{summary['relations']:,}",
        f"- 证据覆盖率：{summary['evidence_coverage']:.0%}", "",
        "| 严格指标 | 数量 | 要求 |", "|---|---:|---:|",
        f"| 重复实体 ID | {critical['duplicate_entity_ids']} | 0 |",
        f"| 重复关系 | {critical['duplicate_relations']} | 0 |",
        f"| 悬空关系 | {critical['dangling_relations']} | 0 |",
        f"| 缺失证据 | {critical['missing_evidence']} | 0 |",
        f"| 非法关系约束 | {critical['invalid_relation_constraints']} | 0 |", "",
        "## 实体类型", "", "| 类型 | 数量 |", "|---|---:|",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in summary["entity_types"].items())
    lines.extend(["", "## 关系类型", "", "| 类型 | 数量 |", "|---|---:|"])
    lines.extend(f"| {name} | {count} |" for name, count in summary["relation_types"].items())
    lines.extend(["", "## 覆盖说明", "",
                  f"本项目收录 {summary['diseases']} 个疾病实体，"
                  f"其中 {summary['diseases_with_syndrome_relations']} 个已建立常见证候关系。",
                  "该覆盖范围仅代表项目数据集，不宣称覆盖全部临床疾病与辨证分型。", ""])
    Path("docs/数据质量报告.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(str(path) for path in targets))
