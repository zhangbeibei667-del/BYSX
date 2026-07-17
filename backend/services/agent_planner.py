from __future__ import annotations

import json
import re

from backend.services.llm_client import get_llm_client


AVAILABLE_TOOLS = {"symptom_analysis", "followup", "graph_query", "sql_query", "literature_search",
                   "formula_explanation", "knowledge_explanation", "streaming_voice", "safety_review"}

CASE_TOOLS = ["symptom_analysis", "followup", "graph_query", "sql_query", "literature_search",
              "formula_explanation", "knowledge_explanation", "streaming_voice", "safety_review"]


class AgentPlanner:
    def plan(self, text: str, has_context: bool = False) -> dict:
        llm_plan = self._llm_plan(text, has_context)
        if llm_plan:
            if self._looks_like_case(text) or has_context:
                llm_plan["intent"] = "case_analysis"
                llm_plan["tools"] = list(dict.fromkeys([*llm_plan.get("tools", []), *CASE_TOOLS]))
            return llm_plan
        if self._looks_like_case(text) or has_context:
            tools = CASE_TOOLS.copy()
            intent = "case_analysis"
        elif any(marker in text for marker in ("方", "汤", "丸", "散", "组成", "药材")):
            tools = ["graph_query", "sql_query", "literature_search", "formula_explanation",
                     "knowledge_explanation", "streaming_voice", "safety_review"]
            intent = "formula_query"
        elif any(marker in text for marker in ("文献", "教材", "药典", "出处", "依据")):
            tools, intent = ["graph_query", "literature_search", "knowledge_explanation", "streaming_voice", "safety_review"], "literature_query"
        else:
            tools, intent = ["graph_query", "literature_search", "knowledge_explanation", "streaming_voice", "safety_review"], "knowledge_query"
        return {"intent": intent, "tools": tools, "planner": "local-dynamic", "reason": "按问题意图选择必要工具"}

    @staticmethod
    def _looks_like_case(text: str) -> bool:
        return any(marker in text for marker in (
            "患者", "舌", "脉", "症状", "主诉", "辨证", "疼", "痛", "失眠", "咳", "便", "口渴"
        ))

    def _llm_plan(self, text: str, has_context: bool) -> dict | None:
        client = get_llm_client()
        response = client.complete([{"role": "system", "content":
            "你是中医药智能体的工具规划器。只返回JSON，不回答医学问题。必须保留safety_review。"},
            {"role": "user", "content": f"可用工具：{sorted(AVAILABLE_TOOLS)}\n已有上下文：{has_context}\n问题：{text}\n"
             "返回格式：{\"intent\":\"...\",\"tools\":[...],\"reason\":\"...\"}"}],
            temperature=0, response_format={"type": "json_object"})
        if not response:
            return None
        try:
            content = re.sub(r"^```json|```$", "", response["content"].strip()).strip()
            plan = json.loads(content)
            tools = [tool for tool in plan.get("tools", []) if tool in AVAILABLE_TOOLS]
            intent = str(plan.get("intent") or "").strip()
            # Providers occasionally return a Chinese label instead of the canonical
            # machine intent. Tool selection is the stable contract.
            if "symptom_analysis" in tools or any(word in intent for word in ("辨证", "病例", "症状")):
                intent = "case_analysis"
                for required in ("symptom_analysis", "followup", "graph_query", "sql_query",
                                 "literature_search", "formula_explanation", "knowledge_explanation",
                                 "streaming_voice"):
                    if required not in tools:
                        tools.append(required)
            elif "formula_explanation" in tools:
                intent = "formula_query"
            elif "literature_search" in tools:
                intent = "literature_query"
            else:
                intent = "knowledge_query"
            if "safety_review" not in tools:
                tools.append("safety_review")
            return {**plan, "intent": intent, "tools": tools, "planner": "llm-dynamic", "model": response["model"]}
        except (json.JSONDecodeError, TypeError):
            return None
