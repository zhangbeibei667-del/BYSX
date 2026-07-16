import unittest
import uuid

from backend.services.agent_planner import AgentPlanner
from backend.services.vector_retrieval_service import VectorRetrievalService
from backend.services.data_quality_service import DataQualityService
from backend.tools.sql_tool import GraphSQLTool
from backend.services.llm_client import LLMClient
from backend.services.conversation_service import ConversationService
from backend.db.database import init_db


class DeliveryFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_dynamic_planner_selects_case_tools(self):
        plan = AgentPlanner().plan("患者失眠多梦，舌淡，脉细，请分析")
        self.assertEqual(plan["intent"], "case_analysis")
        self.assertIn("graph_query", plan["tools"])
        self.assertIn("sql_query", plan["tools"])
        self.assertIn("safety_review", plan["tools"])

    def test_vector_embedding_is_deterministic(self):
        service = VectorRetrievalService()
        first = service.embed("归脾汤健脾养心")
        second = service.embed("归脾汤健脾养心")
        self.assertEqual(first, second)
        self.assertAlmostEqual(sum(value * value for value in first), 1.0)

    def test_text_to_sql_is_read_only(self):
        tool = GraphSQLTool()
        result = tool.execute_readonly("SELECT type, COUNT(*) AS count FROM entities GROUP BY type")
        self.assertTrue(result["read_only"])
        self.assertGreater(result["row_count"], 0)
        with self.assertRaises(ValueError):
            tool.execute_readonly("DELETE FROM entities")
        with self.assertRaises(ValueError):
            tool.execute_readonly("SELECT * FROM sqlite_master")

    def test_required_corpus_categories_exist(self):
        report = DataQualityService().report()
        available = {item["category"] for item in report["corpus"]["categories"]}
        self.assertTrue(set(report["corpus"]["required_categories"]).issubset(available))
        self.assertEqual(report["vector_database"]["status"], "ready")

    def test_kg_quality_gate_is_clean(self):
        gate = DataQualityService().report()["quality_gate"]
        self.assertTrue(gate["passed"])
        self.assertTrue(all(value == 0 for value in gate["critical"].values()))
        self.assertEqual(gate["warnings"]["endpoint_name_mismatches"], 0)

    def test_llm_status_never_exposes_key(self):
        status = LLMClient().status()
        self.assertNotIn("api_key", status)
        self.assertIn(status["provider"], {"deepseek", "aliyun-bailian"})

    def test_followup_context_contains_previous_topic(self):
        session = {"turns": [
            {"role": "user", "content": "失眠应该用什么方剂？"},
            {"role": "assistant", "content": "需要结合舌脉辨证。"},
        ], "collected": {}, "pending_questions": [], "status": "answered"}
        context = ConversationService.contextualize(session, "那该怎么办？")
        self.assertIn("失眠应该用什么方剂", context)
        self.assertIn("本轮问题：那该怎么办", context)


    def test_conversation_round_trip_and_followup_state(self):
        service = ConversationService()
        session_id = f"test-{uuid.uuid4().hex}"
        session = service.load(session_id)
        result = {
            "answer": "请补充舌象和脉象。", "symptoms": ["失眠"], "tongue": [], "pulse": [],
            "follow_up_questions": ["舌象如何？", "脉象如何？"], "needs_clarification": True,
        }
        service.save_turn(session, "患者失眠", result)
        restored = service.load(session_id)
        self.assertEqual(restored["status"], "awaiting_clarification")
        self.assertEqual(restored["collected"]["symptoms"], ["失眠"])
        self.assertEqual(len(restored["turns"]), 2)
        self.assertTrue(any(item["id"] == session_id for item in service.list(1, 100)["list"]))
        self.assertTrue(service.delete(session_id))


if __name__ == "__main__":
    unittest.main()
