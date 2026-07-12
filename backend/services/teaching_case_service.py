from __future__ import annotations

import json
import time

from backend.db.database import get_connection


class TeachingCaseService:
    def create(self, data: dict) -> dict:
        case_id = str(data.get("id") or int(time.time() * 1000))
        title = str(data.get("name") or data.get("title") or data.get("chiefComplaint") or "教学病例")[:40]
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO teaching_cases(id,title,case_json,status) VALUES(?,?,?,?)",
                (case_id, title, json.dumps({**data, "id": case_id}, ensure_ascii=False), "draft"),
            )
            conn.commit()
        return self.get(case_id) or {"id": case_id, **data}

    def get(self, case_id: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM teaching_cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            return None
        data = json.loads(row["case_json"] or "{}")
        analysis = json.loads(row["analysis_json"] or "{}")
        return {**data, "id": row["id"], "title": row["title"], "analysisResult": analysis,
                "sessionId": row["session_id"], "status": row["status"],
                "createdAt": row["created_at"], "updatedAt": row["updated_at"]}

    def save_analysis(self, case_id: str, result: dict, session_id: str | None = None) -> dict | None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE teaching_cases SET analysis_json=?,session_id=?,status=?,updated_at=datetime('now','localtime') WHERE id=?",
                (json.dumps(result, ensure_ascii=False), session_id, result.get("conversation", {}).get("status", "analyzed"), case_id),
            )
            conn.commit()
        return self.get(case_id)

    def list(self, page: int = 1, page_size: int = 20) -> dict:
        offset = max(0, page - 1) * page_size
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM teaching_cases").fetchone()[0]
            rows = conn.execute(
                "SELECT id FROM teaching_cases ORDER BY updated_at DESC LIMIT ? OFFSET ?", (page_size, offset)
            ).fetchall()
        return {"list": [self.get(row["id"]) for row in rows], "total": total}

