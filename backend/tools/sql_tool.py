from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from backend.scripts.sync_kg_sqlite import sync_kg_sqlite


class GraphSQLTool:
    """SQL Agent backed by a real local SQLite copy of the knowledge graph."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        workspace_root = Path(__file__).resolve().parents[2]
        self.db_path = Path(db_path) if db_path else workspace_root / "backend" / "data" / "kg.sqlite"
        self.ensure_database()

    def ensure_database(self) -> None:
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            sync_kg_sqlite(self.db_path)

    def refresh_database(self) -> None:
        sync_kg_sqlite(self.db_path)

    def query_entity_statistics(self, syndromes: list[str] | None = None, formulas: list[str] | None = None) -> dict:
        self.ensure_database()
        syndromes = syndromes or []
        formulas = formulas or []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            entity_counts = {
                row["type"]: row["count"]
                for row in conn.execute(
                    "SELECT type, COUNT(*) AS count FROM entities GROUP BY type ORDER BY type"
                )
            }
            relation_count = conn.execute("SELECT COUNT(*) AS count FROM relations").fetchone()["count"]

            matched_syndromes = self._match_entities(conn, "证候", syndromes)
            matched_formulas = self._match_entities(conn, "方剂", formulas)
            formula_herbs = self._query_formula_herbs(conn, [item["name"] for item in matched_formulas])
            syndrome_formula_relations = self._query_syndrome_formula_relations(
                conn,
                [item["name"] for item in matched_syndromes],
            )
            matched_relation_count = self._count_relations_for_entities(
                conn,
                [item["id"] for item in [*matched_syndromes, *matched_formulas]],
            )

        return {
            "status": "sqlite",
            "database": str(self.db_path),
            "entity_counts": {
                "symptom": entity_counts.get("症状", 0),
                "syndrome": entity_counts.get("证候", 0),
                "formula": entity_counts.get("方剂", 0),
                "herb": entity_counts.get("药材", 0),
                "effect": entity_counts.get("功效", 0),
                "contraindication": entity_counts.get("禁忌", 0),
                "literature": entity_counts.get("文献", 0),
                "total": sum(entity_counts.values()),
            },
            "relation_count": relation_count,
            "matched_syndromes": matched_syndromes,
            "matched_formulas": matched_formulas,
            "matched_entity_count": len(matched_syndromes) + len(matched_formulas),
            "matched_relation_count": matched_relation_count,
            "formula_herbs": formula_herbs,
            "syndrome_formula_relations": syndrome_formula_relations,
            "note": "SQL Agent queried the local SQLite knowledge-graph database synchronized from entities_relations JSON.",
        }

    @staticmethod
    def _match_entities(conn: sqlite3.Connection, entity_type: str, names: list[str]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for name in names:
            name = str(name).strip()
            if not name:
                continue
            rows = conn.execute(
                """
                SELECT id, name, type, alias, description
                FROM entities
                WHERE type = ?
                  AND (name = ? OR alias = ? OR name LIKE ? OR alias LIKE ?)
                LIMIT 10
                """,
                (entity_type, name, name, f"%{name}%", f"%{name}%"),
            ).fetchall()
            for row in rows:
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                result.append(dict(row))
        return result

    @staticmethod
    def _query_formula_herbs(conn: sqlite3.Connection, formulas: list[str]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for formula in formulas:
            rows = conn.execute(
                """
                SELECT r.target_name AS herb
                FROM relations r
                JOIN entities f ON f.id = r.source_id
                JOIN entities h ON h.id = r.target_id
                WHERE f.type = '方剂'
                  AND h.type = '药材'
                  AND f.name = ?
                  AND r.relation IN ('包含', '组成', '配伍')
                ORDER BY h.name
                """,
                (formula,),
            ).fetchall()
            result[formula] = [row["herb"] for row in rows]
        return result

    @staticmethod
    def _query_syndrome_formula_relations(conn: sqlite3.Connection, syndromes: list[str]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for syndrome in syndromes:
            rows = conn.execute(
                """
                SELECT r.source_name, r.relation, r.target_name, r.evidence
                FROM relations r
                JOIN entities s ON s.id = r.source_id
                JOIN entities f ON f.id = r.target_id
                WHERE s.type = '证候'
                  AND f.type = '方剂'
                  AND s.name = ?
                UNION
                SELECT r.target_name AS source_name, r.relation, r.source_name AS target_name, r.evidence
                FROM relations r
                JOIN entities f ON f.id = r.source_id
                JOIN entities s ON s.id = r.target_id
                WHERE s.type = '证候'
                  AND f.type = '方剂'
                  AND s.name = ?
                LIMIT 20
                """,
                (syndrome, syndrome),
            ).fetchall()
            result.extend(dict(row) for row in rows)
        return result

    @staticmethod
    def _count_relations_for_entities(conn: sqlite3.Connection, entity_ids: list[str]) -> int:
        if not entity_ids:
            return 0
        placeholders = ",".join("?" for _ in entity_ids)
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM relations
            WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})
            """,
            [*entity_ids, *entity_ids],
        ).fetchone()
        return int(row["count"] if row else 0)
