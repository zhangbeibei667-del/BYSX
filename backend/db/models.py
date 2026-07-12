CREATE_QA_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS qa_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_text TEXT NOT NULL,
    answer TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


CREATE_DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source TEXT,
    content TEXT,
    file_path TEXT,
    category TEXT NOT NULL DEFAULT '未分类',
    edition TEXT,
    chapter TEXT,
    section TEXT,
    publisher TEXT,
    identifier TEXT,
    source_url TEXT,
    license TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

CREATE_DOCUMENT_CHUNKS_TABLE = """
CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    locator_json TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT,
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
    UNIQUE(document_id, chunk_index)
);
"""

CREATE_CONVERSATION_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    turns_json TEXT NOT NULL DEFAULT '[]',
    collected_json TEXT NOT NULL DEFAULT '{}',
    pending_questions_json TEXT NOT NULL DEFAULT '[]',
    last_result_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

CREATE_CASES_TABLE = """
CREATE TABLE IF NOT EXISTS teaching_cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    case_json TEXT NOT NULL DEFAULT '{}',
    analysis_json TEXT NOT NULL DEFAULT '{}',
    session_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""
