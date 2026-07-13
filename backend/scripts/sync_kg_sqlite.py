"""Synchronize the knowledge graph into a queryable SQLite database.

Two data sources are supported:

1. **Local JSON files** (entities/*.json + relations/*.json) — the default.
2. **MySQL** (via server.store_mysql.MySQLStore) — pass ``--from-mysql``.

Usage::

    python -m backend.scripts.sync_kg_sqlite              # JSON → SQLite
    python -m backend.scripts.sync_kg_sqlite --from-mysql # MySQL → SQLite
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))


def sync_kg_sqlite(db_path: Path | None = None) -> Path:
    """Synchronize the currently loaded local KG (JSON) into a queryable SQLite DB."""
    from backend.services.local_graphrag_service import get_local_graphrag_service

    db_path = db_path or WORKSPACE_ROOT / "backend" / "data" / "kg.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    service = get_local_graphrag_service()
    _write_sqlite(db_path, service.entities, service.relations, source="local_entities_relations_json")
    return db_path


def sync_kg_sqlite_from_mysql(db_path: Path | None = None) -> Path:
    """Synchronize the MySQL knowledge graph into a queryable SQLite DB."""
    db_path = db_path or WORKSPACE_ROOT / "backend" / "data" / "kg.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    from server.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
    from server.store_mysql import MySQLStore

    store = MySQLStore(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
    )

    # Collect entities from MySQL
    total_e, entities = store.list_entities(None, None, 1, 100000)
    # Convert Entity Pydantic models to objects with the attributes sql_tool expects
    entity_objs = []
    for e in entities:
        entity_objs.append(_EntityProxy(
            id=e.id, name=e.name, type=e.type,
            alias=e.alias, description=e.description,
            properties=e.properties,
        ))

    # Collect relations from MySQL
    total_r, relations = store.list_relations(None, None, None, 1, 100000)
    relation_objs = []
    for r in relations:
        src = store.get_entity(r.source_id)
        tgt = store.get_entity(r.target_id)
        relation_objs.append(_RelationProxy(
            source_id=r.source_id,
            source_name=r.source_name,
            source_type=src.type if src else "",
            relation=r.relation,
            target_id=r.target_id,
            target_name=r.target_name,
            target_type=tgt.type if tgt else "",
            evidence=r.evidence,
        ))

    _write_sqlite(db_path, entity_objs, relation_objs, source="mysql_auto_sync")
    return db_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _EntityProxy:
    """Minimal entity proxy matching the interface expected by _write_sqlite."""
    __slots__ = ("id", "name", "type", "alias", "description", "properties")
    def __init__(self, id, name, type, alias, description, properties):
        self.id = id
        self.name = name
        self.type = type
        self.alias = alias
        self.description = description
        self.properties = properties


class _RelationProxy:
    """Minimal relation proxy matching the interface expected by _write_sqlite."""
    __slots__ = ("source_id", "source_name", "source_type", "relation",
                 "target_id", "target_name", "target_type", "evidence")
    def __init__(self, source_id, source_name, source_type, relation,
                 target_id, target_name, target_type, evidence):
        self.source_id = source_id
        self.source_name = source_name
        self.source_type = source_type
        self.relation = relation
        self.target_id = target_id
        self.target_name = target_name
        self.target_type = target_type
        self.evidence = evidence


def _write_sqlite(db_path: Path, entities: list, relations: list, source: str = "") -> None:
    """Write entities and relations to a fresh SQLite database."""
    conn = sqlite3.connect(str(db_path))
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
                for entity in entities
            ],
        )

        rows = []
        for relation in relations:
            relation_id = f"{relation.source_id}|{relation.relation}|{relation.target_id}"
            rows.append(
                (
                    relation_id,
                    relation.source_id,
                    relation.source_name or "",
                    relation.source_type or "",
                    relation.relation,
                    relation.target_id,
                    relation.target_name or "",
                    relation.target_type or "",
                    relation.evidence or "",
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
                ("entity_count", str(len(entities))),
                ("relation_count", str(len(relations))),
                ("source", source or "unknown"),
            ],
        )
        conn.commit()
        print(f"[sync_kg_sqlite] Wrote {len(entities)} entities, {len(relations)} relations to {db_path} (source: {source})")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync KG data to SQLite")
    parser.add_argument("--from-mysql", action="store_true",
                        help="Pull data from MySQL instead of local JSON files")
    parser.add_argument("--output", type=str, default=None,
                        help="Output SQLite path (default: backend/data/kg.sqlite)")
    args = parser.parse_args()

    out_path = Path(args.output) if args.output else None

    if args.from_mysql:
        path = sync_kg_sqlite_from_mysql(out_path)
    else:
        path = sync_kg_sqlite(out_path)

    print(f"Done: {path}")
