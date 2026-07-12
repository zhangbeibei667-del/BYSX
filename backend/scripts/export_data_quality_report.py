import json
from pathlib import Path

from backend.db.database import init_db
from backend.services.data_quality_service import DataQualityService


if __name__ == "__main__":
    init_db()
    report = DataQualityService().report()
    path = Path("backend/data/data_quality_report.json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
