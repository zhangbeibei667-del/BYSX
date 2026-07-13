"""Graph SQL Agent — NL→SQL for structured KG metadata queries.

Called by TCMTeachingOrchestratorAgent.  Receives the user's original case text
plus any syndromes / formulas already identified by the GraphReasoningAgent,
then generates and executes a targeted SQL query against the knowledge graph.
"""

from __future__ import annotations

from backend.tools.sql_tool import GraphSQLTool


class GraphSQLAgent:
    """Call the graph-data SQL tool for structured graph metadata.

    Unlike the previous version which only returned statistics, this agent
    now generates a real NL→SQL query from the user's case text, executes it,
    and returns both the generated SQL and the result rows.
    """

    def __init__(self, sql_tool: GraphSQLTool | None = None) -> None:
        self.sql_tool = sql_tool or GraphSQLTool()

    def run(self, graph_result: dict, case_text: str = "") -> dict:
        """Run the SQL Agent pipeline.

        Parameters
        ----------
        graph_result : dict
            Output from GraphReasoningAgent — contains 'syndromes', 'formulas',
            'herbs', and 'graph'.
        case_text : str
            The user's original question / case description.  Used as the
            natural-language input for Text-to-SQL generation.

        Returns
        -------
        dict
            {sql_result: {...}, generated_sql: str, explanation: str, ...}
        """
        print("[GraphSQLAgent] start")

        syndromes = graph_result.get("syndromes", [])
        formulas = graph_result.get("formulas", [])

        # Build a focused NL question from available context
        question = self._build_question(case_text, syndromes, formulas)

        # Full NL→SQL pipeline
        text_to_sql_result = self.sql_tool.text_to_sql(
            question, syndromes=syndromes, formulas=formulas,
        )

        # Also get statistics for downstream agents
        statistics = self.sql_tool.query_entity_statistics(
            syndromes=syndromes, formulas=formulas,
        )

        # Build a human-readable explanation of the SQL results
        explanation = self._build_explanation(
            question=question,
            generated_sql=text_to_sql_result.get("generated_sql", ""),
            rows=text_to_sql_result.get("rows", []),
            row_count=text_to_sql_result.get("row_count", 0),
        )

        result = {
            "sql_result": {
                **statistics,
                "text_to_sql": {
                    "question": question,
                    "generated_sql": text_to_sql_result.get("generated_sql", ""),
                    "rows": text_to_sql_result.get("rows", []),
                    "row_count": text_to_sql_result.get("row_count", 0),
                    "status": text_to_sql_result.get("status", "error"),
                    "generator": text_to_sql_result.get("generator", "unknown"),
                    "model_used": text_to_sql_result.get("model_used", ""),
                },
            },
            "generated_sql": text_to_sql_result.get("generated_sql", ""),
            "sql_explanation": explanation,
            "sql_mode": self.sql_tool.active_mode,
            "sql_error": text_to_sql_result.get("error"),
        }

        print("[GraphSQLAgent] completed")
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_question(
        case_text: str, syndromes: list[str], formulas: list[str],
    ) -> str:
        """Compose a focused NL question from available context."""
        parts = []

        if case_text and case_text.strip():
            parts.append(case_text.strip())

        if syndromes:
            parts.append(f"相关证候：{'、'.join(syndromes)}")
        if formulas:
            parts.append(f"相关方剂：{'、'.join(formulas)}")

        if not parts:
            return "查询图谱实体统计"

        return "；".join(parts)

    @staticmethod
    def _build_explanation(
        question: str, generated_sql: str,
        rows: list[dict], row_count: int,
    ) -> str:
        """Build a brief human-readable summary of what the SQL query found."""
        if not generated_sql:
            return "未能生成有效的 SQL 查询。"

        if row_count == 0:
            return f"执行了 SQL 查询，但未找到匹配的数据。（SQL: {generated_sql[:120]}...）"

        # Extract key entity names from result rows for a natural summary
        entity_names: list[str] = []
        for row in rows[:10]:
            for key in ("name", "herb", "formula", "syndrome", "target_name", "source_name"):
                val = row.get(key)
                if val and str(val) not in entity_names:
                    entity_names.append(str(val))

        if entity_names:
            sample = "、".join(entity_names[:8])
            return (
                f"SQL 查询返回 {row_count} 条记录，"
                f"涉及：{sample}"
                f"{'等' if len(entity_names) > 8 else ''}。"
            )

        return f"SQL 查询返回 {row_count} 条结构化数据记录。"
