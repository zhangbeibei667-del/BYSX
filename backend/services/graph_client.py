from backend.tools.graph_tool import GraphQueryTool


class GraphClient:
    """Client wrapper for knowledge graph access.

    TODO: Replace GraphQueryTool with a real graph service client, such as
    Neo4j Cypher, HTTP graph API, or another teammate's graph backend.
    """

    def __init__(self, graph_tool: GraphQueryTool | None = None) -> None:
        self.graph_tool = graph_tool or GraphQueryTool()

    def query_by_symptoms(self, symptoms: list[str]) -> dict:
        return self.graph_tool.query_by_symptoms(symptoms)
