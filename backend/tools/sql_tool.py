"""Graph SQL Tool — LLM-driven Text-to-SQL with MySQL + SQLite dual backend.

Primary path:   MySQL (via server.store_mysql.MySQLStore) — real-time KG data.
Fallback path:  Local SQLite (backend/data/kg.sqlite) — offline / no-MySQL mode.

Safety: all SQL passes through execute_readonly() which enforces SELECT-only,
table whitelist, and row limits regardless of which backend executes it.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from backend.prompts.text_to_sql import TEXT_TO_SQL_SYSTEM_PROMPT, build_user_prompt
from backend.scripts.sync_kg_sqlite import sync_kg_sqlite

logger = logging.getLogger(__name__)


class GraphSQLTool:
    """SQL Agent backed by MySQL (primary) with local SQLite fallback.

    On init it tries to open a MySQL connection through the shared
    server.store_mysql module.  If that fails — missing driver, unreachable
    server, wrong credentials — it silently degrades to the local SQLite copy.
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(
        self,
        db_path: str | Path | None = None,
        use_mysql: bool = True,
    ) -> None:
        workspace_root = Path(__file__).resolve().parents[2]
        self.db_path = Path(db_path) if db_path else workspace_root / "backend" / "data" / "kg.sqlite"
        self._mysql_store: Any = None
        self._mysql_available: bool = False

        if use_mysql:
            self._init_mysql()

        # Ensure the SQLite fallback exists
        self.ensure_database()

        # Cached schema info for prompt injection
        self._schema_cache: dict | None = None

    def _init_mysql(self) -> None:
        """Try to open a MySQL connection via the shared server.store_mysql module."""
        try:
            from server.config import STORE_BACKEND, MYSQL_HOST, MYSQL_PORT, \
                MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
            from server.store_mysql import MySQLStore

            if STORE_BACKEND in ("mysql", "hybrid"):
                self._mysql_store = MySQLStore(
                    host=MYSQL_HOST, port=MYSQL_PORT,
                    user=MYSQL_USER, password=MYSQL_PASSWORD,
                    database=MYSQL_DATABASE,
                )
                # Smoke-test the connection
                self._mysql_store.stats()
                self._mysql_available = True
                logger.info("GraphSQLTool: MySQL connection established")
            else:
                logger.info("GraphSQLTool: STORE_BACKEND=%s, skipping MySQL", STORE_BACKEND)
        except Exception as exc:
            logger.warning("GraphSQLTool: MySQL unavailable (%s), falling back to SQLite", exc)
            self._mysql_store = None
            self._mysql_available = False

    # ------------------------------------------------------------------
    # Database lifecycle
    # ------------------------------------------------------------------

    def ensure_database(self) -> None:
        """Create / refresh the local SQLite copy if it is missing or empty."""
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            sync_kg_sqlite(self.db_path)

    def refresh_database(self) -> None:
        """Force a full re-sync of the SQLite copy.

        If MySQL is available the sync is pulled from there; otherwise it
        re-reads the entities/relations JSON files.
        """
        if self._mysql_available and self._mysql_store is not None:
            try:
                self._mysql_store.sync_to_sqlite(str(self.db_path))
                self._schema_cache = None
                logger.info("GraphSQLTool: synced SQLite from MySQL")
                return
            except Exception as exc:
                logger.warning("GraphSQLTool: MySQL sync failed (%s), using JSON", exc)
        sync_kg_sqlite(self.db_path)
        self._schema_cache = None

    @property
    def active_mode(self) -> str:
        """Return 'mysql' or 'sqlite' depending on what is currently available."""
        return "mysql" if self._mysql_available else "sqlite"

    # ------------------------------------------------------------------
    # Schema information (for LLM prompt injection)
    # ------------------------------------------------------------------

    def get_schema_info(self) -> dict:
        """Return table schemas, type enumerations, and row counts.

        Cached in self._schema_cache until the next refresh_database() call.
        """
        if self._schema_cache is not None:
            return self._schema_cache

        # Try MySQL first
        if self._mysql_available and self._mysql_store is not None:
            try:
                info = self._get_schema_from_mysql()
                self._schema_cache = info
                return info
            except Exception:
                pass

        info = self._get_schema_from_sqlite()
        self._schema_cache = info
        return info

    def _get_schema_from_mysql(self) -> dict:
        store = self._mysql_store
        stats = store.stats()
        entity_types = sorted(stats.get("entity_by_type", {}).keys())
        relation_types = sorted(stats.get("relation_by_type", {}).keys())
        return {
            "entity_columns": ["id", "name", "type", "alias", "description", "properties_json"],
            "relation_columns": ["source_id", "source_name", "source_type", "relation",
                                 "target_id", "target_name", "target_type", "evidence"],
            "entity_types": entity_types,
            "relation_types": relation_types,
            "entity_count": stats.get("entity_count", 0),
            "relation_count": stats.get("relation_count", 0),
            "source": "mysql",
        }

    def _get_schema_from_sqlite(self) -> dict:
        self.ensure_database()
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            entity_types = [
                row["type"] for row in
                conn.execute("SELECT DISTINCT type FROM entities ORDER BY type")
            ]
            relation_types = [
                row["relation"] for row in
                conn.execute("SELECT DISTINCT relation FROM relations ORDER BY relation")
            ]
            entity_count = conn.execute("SELECT COUNT(*) AS c FROM entities").fetchone()["c"]
            relation_count = conn.execute("SELECT COUNT(*) AS c FROM relations").fetchone()["c"]
        return {
            "entity_columns": ["id", "name", "type", "alias", "description", "properties_json"],
            "relation_columns": ["source_id", "source_name", "source_type", "relation",
                                 "target_id", "target_name", "target_type", "evidence"],
            "entity_types": entity_types,
            "relation_types": relation_types,
            "entity_count": entity_count,
            "relation_count": relation_count,
            "source": "sqlite",
        }

    def refresh_schema_cache(self) -> None:
        """Clear cached schema so the next get_schema_info() re-queries."""
        self._schema_cache = None

    # ------------------------------------------------------------------
    # Safe SQL executor (dual-backend)
    # ------------------------------------------------------------------

    def execute_readonly(
        self, sql: str, params: list[Any] | None = None, max_rows: int = 100,
    ) -> dict:
        """Validate and execute one read-only SELECT statement.

        Tries MySQL first; falls back to SQLite on any error.
        """
        # --- Normalise & safety-validate ---
        normalized = re.sub(r"\s+", " ", sql.strip()).rstrip(";")
        if not re.match(r"^(SELECT|WITH)\b", normalized, re.IGNORECASE):
            raise ValueError("SQL Agent 只允许 SELECT/WITH 只读查询")
        if ";" in normalized or re.search(
            r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|VACUUM)\b",
            normalized, re.IGNORECASE,
        ):
            raise ValueError("检测到不安全或多语句 SQL")

        # Table whitelist
        tables = set(re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][\w]*)", normalized, re.IGNORECASE))
        if not tables or not tables.issubset({"entities", "relations", "metadata"}):
            raise ValueError(f"只允许访问知识图谱白名单表，当前表：{sorted(tables)}")

        # Auto-append LIMIT
        limited = normalized
        if not re.search(r"\bLIMIT\s+\d+", normalized, re.IGNORECASE):
            limited = f"{normalized} LIMIT {max_rows}"

        # --- Execute: MySQL first ---
        if self._mysql_available and self._mysql_store is not None:
            try:
                result = self._mysql_store.execute_readonly_sql(limited, params or [], max_rows)
                result["backend"] = "mysql"
                return result
            except Exception as exc:
                logger.warning("MySQL execute_readonly failed (%s), trying SQLite", exc)

        # --- Execute: SQLite fallback ---
        self.ensure_database()
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            conn.execute("EXPLAIN QUERY PLAN " + limited, params or [])
            rows = [dict(row) for row in conn.execute(limited, params or []).fetchmany(max_rows)]
        return {
            "status": "success", "sql": limited, "rows": rows,
            "row_count": len(rows), "database": str(self.db_path),
            "read_only": True, "backend": "sqlite",
        }

    # ------------------------------------------------------------------
    # NL → SQL (LLM-driven with template fallback)
    # ------------------------------------------------------------------

    def generate_sql(
        self, question: str,
        syndromes: list[str] | None = None,
        formulas: list[str] | None = None,
    ) -> dict:
        """Use LLM to translate a natural-language question into safe SQL.

        Returns {"sql": ..., "generator": "llm"|"llm-error", "model": ...}
        """
        from backend.services.llm_client import get_llm_client

        llm = get_llm_client()
        if not llm.available:
            return {"sql": "", "generator": "llm-unavailable", "model": "", "error": llm.last_error}

        messages = [
            {"role": "system", "content": TEXT_TO_SQL_SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(question, syndromes, formulas)},
        ]

        response = llm.complete(messages, temperature=0.0)
        if not response:
            return {"sql": "", "generator": "llm-error", "model": "", "error": llm.last_error}

        raw = response["content"].strip()
        # Strip markdown code fences if the model wraps the output
        raw = re.sub(r"^```(?:sql)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        sql = raw.strip().rstrip(";")

        # Basic sanity: must start with SELECT / WITH
        if not re.match(r"^(SELECT|WITH)\b", sql, re.IGNORECASE):
            return {
                "sql": "", "generator": "llm-invalid",
                "model": response.get("model", ""),
                "raw_output": raw,
                "error": "LLM 输出不是有效的 SELECT/WITH 语句",
            }

        return {
            "sql": sql, "generator": "llm",
            "model": response.get("model", ""),
            "usage": response.get("usage", {}),
        }

    def text_to_sql(
        self, question: str,
        syndromes: list[str] | None = None,
        formulas: list[str] | None = None,
    ) -> dict:
        """Full pipeline: NL question → SQL → execute → result.

        1. Try LLM generation first.
        2. Fall back to template-based generation if LLM is unavailable or fails.
        3. Validate and execute the generated SQL.
        """
        syndromes = syndromes or []
        formulas = formulas or []

        # --- Step 1: LLM generation ---
        gen = self.generate_sql(question, syndromes, formulas)
        sql = gen.get("sql", "")

        # --- Step 2: Template fallback ---
        if not sql:
            sql, params = self._template_sql(question, syndromes, formulas)
            gen = {"generator": "template", "model": "", "sql": sql, "parameters": params}

        # --- Step 3: Execute ---
        try:
            params = gen.get("parameters", [])
            result = self.execute_readonly(sql, params if params else None)
            result.update({
                "question": question,
                "generated_sql": sql,
                "generator": gen.get("generator", "unknown"),
                "model_used": gen.get("model", ""),
            })
            if gen.get("error"):
                result["generation_error"] = gen["error"]
            return result
        except ValueError as exc:
            return {
                "status": "rejected", "question": question,
                "generated_sql": sql, "generator": gen.get("generator", "unknown"),
                "model_used": gen.get("model", ""),
                "error": str(exc), "rows": [], "row_count": 0,
            }

    # ------------------------------------------------------------------
    # Template-based SQL generation (fallback)
    # ------------------------------------------------------------------

    @staticmethod
    def _template_sql(
        question: str, syndromes: list[str], formulas: list[str],
    ) -> tuple[str, list]:
        """Hard-coded templates for common KG question patterns.

        These are the fallback when LLM is unavailable.  Kept from the
        original implementation and extended with a few more patterns.
        """
        # --- Pattern: formula composition ---
        if formulas:
            sql = (
                "SELECT r.source_name AS formula, r.relation, "
                "r.target_name AS herb, r.evidence "
                "FROM relations r JOIN entities e ON e.id = r.source_id "
                "WHERE e.name = ? AND r.relation IN ('包含', '组成', '配伍') "
                "ORDER BY r.target_name LIMIT 100"
            )
            return sql, [formulas[0]]

        # --- Pattern: syndrome → formulas ---
        if syndromes:
            sql = (
                "SELECT DISTINCT r.source_name, r.relation, r.target_name, r.evidence "
                "FROM relations r "
                "WHERE (r.source_name = ? OR r.target_name = ?) LIMIT 100"
            )
            return sql, [syndromes[0], syndromes[0]]

        # --- Pattern: statistics ---
        if any(word in question for word in ("数量", "多少", "统计", "概况", "概览", "总共")):
            sql = (
                "SELECT type, COUNT(*) AS count FROM entities "
                "GROUP BY type ORDER BY count DESC"
            )
            return sql, []

        # --- Pattern: entity type listing ---
        type_keywords = {
            "药材": ["药材", "草药", "中药", "herb"],
            "方剂": ["方剂", "汤剂", "处方", "formula"],
            "症状": ["症状", "表现", "symptom"],
            "证候": ["证候", "证型", "syndrome"],
            "功效": ["功效", "作用", "effect"],
            "禁忌": ["禁忌", "注意事项", "contraindication"],
            "文献": ["文献", "来源", "出处", "literature"],
        }
        for entity_type, keywords in type_keywords.items():
            if any(kw in question for kw in keywords):
                sql = (
                    "SELECT id, name, type, alias, description "
                    "FROM entities WHERE type = ? ORDER BY name LIMIT 100"
                )
                return sql, [entity_type]

        # --- Pattern: keyword search (default) ---
        keyword = re.sub(r"[？?，,。\s]", "", question)
        if len(keyword) > 12:
            keyword = keyword[-12:]
        sql = (
            "SELECT id, name, type, alias, description FROM entities "
            "WHERE name LIKE ? OR alias LIKE ? ORDER BY name LIMIT 50"
        )
        return sql, [f"%{keyword}%", f"%{keyword}%"]

    # ------------------------------------------------------------------
    # Entity statistics (unchanged — keeps existing behaviour)
    # ------------------------------------------------------------------

    def query_entity_statistics(
        self, syndromes: list[str] | None = None, formulas: list[str] | None = None,
    ) -> dict:
        """Return rich KG statistics + matched entities for the orchestrator."""
        self.ensure_database()
        syndromes = syndromes or []
        formulas = formulas or []

        # --- Query from MySQL if available ---
        if self._mysql_available and self._mysql_store is not None:
            try:
                return self._query_stats_mysql(syndromes, formulas)
            except Exception:
                pass

        # --- SQLite fallback ---
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            entity_counts = {
                row["type"]: row["count"]
                for row in conn.execute(
                    "SELECT type, COUNT(*) AS count FROM entities GROUP BY type ORDER BY type"
                )
            }
            relation_count = conn.execute(
                "SELECT COUNT(*) AS count FROM relations"
            ).fetchone()["count"]

            matched_syndromes = self._match_entities(conn, "证候", syndromes)
            matched_formulas = self._match_entities(conn, "方剂", formulas)
            formula_herbs = self._query_formula_herbs(
                conn, [item["name"] for item in matched_formulas],
            )
            syndrome_formula_relations = self._query_syndrome_formula_relations(
                conn, [item["name"] for item in matched_syndromes],
            )
            matched_relation_count = self._count_relations_for_entities(
                conn, [item["id"] for item in [*matched_syndromes, *matched_formulas]],
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
            "note": "SQL Agent queried the local SQLite knowledge-graph database.",
        }

    def _query_stats_mysql(self, syndromes: list[str], formulas: list[str]) -> dict:
        """Gather statistics from MySQL."""
        store = self._mysql_store
        stats = store.stats()
        eb = stats.get("entity_by_type", {})

        # Match entities via MySQL
        matched_syndromes = self._match_entities_mysql("证候", syndromes)
        matched_formulas = self._match_entities_mysql("方剂", formulas)
        formula_herbs = self._query_formula_herbs_mysql(
            [item["name"] for item in matched_formulas],
        )
        syndrome_formula_relations = self._query_syndrome_formula_relations_mysql(
            [item["name"] for item in matched_syndromes],
        )

        return {
            "status": "mysql",
            "database": f"{store._conn_params.get('host', '')}:{store._conn_params.get('port', '')}/{store._conn_params.get('database', '')}",
            "entity_counts": {
                "symptom": eb.get("症状", 0),
                "syndrome": eb.get("证候", 0),
                "formula": eb.get("方剂", 0),
                "herb": eb.get("药材", 0),
                "effect": eb.get("功效", 0),
                "contraindication": eb.get("禁忌", 0),
                "literature": eb.get("文献", 0),
                "total": stats.get("entity_count", 0),
            },
            "relation_count": stats.get("relation_count", 0),
            "matched_syndromes": matched_syndromes,
            "matched_formulas": matched_formulas,
            "matched_entity_count": len(matched_syndromes) + len(matched_formulas),
            "matched_relation_count": 0,
            "formula_herbs": formula_herbs,
            "syndrome_formula_relations": syndrome_formula_relations,
            "note": "SQL Agent queried MySQL knowledge-graph database.",
        }

    # ------------------------------------------------------------------
    # Entity matching helpers
    # ------------------------------------------------------------------

    def _match_entities_mysql(self, entity_type: str, names: list[str]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for name in names:
            name = str(name).strip()
            if not name:
                continue
            _, rows = self._mysql_store.list_entities(entity_type, name, 1, 10)
            for row in rows:
                d = row.model_dump() if hasattr(row, "model_dump") else dict(row)
                eid = d.get("id", "")
                if eid in seen:
                    continue
                seen.add(eid)
                result.append(d)
        return result

    def _query_formula_herbs_mysql(self, formulas: list[str]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for formula in formulas:
            try:
                sql = (
                    "SELECT r.target_name AS herb FROM relations r "
                    "JOIN entities f ON f.id = r.source_id "
                    "JOIN entities h ON h.id = r.target_id "
                    "WHERE f.type = '方剂' AND h.type = '药材' "
                    "AND f.name = %s "
                    "AND r.relation IN ('包含', '组成', '配伍') "
                    "ORDER BY h.name LIMIT 50"
                )
                res = self._mysql_store.execute_readonly_sql(sql, [formula])
                result[formula] = [row["herb"] for row in res.get("rows", [])]
            except Exception:
                result[formula] = []
        return result

    def _query_syndrome_formula_relations_mysql(self, syndromes: list[str]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for syndrome in syndromes:
            try:
                sql = (
                    "SELECT r.source_name, r.relation, r.target_name, r.evidence "
                    "FROM relations r "
                    "JOIN entities s ON s.id = r.source_id "
                    "JOIN entities f ON f.id = r.target_id "
                    "WHERE s.type = '证候' AND f.type = '方剂' AND s.name = %s "
                    "UNION "
                    "SELECT r.target_name AS source_name, r.relation, "
                    "r.source_name AS target_name, r.evidence "
                    "FROM relations r "
                    "JOIN entities f ON f.id = r.source_id "
                    "JOIN entities s ON s.id = r.target_id "
                    "WHERE s.type = '证候' AND f.type = '方剂' AND s.name = %s "
                    "LIMIT 20"
                )
                res = self._mysql_store.execute_readonly_sql(sql, [syndrome, syndrome])
                result.extend(res.get("rows", []))
            except Exception:
                pass
        return result

    # ------------------------------------------------------------------
    # Static helpers (shared between MySQL and SQLite paths)
    # ------------------------------------------------------------------

    @staticmethod
    def _match_entities(
        conn: sqlite3.Connection, entity_type: str, names: list[str],
    ) -> list[dict[str, Any]]:
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
    def _query_formula_herbs(
        conn: sqlite3.Connection, formulas: list[str],
    ) -> dict[str, list[str]]:
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
    def _query_syndrome_formula_relations(
        conn: sqlite3.Connection, syndromes: list[str],
    ) -> list[dict[str, Any]]:
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
                SELECT r.target_name AS source_name, r.relation,
                       r.source_name AS target_name, r.evidence
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
    def _count_relations_for_entities(
        conn: sqlite3.Connection, entity_ids: list[str],
    ) -> int:
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
