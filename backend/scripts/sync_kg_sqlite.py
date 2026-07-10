from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.services.local_graphrag_service import get_local_graphrag_service


def sync_kg_sqlite(db_path: Path | None = None) -> Path:
    """Synchronize the currently loaded local KG into a queryable SQLite DB."""
    db_path = db_path or WORKSPACE_ROOT / "backend" / "data" / "kg.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    service = get_local_graphrag_service()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.executescript(
            """
            DROP TABLE IF EXISTS entities;
            DROP TABLE IF EXISTS relations;
            DROP TABLE IF EXISTS metadata;

            CREATE TABLE entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                alias TEXT,
                description TEXT,
                properties_json TEXT
            );

            CREATE TABLE relations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_name TEXT,
                source_type TEXT,
                relation TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_name TEXT,
                target_type TEXT,
                evidence TEXT
            );

            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX idx_entities_type ON entities(type);
            CREATE INDEX idx_entities_name ON entities(name);
            CREATE INDEX idx_relations_source ON relations(source_id);
            CREATE INDEX idx_relations_target ON relations(target_id);
            CREATE INDEX idx_relations_relation ON relations(relation);
            """
        )

        conn.executemany(
            """
            INSERT OR REPLACE INTO entities
            (id, name, type, alias, description, properties_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    entity.id,
                    entity.name,
                    entity.type,
                    entity.alias,
                    entity.description,
                    json.dumps(entity.properties or {}, ensure_ascii=False),
                )
                for entity in service.entities
            ],
        )

        rows = []
        for relation in service.relations:
            source = service.entities_by_id.get(relation.source_id)
            target = service.entities_by_id.get(relation.target_id)
            relation_id = f"{relation.source_id}|{relation.relation}|{relation.target_id}"
            rows.append(
                (
                    relation_id,
                    relation.source_id,
                    relation.source_name or (source.name if source else ""),
                    source.type if source else "",
                    relation.relation,
                    relation.target_id,
                    relation.target_name or (target.name if target else ""),
                    target.type if target else "",
                    relation.evidence,
                )
            )
        conn.executemany(
            """
            INSERT OR REPLACE INTO relations
            (id, source_id, source_name, source_type, relation, target_id, target_name, target_type, evidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.executemany(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
            [
                ("entity_count", str(len(service.entities))),
                ("relation_count", str(len(service.relations))),
                ("source", "local_entities_relations_json"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    return db_path


if __name__ == "__main__":
    path = sync_kg_sqlite()
    print(path)
