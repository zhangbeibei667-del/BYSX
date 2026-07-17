import unittest
import uuid

from backend.services.agent_planner import AgentPlanner
from backend.services.vector_retrieval_service import VectorRetrievalService
from backend.services.data_quality_service import DataQualityService
from backend.tools.sql_tool import GraphSQLTool
from backend.tools.rag_tool import RAGRetrievalTool
from backend.services.llm_client import LLMClient
from backend.services.conversation_service import ConversationService
from backend.db.database import init_db
from backend.api.frontend_compat_api import evidence_to_sources


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
        self.assertTrue(ConversationService.requires_context("那该怎么办？"))
        self.assertFalse(ConversationService.requires_context("我最近总是失眠多梦，应该怎么调理？"))

    def test_lone_symptom_never_becomes_formula_recommendation(self):
        result = RAGRetrievalTool().query("失眠应该用什么方剂治疗？")
        self.assertEqual(result["mode"], "evidence-needs-clarification")
        self.assertTrue(result["needs_clarification"])
        self.assertEqual(result["formulas"], [])
        self.assertEqual(len(result["follow_up_questions"]), 1)
        self.assertIn("不能直接当作处方、用药或穴位建议", result["answer"])

    def test_lone_symptom_self_care_request_is_gated(self):
        result = RAGRetrievalTool().query("我最近总是失眠多梦，应该怎么调理？")
        self.assertEqual(result["mode"], "evidence-needs-clarification")
        self.assertTrue(result["needs_clarification"])
        self.assertEqual(result["generation"]["mode"], "evidence-gated-clarification")
        self.assertEqual(result["formulas"], [])
        self.assertNotIn("酸枣仁", result["answer"])
        self.assertNotIn("穴位治疗", result["answer"])
        self.assertIn("固定作息", result["answer"])
        self.assertIn("持续多久", result["follow_up_questions"][0])
        self.assertGreater(result["retrieval"]["document_hits"], 0)
        self.assertIn("RAG知识库资料", result["answer"])

    def test_clinical_rag_excludes_incidental_qa_documents(self):
        graph_result = {
            "syndromes": ["心脾两虚", "心肾不交"],
            "graph": {"nodes": [], "edges": []},
        }
        items = [
            {
                "title": "心肾不交证：常见疾病与相关说明", "category": "证候知识",
                "content": "不寐\n失眠多梦，腰膝酸软，心烦。", "score": 0.41,
            },
            {
                "title": "TCM-QG 文档 1247", "category": "文献问答",
                "content": "其他疾病中偶然提及失眠与心脾两虚。", "score": 0.48,
            },
        ]
        filtered = RAGRetrievalTool._filter_clinical_documents(
            "我最近失眠多梦并有腰膝酸软", graph_result, items
        )
        self.assertEqual([item["title"] for item in filtered], ["心肾不交证：常见疾病与相关说明"])

    def test_clinical_rerank_prioritizes_tongue_pulse_discriminators(self):
        graph_result = {
            "syndromes": ["痰热扰心", "少阴热化", "脾胃不和"],
            "graph": {"nodes": [], "edges": []},
        }
        items = [
            {"title": "脾胃不和证", "category": "证候知识", "content": "不寐\n乏力，胃脘不适。", "score": 0.5},
            {"title": "少阴热化证", "category": "证候知识", "content": "不寐\n腰膝酸软，舌红，脉数。", "score": 0.4},
            {"title": "痰热扰心证", "category": "证候知识", "content": "不寐\n苔黄腻，脉滑数。", "score": 0.39},
        ]
        filtered = RAGRetrievalTool._filter_clinical_documents(
            "我最近不寐、乏力、腰膝酸软，舌红、苔黄、脉数", graph_result, items
        )
        self.assertNotEqual(filtered[0]["title"], "脾胃不和证")
        self.assertEqual({item["title"] for item in filtered[:2]}, {"少阴热化证", "痰热扰心证"})

    def test_clinical_document_does_not_mix_disease_sections(self):
        item = {
            "title": "阴虚湿热证：常见疾病与相关说明",
            "category": "证候知识",
            "content": (
                "证候：阴虚湿热证\n"
                "1、痹病\n失眠多梦，腰膝酸软，舌红。\n"
                "2、泌尿系感染\n舌红苔黄腻，脉滑数。"
            ),
        }
        focused = RAGRetrievalTool._focus_clinical_document("我最近失眠多梦", item)
        self.assertIsNone(focused)

        insomnia_item = {
            **item,
            "content": "证候：心肾不交证\n1、惊悸\n心悸。\n2、不寐\n失眠多梦，腰膝酸软，舌红少苔，脉细数。",
        }
        focused = RAGRetrievalTool._focus_clinical_document("我最近失眠多梦", insomnia_item)
        self.assertIn("2、不寐", focused["content"])
        self.assertNotIn("1、惊悸", focused["content"])

    def test_clinical_fallback_exposes_graph_and_rag_evidence(self):
        result = {
            "syndromes": ["心脾两虚", "心肾不交"],
            "graph": {"nodes": [], "edges": []},
            "evidence": [{
                "title": "心肾不交证：常见疾病与相关说明",
                "source": "TCM-SD", "category": "证候知识", "content": "失眠多梦，腰膝酸软。",
            }],
        }
        answer = RAGRetrievalTool.clinical_safety_fallback("我最近失眠多梦", result)
        self.assertIn("教学性辨证分析", answer)
        self.assertIn("心肾不交证可以作为一个教学性辨证方向", answer)
        self.assertNotIn("文献片段对照显示", answer)
        self.assertNotIn("建议服用", answer)

    def test_evidence_scores_keep_document_and_graph_semantics_separate(self):
        sources = evidence_to_sources([
            {
                "title": "测试证候资料", "category": "证候知识", "document_id": 1,
                "content": "不寐相关说明", "score": 0.36,
            },
            {
                "title": "不寐—常见证候→心肾不交", "source": "《中医诊断学》",
                "content": "知识图谱关系：不寐—常见证候→心肾不交", "score": 1.0,
            },
            {
                "title": "腰膝酸软", "source": "图谱实体/症状",
                "content": "腰膝酸软实体命中", "score": 31.25,
            },
        ])
        self.assertEqual(sources[0]["score"], 0.36)
        self.assertEqual(sources[0]["metric_label"], "检索相关度")
        self.assertEqual(sources[1]["type"], "图谱关系")
        self.assertIsNone(sources[1]["score"])
        self.assertEqual(sources[1]["status_label"], "已验证关系")
        self.assertEqual(sources[2]["type"], "图谱实体")
        self.assertIsNone(sources[2]["score"])
        self.assertEqual(sources[2]["status_label"], "命中图谱实体")

        clinical_sources = evidence_to_sources([{
            "title": "不寐资料", "category": "证候知识", "document_id": 2,
            "content": "症见失眠多梦，舌红。治宜养阴。方用某方。", "score": 0.4,
        }], clinical=True)
        self.assertTrue(clinical_sources[0]["contains_treatment"])
        self.assertNotIn("治宜", clinical_sources[0]["original_text"])
        self.assertNotIn("方用", clinical_sources[0]["original_text"])

        confidence, score = RAGRetrievalTool._assess_evidence_confidence(
            True, [{"score": 0.36}], [{"score": 1.0}]
        )
        self.assertEqual(confidence, "medium")
        self.assertLess(score, 0.5)

    def test_rag_prompt_uses_question_specific_layout(self):
        evidence = {
            "evidence": [{"title": "测试资料", "citation": "测试资料 第一章", "content": "测试片段"}],
            "graph": {"edges": []},
        }
        comparison = RAGRetrievalTool.build_generation_messages(
            "麻黄汤和桂枝汤有什么区别？", evidence, "concise"
        )[0]["content"]
        factual = RAGRetrievalTool.build_generation_messages(
            "麻黄汤的组成是什么？", evidence, "concise"
        )[0]["content"]
        self.assertIn("紧凑表格", comparison)
        self.assertIn("自然段回答核心事实", factual)
        self.assertIn("详细来源由界面的“查看依据”展示", factual)

    def test_clarification_progress_keeps_partial_reply_gated(self):
        progress = RAGRetrievalTool.clarification_progress(
            "我最近总是失眠多梦，应该怎么调理？",
            "是入睡困难、易醒、早醒，每周大约3到4次",
        )
        self.assertFalse(progress["complete"])
        self.assertEqual(progress["answered"], ["sleep_pattern"])
        self.assertEqual(len(progress["remaining_questions"]), 1)
        self.assertIn("心悸", progress["remaining_questions"][0])

        unavailable = RAGRetrievalTool.clarification_progress(
            "我最近总是失眠多梦，应该怎么调理？",
            "主要是入睡困难，每周3-4次；伴有乏力；舌质、舌苔和脉象不清楚",
        )
        self.assertTrue(unavailable["finished"])
        self.assertFalse(unavailable["complete"])
        self.assertEqual(unavailable["unavailable"], ["tongue_body", "tongue_coat", "pulse"])

    def test_personal_clinical_output_blocks_concrete_treatment(self):
        self.assertTrue(RAGRetrievalTool.is_personal_clinical_request("我最近失眠，应该怎么调理？"))
        self.assertFalse(RAGRetrievalTool.clinical_output_is_safe("可参考天王补心丹加减，并使用酸枣仁。"))
        self.assertFalse(RAGRetrievalTool.clinical_output_is_safe("建议按摩神门穴，并配合食疗。"))
        self.assertFalse(RAGRetrievalTool.clinical_output_is_safe("睡前服用枸杞子约30克。"))
        self.assertFalse(RAGRetrievalTool.clinical_output_is_safe("证据等级 high，图谱路径如下。"))
        self.assertFalse(RAGRetrievalTool.clinical_output_is_safe("这些表现整体指向阴虚火旺，并与资料高度契合。"))
        self.assertFalse(RAGRetrievalTool.clinical_output_is_safe("苔黄而非资料中常见的少苔，因此存在矛盾。"))
        self.assertTrue(RAGRetrievalTool.clinical_output_is_safe("苔黄是苔色，少苔是苔量，两者可以同时出现。"))
        self.assertFalse(RAGRetrievalTool.clinical_output_is_safe("目前更倾向阴虚，治法重在滋阴清热。"))
        natural = RAGRetrievalTool.sanitize_clinical_answer(
            "这些表现整体呈现阴虚内热，更倾向于心肾不交，且与资料高度契合。"
        )
        self.assertNotIn("整体呈现", natural)
        self.assertNotIn("更倾向", natural)
        self.assertNotIn("高度契合", natural)
        self.assertTrue(RAGRetrievalTool.clinical_output_is_safe(natural))
        treatment_direction = RAGRetrievalTool.sanitize_clinical_answer(
            "目前可以整体偏向阴虚理解。建议以滋阴降火、交通心肾为调理方向，日常保持规律作息。"
        )
        self.assertNotIn("整体偏向", treatment_direction)
        self.assertNotIn("调理方向", treatment_direction)
        self.assertNotIn("滋阴降火", treatment_direction)
        self.assertTrue(RAGRetrievalTool.clinical_output_is_safe(treatment_direction))
        filtered = RAGRetrievalTool.remove_unsafe_clinical_sentences(
            "现有表现可先从心脾两虚方向理解，但仍需结合食欲和二便继续鉴别。"
            "日常可以服用山药、莲子进行食疗。"
            "目前只建议保持规律作息；若持续影响白天功能，应及时面诊。"
        )
        self.assertIn("心脾两虚", filtered)
        self.assertNotIn("山药", filtered)
        self.assertNotIn("莲子", filtered)
        self.assertTrue(RAGRetrievalTool.clinical_output_is_safe(filtered))
        hidden_treatment = RAGRetrievalTool.sanitize_clinical_answer(
            "腰膝酸软提示还要继续核对肾虚线索，需在调理心脾基础上兼顾固本。"
            "目前可先保持固定作息，并记录睡眠变化。"
        )
        self.assertNotIn("调理心脾", hidden_treatment)
        cited = RAGRetrievalTool.ensure_clinical_citation(
            "现有表现可先从心脾两虚方向继续核对。", 2
        )
        self.assertIn("[1]。", cited)
        relocated = RAGRetrievalTool.relocate_trailing_clinical_citations(
            "心脾两虚更值得优先核对。心肾不交目前依据较弱。"
            "本分析仅用于知识学习，不能替代专业诊疗[1][2]。",
            [{"candidate": "心脾两虚证"}, {"candidate": "心肾不交证"}],
        )
        self.assertIn("心脾两虚更值得优先核对[1]。", relocated)
        self.assertIn("心肾不交目前依据较弱[2]。", relocated)
        self.assertIn("不能替代专业诊疗。", relocated)
        safe = RAGRetrievalTool.clinical_safety_fallback(
            "我最近失眠", {"syndromes": ["心脾两虚", "心肾不交"]}
        )
        self.assertNotIn("天王补心丹", safe)
        self.assertIn("不会据此提供具体方剂", safe)

        vague_normal = RAGRetrievalTool.clarification_progress(
            "我最近失眠多梦", "入睡困难每周3次；伴有乏力；舌质、舌苔和脉象都正常"
        )
        self.assertTrue(vague_normal["finished"])
        self.assertTrue(vague_normal["complete"])
        self.assertEqual(vague_normal["unavailable"], [])
        self.assertEqual(
            vague_normal["low_confidence"],
            ["tongue_body", "coat_color", "coat_amount", "coat_texture", "pulse_rate", "pulse_shape"],
        )

    def test_clinical_dimensions_do_not_mix_coat_color_and_amount(self):
        dimensions = RAGRetrievalTool.parse_clinical_dimensions("舌红、苔黄、脉数")
        self.assertEqual(dimensions["tongue_body"]["values"], ["红"])
        self.assertEqual(dimensions["coat_color"]["values"], ["黄"])
        self.assertFalse(dimensions["coat_amount"]["observed"])
        self.assertFalse(dimensions["coat_texture"]["observed"])
        self.assertEqual(dimensions["pulse_rate"]["values"], ["数"])
        self.assertFalse(dimensions["pulse_shape"]["observed"])

        rows = RAGRetrievalTool.build_differential_evidence(
            "失眠多梦，舌红、苔黄、脉数",
            {"evidence": [{
                "title": "少阴热化证：辨证说明",
                "category": "证候知识",
                "content": "不寐，多梦，舌红少苔，脉细数。",
            }]},
        )
        self.assertEqual(len(rows), 1)
        self.assertFalse(any("苔黄" in item and "少" in item for item in rows[0]["differences"]))
        self.assertIn("苔量（资料为少）", rows[0]["missing"])
        self.assertIn("脉形（资料为细）", rows[0]["missing"])

        latest = RAGRetrievalTool.parse_clinical_dimensions(
            "舌苔是黄色，是薄、燥，不发腻\n舌苔：薄白，润度适中，不腻。"
        )
        self.assertEqual(latest["coat_color"]["values"], ["白"])
        self.assertEqual(latest["coat_texture"]["values"], ["薄", "润", "不腻"])

        next_step = RAGRetrievalTool.clarification_progress(
            "我最近总是失眠多梦，应该怎么调理？",
            "主要入睡困难，持续一个月，每周3-4次；伴有乏力；"
            "舌质淡红，接近正常；舌苔：薄白，润度适中，不腻。",
        )
        self.assertEqual(next_step["next_question_key"], "pulse")
        self.assertEqual(len(next_step["remaining_questions"]), 1)

        pulse_reply = "脉率平，不迟不数；脉象平和或略细，浮沉适中，无明显弦、滑等兼象。"
        pulse_dimensions = RAGRetrievalTool.parse_clinical_dimensions(pulse_reply)
        self.assertEqual(pulse_dimensions["pulse_rate"]["values"], ["平"])
        self.assertEqual(pulse_dimensions["pulse_shape"]["values"], ["平和", "细"])
        completed = RAGRetrievalTool.clarification_progress(
            "我最近总是失眠多梦，应该怎么调理？",
            "主要入睡困难，持续一个月，每周3-4次；伴有乏力；"
            "舌质淡红，接近正常；舌苔：薄白，润度适中，不腻；" + pulse_reply,
        )
        self.assertTrue(completed["complete"])
        self.assertEqual(completed["remaining_questions"], [])

        natural_pulse = (
            "脉象偏慢，表现为沉细、无力，以沉脉和细脉为主；"
            "没有明显弦、滑或浮的表现。"
        )
        natural_dimensions = RAGRetrievalTool.parse_clinical_dimensions(natural_pulse)
        self.assertEqual(natural_dimensions["pulse_rate"]["values"], ["迟"])
        self.assertEqual(natural_dimensions["pulse_shape"]["values"], ["细", "沉", "弱"])
        for excluded in ("弦", "滑", "浮"):
            self.assertNotIn(excluded, natural_dimensions["pulse_shape"]["values"])

    def test_standalone_unknown_resolves_current_clarification_question(self):
        progress = RAGRetrievalTool.clarification_progress(
            "畏寒怕冷，四肢不温，应该用什么药材？",
            "持续一个月；伴有乏力；舌质淡；舌苔薄白\n不清楚",
        )
        self.assertTrue(progress["finished"])
        self.assertFalse(progress["complete"])
        self.assertEqual(progress["unavailable"], ["pulse"])
        self.assertEqual(progress["remaining_questions"], [])

    def test_clarification_asks_one_high_information_question_per_turn(self):
        topic = "我最近总是失眠多梦，应该怎么调理？"
        stages = [
            ("主要入睡困难，每周3-4次", "companions"),
            ("主要入睡困难，每周3-4次；伴有乏力、腰膝酸软", "tongue_body"),
            ("主要入睡困难，每周3-4次；伴有乏力、腰膝酸软；舌红", "tongue_coat"),
            ("主要入睡困难，每周3-4次；伴有乏力、腰膝酸软；舌红、苔黄", "tongue_coat"),
            ("主要入睡困难，每周3-4次；伴有乏力、腰膝酸软；舌红、苔黄、薄苔", "pulse"),
            ("主要入睡困难，每周3-4次；伴有乏力、腰膝酸软；舌红、苔黄、薄苔、脉数", "pulse"),
        ]
        for text, expected_key in stages:
            with self.subTest(text=text):
                progress = RAGRetrievalTool.clarification_progress(topic, text)
                self.assertEqual(progress["next_question_key"], expected_key)
                self.assertEqual(len(progress["remaining_questions"]), 1)

        complete = RAGRetrievalTool.clarification_progress(
            topic,
            "主要入睡困难，每周3-4次；伴有乏力、腰膝酸软；舌红、苔黄、薄苔、脉细数",
        )
        self.assertTrue(complete["complete"])
        self.assertEqual(complete["remaining_questions"], [])


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
        self.assertEqual(restored["turns"][1]["response"]["answer"], "请补充舌象和脉象。")
        self.assertTrue(restored["turns"][0]["id"].startswith(session_id))
        self.assertTrue(restored["turns"][0]["timestamp"])
        self.assertTrue(any(item["id"] == session_id for item in service.list(1, 100)["list"]))
        self.assertTrue(service.delete(session_id))


if __name__ == "__main__":
    unittest.main()
