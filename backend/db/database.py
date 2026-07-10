import sqlite3
from pathlib import Path

from backend.db.models import CREATE_DOCUMENTS_TABLE, CREATE_QA_HISTORY_TABLE


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "tcm_agent.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(CREATE_QA_HISTORY_TABLE)
        conn.execute(CREATE_DOCUMENTS_TABLE)
        conn.commit()
