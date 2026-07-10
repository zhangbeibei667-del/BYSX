class KnowledgeExplanationAgent:
    """Build a structured teaching explanation from graph, SQL and RAG evidence.

    TODO: Later this agent can call a real LLM API. Keep the input contract stable:
    case_text + symptom_result + graph_result + sql_result + rag_result + formula_result.
    """

    def run(
        self,
        case_text: str,
        symptom_result: dict,
        graph_result: dict,
        sql_result: dict,
        rag_result: dict,
        formula_result: dict,
    ) -> dict:
        print("[KnowledgeExplanationAgent] start")

        symptoms = symptom_result.get("symptoms", [])
        tongue = symptom_result.get("tongue", [])
        pulse = symptom_result.get("pulse", [])
        syndromes = graph_result.get("syndromes", [])
        formulas = graph_result.get("formulas", [])
        herbs = graph_result.get("herbs", [])
        reasoning_paths = graph_result.get("reasoning_paths", [])
        evidence = rag_result.get("evidence", [])
        formula_explanations = formula_result.get("formula_explanations", [])
        needs_clarification = graph_result.get("needs_clarification", False)

        sections = [
            f"病例输入：{case_text}",
            f"症状信息提取：识别到 {self._join(symptoms)}。",
        ]
        if tongue:
            sections.append(f"舌象信息：{self._join(tongue)}。")
        if pulse:
            sections.append(f"脉象信息：{self._join(pulse)}。")

        if needs_clarification:
            sections.extend(
                [
                    "辨证信息评估：当前描述较宽泛，尚不足以建立可靠的证候、方剂和药材关联。",
                    f"图谱推理状态：{self._join(reasoning_paths)}。",
                    "下一步建议：先补充不适部位、具体表现、持续时间、饮食与大便情况，以及舌象和脉象。",
                ]
            )
        else:
            sections.extend(
                [
                    f"可能相关证候：可从 {self._join(syndromes)} 角度进行教学分析。",
                    f"图谱推理路径：{self._join(reasoning_paths)}。",
                    (
                        "图谱数据查询：本次在演示知识图谱中匹配到 "
                        f"{len(syndromes)} 个证候和 {len(formulas)} 个方剂。"
                    ),
                    f"方剂与药材解释：相关方剂包括 {self._join(formulas)}，涉及药材 {self._join(herbs)}。",
                    f"文献资料依据：检索到 {len(evidence)} 条资料片段，包括 {self._join([item['title'] for item in evidence])}。",
                ]
            )

        if needs_clarification:
            learning_summary = (
                "本案例当前适合学习中医问诊中的信息补全：宽泛主诉不能直接对应证候和方剂，"
                "应先明确症状性质并补充四诊资料。"
            )
        elif formula_explanations:
            first_formula = formula_explanations[0]
            learning_summary = (
                f"本案例可用于学习 {self._join(syndromes)} 与 {self._join(symptoms)} "
                f"之间的关联，以及 {first_formula['name']} 的组成、功效和适用知识点。"
            )
        else:
            learning_summary = "本案例可按症状、证候、方剂、药材的顺序建立知识关联。"

        sections.append(f"教学学习总结：{learning_summary}")
        result = {
            "answer": "".join(sections),
            "learning_summary": learning_summary,
            "teaching_sections": sections,
            "needs_clarification": needs_clarification,
        }

        print("[KnowledgeExplanationAgent] completed")
        return result

    def _join(self, values: list) -> str:
        return "、".join(str(value) for value in values) if values else "暂无明确数据"
