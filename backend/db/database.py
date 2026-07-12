import sqlite3
from pathlib import Path

from backend.db.models import (
    CREATE_CASES_TABLE,
    CREATE_CONVERSATION_SESSIONS_TABLE,
    CREATE_DOCUMENT_CHUNKS_TABLE,
    CREATE_DOCUMENTS_TABLE,
    CREATE_QA_HISTORY_TABLE,
)


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "tcm_agent.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(CREATE_QA_HISTORY_TABLE)
        conn.execute(CREATE_DOCUMENTS_TABLE)
        conn.execute(CREATE_DOCUMENT_CHUNKS_TABLE)
        conn.execute(CREATE_CONVERSATION_SESSIONS_TABLE)
        conn.execute(CREATE_CASES_TABLE)
        conversation_columns = {row[1] for row in conn.execute("PRAGMA table_info(conversation_sessions)")}
        for name, definition in {
            "title": "TEXT NOT NULL DEFAULT ''",
            "last_result_json": "TEXT NOT NULL DEFAULT '{}'",
            "created_at": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if name not in conversation_columns:
                conn.execute(f"ALTER TABLE conversation_sessions ADD COLUMN {name} {definition}")
        document_columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
        for name, definition in {
            "category": "TEXT NOT NULL DEFAULT '未分类'", "edition": "TEXT", "chapter": "TEXT",
            "section": "TEXT", "publisher": "TEXT", "identifier": "TEXT", "source_url": "TEXT", "license": "TEXT",
        }.items():
            if name not in document_columns:
                conn.execute(f"ALTER TABLE documents ADD COLUMN {name} {definition}")
        chunk_columns = {row[1] for row in conn.execute("PRAGMA table_info(document_chunks)")}
        if "locator_json" not in chunk_columns:
            conn.execute("ALTER TABLE document_chunks ADD COLUMN locator_json TEXT NOT NULL DEFAULT '{}'")
        if "content_hash" not in chunk_columns:
            conn.execute("ALTER TABLE document_chunks ADD COLUMN content_hash TEXT")
        conn.commit()
