from __future__ import annotations

import json
import time

from backend.db.database import get_connection


class ConversationService:
    def load(self, session_id: str | None) -> dict:
        session_id = session_id or str(int(time.time() * 1000))
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM conversation_sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return {"id": session_id, "turns": [], "collected": {}, "pending_questions": [], "status": "active"}
        return {"id": session_id, "turns": json.loads(row["turns_json"]),
                "collected": json.loads(row["collected_json"]),
                "pending_questions": json.loads(row["pending_questions_json"]), "status": row["status"]}

    def save_turn(self, session: dict, user_text: str, result: dict) -> dict:
        session["turns"].extend([
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": result.get("answer", "")},
        ])
        session["turns"] = session["turns"][-20:]
        for key in ("symptoms", "tongue", "pulse"):
            session["collected"][key] = list(dict.fromkeys([
                *session["collected"].get(key, []), *result.get(key, [])]))
        session["pending_questions"] = result.get("follow_up_questions", [])
        session["status"] = "awaiting_clarification" if result.get("needs_clarification") else "answered"
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO conversation_sessions(id, turns_json, collected_json, pending_questions_json, status, updated_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
                   ON CONFLICT(id) DO UPDATE SET turns_json=excluded.turns_json,
                   collected_json=excluded.collected_json, pending_questions_json=excluded.pending_questions_json,
                   status=excluded.status, updated_at=excluded.updated_at""",
                (session["id"], json.dumps(session["turns"], ensure_ascii=False),
                 json.dumps(session["collected"], ensure_ascii=False),
                 json.dumps(session["pending_questions"], ensure_ascii=False), session["status"]),
            )
            conn.commit()
        return session

    @staticmethod
    def contextualize(session: dict, user_text: str) -> str:
        if not session.get("turns"):
            return user_text
        previous_user_turns = [turn["content"] for turn in session["turns"] if turn.get("role") == "user"][-3:]
        collected = session.get("collected", {})
        clinical = "；".join(
            f"已采集{label}：{'、'.join(collected.get(key, []))}"
            for key, label in (("symptoms", "症状"), ("tongue", "舌象"), ("pulse", "脉象"))
            if collected.get(key))
        history = "\n".join(f"- {text}" for text in previous_user_turns)
        parts = ["这是同一会话中的后续问题。", f"此前用户问题：\n{history}"]
        if clinical:
            parts.append(clinical)
        parts.extend([f"本轮问题：{user_text}", "请结合此前主题理解本轮中的“它、那、这个、怎么办”等指代表达。"])
        return "\n".join(parts)
