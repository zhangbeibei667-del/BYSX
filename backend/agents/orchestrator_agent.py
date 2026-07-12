from backend.agents.followup_question_agent import FollowUpQuestionAgent
from backend.agents.formula_explanation_agent import FormulaExplanationAgent
from backend.agents.graph_reasoning_agent import GraphReasoningAgent
from backend.agents.knowledge_explanation_agent import KnowledgeExplanationAgent
from backend.agents.literature_retrieval_agent import LiteratureRetrievalAgent
from backend.agents.safety_review_agent import SafetyReviewAgent
from backend.agents.sql_agent import GraphSQLAgent
from backend.agents.streaming_voice_agent import StreamingVoiceQAAgent
from backend.agents.symptom_analysis_agent import SymptomAnalysisAgent
from backend.services.agent_planner import AgentPlanner


class TCMTeachingOrchestratorAgent:
    """Dynamically plan and run only the tools needed by the current turn."""

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
        self.planner = AgentPlanner()

    def run(self, case_text: str, has_context: bool = False) -> dict:
        plan = self.planner.plan(case_text, has_context)
        selected = set(plan["tools"])
        steps = [self._step("动态工具规划", f"识别意图：{plan['intent']}；选择 {len(selected)} 个工具", plan)]

        symptom = self.symptom_agent.run(case_text) if "symptom_analysis" in selected else {
            "symptoms": [], "tongue": [], "pulse": []}
        if "symptom_analysis" in selected:
            steps.append(self._step("症状分析 Agent", f"识别症状：{self._join(symptom['symptoms'])}", symptom))

        followup = self.followup_agent.run(symptom) if "followup" in selected else {"follow_up_questions": []}
        if "followup" in selected:
            steps.append(self._step("症状追问 Agent", f"生成 {len(followup['follow_up_questions'])} 条上下文追问", followup))

        graph = self.graph_agent.run(symptom) if "graph_query" in selected else {
            "syndromes": [], "formulas": [], "herbs": [], "graph": {"nodes": [], "edges": []}}
        if "graph_query" in selected:
            steps.append(self._step("图谱查询 Agent", f"证候：{self._join(graph.get('syndromes', []))}；方剂：{self._join(graph.get('formulas', []))}", graph))

        sql = self.sql_agent.run(graph, case_text) if "sql_query" in selected else {"sql_result": {}}
        if "sql_query" in selected:
            steps.append(self._step("图谱数据 Text-to-SQL Agent", "生成、校验并只读执行 SQL", sql))

        rag = self.literature_agent.run(case_text, graph) if "literature_search" in selected else {"evidence": []}
        if "literature_search" in selected:
            steps.append(self._step("向量文献检索 Agent", f"召回 {len(rag.get('evidence', []))} 条可追溯证据", rag))

        formula = self.formula_agent.run(graph.get("formulas", [])) if "formula_explanation" in selected else {"formula_explanations": []}
        if "formula_explanation" in selected:
            steps.append(self._step("方剂说明 Agent", f"解释：{self._join(graph.get('formulas', []))}", formula))

        explanation = self.knowledge_agent.run(case_text, symptom, graph, sql, rag, formula)
        steps.append(self._step("知识解释 Agent", "融合图谱、SQL 与文献证据生成解释", explanation))

        safety = self.safety_agent.run(explanation["answer"])
        steps.append(self._step("安全审查 Agent", "完成医疗安全边界审查", {"safety_notice": safety["safety_notice"]}))
        voice = self.voice_agent.run(symptom, graph, {**explanation, "answer": safety["answer"]})

        needs_clarification = bool(graph.get("needs_clarification")) or (
            plan["intent"] == "case_analysis" and (len(symptom.get("symptoms", [])) < 2 or not symptom.get("tongue") or not symptom.get("pulse"))
        )
        return {
            "answer": safety["answer"], "symptoms": symptom.get("symptoms", []),
            "tongue": symptom.get("tongue", []), "pulse": symptom.get("pulse", []),
            "syndromes": graph.get("syndromes", []), "formulas": graph.get("formulas", []),
            "herbs": graph.get("herbs", []), "graph": graph.get("graph", {"nodes": [], "edges": []}),
            "sql_result": sql.get("sql_result", {}), "evidence": rag.get("evidence", []),
            "formula_explanations": formula.get("formula_explanations", []),
            "follow_up_questions": followup.get("follow_up_questions", []),
            "learning_summary": explanation.get("learning_summary", ""), "voice_qa": voice.get("voice_qa", {}),
            "citations": explanation.get("citations", []),
            "evidence_confidence": explanation.get("evidence_confidence", "insufficient"),
            "generation": explanation.get("generation", {"mode": "local-evidence-template"}),
            "agent_plan": plan, "agent_steps": steps, "needs_clarification": needs_clarification,
            "safety_notice": safety["safety_notice"],
        }

    @staticmethod
    def _step(name: str, summary: str, output: dict) -> dict:
        return {"name": name, "status": "completed", "summary": summary, "output": output}

    @staticmethod
    def _join(values: list) -> str:
        return "、".join(str(value) for value in values) if values else "暂无明确数据"
