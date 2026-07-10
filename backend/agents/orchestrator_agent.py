from backend.agents.followup_question_agent import FollowUpQuestionAgent
from backend.agents.formula_explanation_agent import FormulaExplanationAgent
from backend.agents.graph_reasoning_agent import GraphReasoningAgent
from backend.agents.knowledge_explanation_agent import KnowledgeExplanationAgent
from backend.agents.literature_retrieval_agent import LiteratureRetrievalAgent
from backend.agents.safety_review_agent import SafetyReviewAgent
from backend.agents.sql_agent import GraphSQLAgent
from backend.agents.streaming_voice_agent import StreamingVoiceQAAgent
from backend.agents.symptom_analysis_agent import SymptomAnalysisAgent


class TCMTeachingOrchestratorAgent:
    """Coordinate the teaching multi-agent workflow and expose step traces."""

    def __init__(self) -> None:
        self.symptom_agent = SymptomAnalysisAgent()
        self.followup_agent = FollowUpQuestionAgent()
        self.graph_agent = GraphReasoningAgent()
        self.sql_agent = GraphSQLAgent()
        self.literature_agent = LiteratureRetrievalAgent()
        self.formula_agent = FormulaExplanationAgent()
        self.knowledge_agent = KnowledgeExplanationAgent()
        self.voice_agent = StreamingVoiceQAAgent()
        self.safety_agent = SafetyReviewAgent()

    def run(self, case_text: str) -> dict:
        print("[TCMTeachingOrchestratorAgent] start")
        agent_steps: list[dict] = []

        symptom_result = self.symptom_agent.run(case_text)
        agent_steps.append(
            self._step(
                "症状分析 Agent",
                f"识别症状：{self._join(symptom_result.get('symptoms', []))}；"
                f"舌象：{self._join(symptom_result.get('tongue', []))}；"
                f"脉象：{self._join(symptom_result.get('pulse', []))}",
                symptom_result,
            )
        )

        followup_result = self.followup_agent.run(symptom_result)
        agent_steps.append(
            self._step(
                "追问建议 Agent",
                f"生成 {len(followup_result.get('follow_up_questions', []))} 条追问建议",
                followup_result,
            )
        )

        graph_result = self.graph_agent.run(symptom_result)
        agent_steps.append(
            self._step(
                "图谱推理 Agent",
                f"匹配证候：{self._join(graph_result.get('syndromes', []))}；"
                f"方剂：{self._join(graph_result.get('formulas', []))}",
                {
                    "syndromes": graph_result.get("syndromes", []),
                    "formulas": graph_result.get("formulas", []),
                    "reasoning_paths": graph_result.get("reasoning_paths", []),
                },
            )
        )

        sql_result = self.sql_agent.run(graph_result)
        agent_steps.append(
            self._step(
                "图谱数据 SQL Agent",
                "查询方剂、药材和证候相关结构化数据",
                sql_result,
            )
        )

        rag_result = self.literature_agent.run(case_text, graph_result)
        agent_steps.append(
            self._step(
                "文献检索 Agent",
                f"检索到 {len(rag_result.get('evidence', []))} 条相关资料依据",
                rag_result,
            )
        )

        formula_result = self.formula_agent.run(graph_result.get("formulas", []))
        agent_steps.append(
            self._step(
                "方剂解释 Agent",
                f"生成 {self._join(graph_result.get('formulas', []))} 的组成、功效和主治说明",
                formula_result,
            )
        )

        explanation_result = self.knowledge_agent.run(
            case_text=case_text,
            symptom_result=symptom_result,
            graph_result=graph_result,
            sql_result=sql_result,
            rag_result=rag_result,
            formula_result=formula_result,
        )
        agent_steps.append(
            self._step(
                "知识解释 Agent",
                "生成面向学习者的教学辅助分析",
                {
                    "learning_summary": explanation_result.get("learning_summary", ""),
                    "teaching_sections": explanation_result.get("teaching_sections", []),
                },
            )
        )

        voice_result = self.voice_agent.run(symptom_result, graph_result, explanation_result)
        agent_steps.append(
            self._step(
                "流式语音问答 Agent",
                "生成 mock 流式语音问答结果",
                voice_result,
            )
        )

        safety_result = self.safety_agent.run(explanation_result["answer"])
        agent_steps.append(
            self._step(
                "安全审查 Agent",
                "已添加教学辅助安全声明，并过滤真实诊断/治疗建议口径",
                {"safety_notice": safety_result["safety_notice"]},
            )
        )

        print("[TCMTeachingOrchestratorAgent] completed")
        return {
            "answer": safety_result["answer"],
            "symptoms": symptom_result.get("symptoms", []),
            "tongue": symptom_result.get("tongue", []),
            "pulse": symptom_result.get("pulse", []),
            "syndromes": graph_result.get("syndromes", []),
            "formulas": graph_result.get("formulas", []),
            "herbs": graph_result.get("herbs", []),
            "graph": graph_result.get("graph", {"nodes": [], "edges": []}),
            "sql_result": sql_result.get("sql_result", {}),
            "evidence": rag_result.get("evidence", []),
            "formula_explanations": formula_result.get("formula_explanations", []),
            "follow_up_questions": followup_result.get("follow_up_questions", []),
            "learning_summary": explanation_result.get("learning_summary", ""),
            "voice_qa": voice_result.get("voice_qa", {}),
            "agent_steps": agent_steps,
            "needs_clarification": graph_result.get("needs_clarification", False),
            "safety_notice": safety_result["safety_notice"],
        }

    def _step(self, name: str, summary: str, output: dict) -> dict:
        return {
            "name": name,
            "status": "completed",
            "summary": summary,
            "output": output,
        }

    def _join(self, values: list) -> str:
        return "、".join(str(value) for value in values) if values else "暂无明确数据"
