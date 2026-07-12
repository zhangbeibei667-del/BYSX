from backend.tools.sql_tool import GraphSQLTool


class GraphSQLAgent:
    """Call the graph-data SQL tool for structured graph metadata."""

    def __init__(self, sql_tool: GraphSQLTool | None = None) -> None:
        self.sql_tool = sql_tool or GraphSQLTool()

    def run(self, graph_result: dict, question: str = "") -> dict:
        print("[GraphSQLAgent] start")
        statistics = self.sql_tool.query_entity_statistics(
                syndromes=graph_result.get("syndromes", []),
                formulas=graph_result.get("formulas", []),
            )
        text_sql = self.sql_tool.text_to_sql(
            question, graph_result.get("syndromes", []), graph_result.get("formulas", [])
        )
        result = {"sql_result": {**statistics, "text_to_sql": text_sql}}
        print("[GraphSQLAgent] completed")
        return result
