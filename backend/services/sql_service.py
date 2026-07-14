"""Graph data SQL Agent service.

Wraps GraphSQLTool and implements the full NL→SQL→execute→enrich pipeline.
"""

from __future__ import annotations

from backend.tools.sql_tool import GraphSQLTool


class SQLService:
    """Graph data SQL Agent service backed by the local SQLite KG (with MySQL fallback)."""

    def __init__(self, sql_tool: GraphSQLTool | None = None) -> None:
        self.sql_tool = sql_tool or GraphSQLTool()

    # ------------------------------------------------------------------
    # Primary entry point: NL question → SQL → result
    # ------------------------------------------------------------------

    def query(
        self,
        question: str,
        syndromes: list[str] | None = None,
        formulas: list[str] | None = None,
    ) -> dict:
        """Translate a natural-language question into SQL, execute it, and return results.

        This is the main improvement over the previous version which ignored
        the *question* parameter entirely.
        """
        text_to_sql_result = self.sql_tool.text_to_sql(
            question, syndromes=syndromes, formulas=formulas,
        )

        return {
            "question": question,
            "generated_sql": text_to_sql_result.get("generated_sql", ""),
            "sql_result": {
                "rows": text_to_sql_result.get("rows", []),
                "row_count": text_to_sql_result.get("row_count", 0),
                "status": text_to_sql_result.get("status", "error"),
            },
            "generator": text_to_sql_result.get("generator", "unknown"),
            "model_used": text_to_sql_result.get("model_used", ""),
            "mode": self.sql_tool.active_mode,
            "error": text_to_sql_result.get("error"),
        }

    # ------------------------------------------------------------------
    # Context-rich query for the Orchestrator
    # ------------------------------------------------------------------

    def query_with_context(
        self,
        question: str,
        syndromes: list[str] | None = None,
        formulas: list[str] | None = None,
        include_statistics: bool = True,
    ) -> dict:
        """Like query() but also includes entity statistics for downstream agents."""
        result = self.query(question, syndromes=syndromes, formulas=formulas)

        if include_statistics:
            result["statistics"] = self.sql_tool.query_entity_statistics(
                syndromes=syndromes, formulas=formulas,
            )

        result["schema_info"] = self.sql_tool.get_schema_info()
        return result

    # ------------------------------------------------------------------
    # Direct SQL execution (for admin / debug use)
    # ------------------------------------------------------------------

    def execute_direct_sql(self, sql: str, params: list | None = None) -> dict:
        """Execute a hand-written SQL statement (read-only, safety-validated)."""
        return self.sql_tool.execute_readonly(sql, params)

    # ------------------------------------------------------------------
    # Schema & statistics
    # ------------------------------------------------------------------

    def get_schema(self) -> dict:
        """Return the current KG schema for API consumers."""
        return self.sql_tool.get_schema_info()

    def get_statistics(self, refresh: bool = False) -> dict:
        """Return KG statistics, optionally forcing a schema refresh."""
        if refresh:
            self.sql_tool.refresh_database()
            self.sql_tool.refresh_schema_cache()
        stats = self.sql_tool.query_entity_statistics()
        stats["schema_info"] = self.sql_tool.get_schema_info()
        stats["mode"] = self.sql_tool.active_mode
        return stats

    def refresh(self) -> dict:
        """Force a database + schema refresh and return the new state."""
        self.sql_tool.refresh_database()
        self.sql_tool.refresh_schema_cache()
        return {
            "status": "refreshed",
            "mode": self.sql_tool.active_mode,
            "schema_info": self.sql_tool.get_schema_info(),
        }
