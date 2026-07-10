from backend.tools.sql_tool import GraphSQLTool


class GraphSQLAgent:
    """Call the graph-data SQL tool for structured graph metadata."""

    def __init__(self, sql_tool: GraphSQLTool | None = None) -> None:
        self.sql_tool = sql_tool or GraphSQLTool()

    def run(self, graph_result: dict) -> dict:
        print("[GraphSQLAgent] start")
        result = {
            "sql_result": self.sql_tool.query_entity_statistics(
                syndromes=graph_result.get("syndromes", []),
                formulas=graph_result.get("formulas", []),
            )
        }
        print("[GraphSQLAgent] completed")
        return result
