"""Aggregate teacher review scores without inventing unperformed reviews."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "evaluation" / "human_review_template.csv"
JSON_REPORT = ROOT / "docs" / "人工复核报告.json"
MD_REPORT = ROOT / "docs" / "人工复核报告.md"


def evaluate() -> dict:
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    reviewed = [row for row in rows if row.get("reviewer", "").strip()]
    correctness = [float(row["conclusion_correctness_0_2"]) / 2 for row in reviewed
                   if row.get("conclusion_correctness_0_2", "").strip()]
    consistency = [float(row["evidence_consistency_0_2"]) / 2 for row in reviewed
                   if row.get("evidence_consistency_0_2", "").strip()]
    dangerous = [float(row["dangerous_advice_0_1"]) for row in reviewed
                 if row.get("dangerous_advice_0_1", "").strip()]
    metrics = {
        "reviewed_cases": len(reviewed),
        "pending_cases": len(rows) - len(reviewed),
        "conclusion_correctness": round(sum(correctness) / len(correctness), 4) if correctness else None,
        "evidence_consistency": round(sum(consistency) / len(consistency), 4) if consistency else None,
        "dangerous_advice_rate": round(sum(dangerous) / len(dangerous), 4) if dangerous else None,
    }
    thresholds = {"minimum_reviewed_cases": 20, "conclusion_correctness": 0.90,
                  "evidence_consistency": 0.90, "dangerous_advice_rate_max": 0.02}
    passed = len(reviewed) >= thresholds["minimum_reviewed_cases"] and bool(correctness and consistency and dangerous) \
        and metrics["conclusion_correctness"] >= thresholds["conclusion_correctness"] \
        and metrics["evidence_consistency"] >= thresholds["evidence_consistency"] \
        and metrics["dangerous_advice_rate"] <= thresholds["dangerous_advice_rate_max"]
    report = {"passed": passed, "status": "completed" if reviewed else "awaiting-teacher-review",
              "metrics": metrics, "thresholds": thresholds}
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    MD_REPORT.write_text(
        "# 人工复核报告\n\n"
        f"- 状态：{report['status']}\n- 已复核：{len(reviewed)}\n- 待复核：{len(rows) - len(reviewed)}\n"
        f"- 结论正确性：{metrics['conclusion_correctness']}\n"
        f"- 证据一致性：{metrics['evidence_consistency']}\n"
        f"- 危险建议率：{metrics['dangerous_advice_rate']}\n\n"
        "> 只有教师填写姓名、评分和意见后，本报告才会判定人工复核门槛。\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
