import json

from backend.db.database import get_connection


class HistoryService:
    def save_case_result(self, case_text: str, result: dict) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO qa_history (case_text, answer, result_json)
                VALUES (?, ?, ?)
                """,
                (
                    case_text,
                    result.get("answer", ""),
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def list_history(self, limit: int = 20, offset: int = 0) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, case_text, answer, created_at
                FROM qa_history
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_history(self, history_id: int) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, case_text, answer, result_json, created_at
                FROM qa_history
                WHERE id = ?
                """,
                (history_id,),
            ).fetchone()
        if row is None:
            return None

        data = dict(row)
        data["result"] = json.loads(data.pop("result_json"))
        return data

    def delete_history(self, history_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM qa_history WHERE id = ?", (history_id,))
            conn.commit()
            return cursor.rowcount > 0
