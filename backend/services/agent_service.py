try:
    # Keep this import shape for integration with the existing Agent package.
    from agents.orchestrator_agent import TCMTeachingOrchestratorAgent
except ModuleNotFoundError:
    from backend.agents.orchestrator_agent import TCMTeachingOrchestratorAgent

from backend.services.history_service import HistoryService


class AgentService:
    def __init__(self, history_service: HistoryService | None = None) -> None:
        self.history_service = history_service or HistoryService()

    def analyze_case(self, case_text: str) -> dict:
        agent = TCMTeachingOrchestratorAgent()
        result = agent.run(case_text)

        history_id = self.history_service.save_case_result(case_text, result)
        result["history_id"] = history_id
        return result
