from backend.tools.sql_tool import GraphSQLTool


class SQLService:
    """Graph data SQL Agent service backed by the local SQLite KG."""

    def __init__(self, sql_tool: GraphSQLTool | None = None) -> None:
        self.sql_tool = sql_tool or GraphSQLTool()

    def query(self, question: str, syndromes: list[str] | None = None, formulas: list[str] | None = None) -> dict:
        result = self.sql_tool.query_entity_statistics(
            syndromes=syndromes or [],
            formulas=formulas or [],
        )
        return {
            "question": question,
            "sql_result": result,
            "mode": "sqlite",
        }
