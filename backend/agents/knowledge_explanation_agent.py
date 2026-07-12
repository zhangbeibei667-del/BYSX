from backend.services.llm_client import get_llm_client


class KnowledgeExplanationAgent:
    """Generate an evidence-bounded explanation with traceable citations."""

    def run(self, case_text: str, symptom_result: dict, graph_result: dict,
            sql_result: dict, rag_result: dict, formula_result: dict) -> dict:
        symptoms = symptom_result.get("symptoms", [])
        tongue = symptom_result.get("tongue", [])
        pulse = symptom_result.get("pulse", [])
        syndromes = graph_result.get("syndromes", [])
        formulas = graph_result.get("formulas", [])
        paths = graph_result.get("reasoning_paths", [])
        evidence = rag_result.get("evidence", [])
        citations = [self._citation(item, index) for index, item in enumerate(evidence, 1)]
        reliable_relations = [edge for edge in graph_result.get("graph", {}).get("edges", [])
                              if edge.get("evidence") and "桥接" not in edge.get("evidence", "")]
        needs_clarification = graph_result.get("needs_clarification", False)

        sections = [f"病例信息：{case_text}", f"已识别症状：{self._join(symptoms)}。"]
        if tongue:
            sections.append(f"舌象：{self._join(tongue)}。")
        if pulse:
            sections.append(f"脉象：{self._join(pulse)}。")

        if needs_clarification or (not reliable_relations and not evidence):
            sections.append("当前证据不足：系统可能识别到相关实体，但没有检索到足以支持证候或方剂结论的可靠关系，因此不作确定性推断。")
            sections.append("建议继续补充症状性质、持续时间、诱因、饮食、二便、寒热及舌脉信息。")
            confidence = "insufficient"
        else:
            sections.append(f"图谱关联：可能相关证候为 {self._join(syndromes)}；相关方剂知识为 {self._join(formulas)}。")
            if paths:
                sections.append(f"推理路径：{self._join(paths)}。")
            confidence = "high" if reliable_relations and len(evidence) >= 2 else "medium"

        if citations:
            sections.append("资料依据：" + "；".join(citations) + "。")
        else:
            sections.append("资料依据：本次未召回可定位的教材、药典或科普资料片段。")
        learning_summary = "结论仅限中医药知识学习与关系分析，应结合完整四诊资料理解。"
        sections.append(learning_summary)
        generated = self._generate(case_text, symptoms, tongue, pulse, syndromes, formulas,
                                   paths, evidence, citations, confidence)
        answer = generated["content"] if generated else "\n\n".join(sections)
        return {
            "answer": answer, "learning_summary": learning_summary,
            "teaching_sections": sections, "needs_clarification": needs_clarification,
            "citations": citations, "evidence_confidence": confidence,
            "generation": ({"mode": "llm-grounded", "provider": generated["provider"],
                            "model": generated["model"], "usage": generated["usage"]}
                           if generated else {"mode": "local-evidence-template"}),
        }

    @staticmethod
    def _generate(case_text, symptoms, tongue, pulse, syndromes, formulas, paths,
                  evidence, citations, confidence) -> dict | None:
        client = get_llm_client()
        if not client.available:
            return None
        sources = "\n\n".join(
            f"[{index}] {item.get('citation') or item.get('title')}\n{str(item.get('content', ''))[:800]}"
            for index, item in enumerate(evidence[:5], 1))
        prompt = (
            f"病例描述：{case_text}\n已识别症状：{symptoms}\n舌象：{tongue}\n脉象：{pulse}\n"
            f"候选证候：{syndromes}\n关联方剂知识：{formulas}\n图谱路径：{paths}\n"
            f"证据等级：{confidence}\n资料：\n{sources}"
        )
        return client.complete([
            {"role": "system", "content": (
                "你是中医药病例学习与辨证思路讲解助手。用自然、循序渐进的中文解释，不要像数据库报告。"
                "先概括已知信息，再说明辨证分歧与理由；资料不足时主动提出最关键的追问。"
                "只能依据给定图谱和资料，每个关键知识结论标注[编号]，不得下诊断、开处方或给剂量。"
                "结尾明确仅用于知识学习和辨证辅助。")},
            {"role": "user", "content": prompt}], temperature=0.25)

    @staticmethod
    def _citation(item: dict, index: int) -> str:
        label = item.get("citation") or f"《{item.get('title', '未命名资料')}》"
        return f"[{index}] {label}"

    @staticmethod
    def _join(values: list) -> str:
        return "、".join(str(value) for value in values) if values else "暂无明确数据"
