try:
    # Keep this import shape for integration with the existing Agent package.
    from agents.orchestrator_agent import TCMTeachingOrchestratorAgent
except ModuleNotFoundError:
    from backend.agents.orchestrator_agent import TCMTeachingOrchestratorAgent

from backend.services.history_service import HistoryService
from backend.db.database import init_db
from backend.services.conversation_service import ConversationService


class AgentService:
    def __init__(self, history_service: HistoryService | None = None) -> None:
        init_db()
        self.history_service = history_service or HistoryService()

    def analyze_case(self, case_text: str, has_context: bool = False,
                     generate_answer: bool = True) -> dict:
        agent = TCMTeachingOrchestratorAgent()
        result = agent.run(
            case_text,
            has_context=has_context,
            generate_answer=generate_answer,
        )

        history_id = self.history_service.save_case_result(case_text, result)
        result["history_id"] = history_id
        return result

    def chat(self, question: str, session_id: str | None = None) -> dict:
        conversations = ConversationService()
        session = conversations.load(session_id)
        contextualized = conversations.contextualize(session, question)
        result = self.analyze_case(contextualized, has_context=bool(session["turns"]))
        conversations.save_turn(session, question, result)
        result["conversation"] = {
            "id": session["id"], "status": session["status"],
            "turn_count": len(session["turns"]) // 2, "collected": session["collected"],
            "pending_questions": session["pending_questions"],
        }
        return result
