from __future__ import annotations

import json
import re

from backend.services.llm_client import get_llm_client


AVAILABLE_TOOLS = {"symptom_analysis", "followup", "graph_query", "sql_query", "literature_search",
                   "formula_explanation", "knowledge_explanation", "safety_review"}


class AgentPlanner:
    def plan(self, text: str, has_context: bool = False) -> dict:
        llm_plan = self._llm_plan(text, has_context)
        if llm_plan:
            return llm_plan
        if any(marker in text for marker in ("患者", "舌", "脉", "症状", "疼", "痛", "失眠", "咳", "便", "口渴")) or has_context:
            tools = ["symptom_analysis", "followup", "graph_query", "sql_query", "literature_search",
                     "formula_explanation", "knowledge_explanation", "safety_review"]
            intent = "case_analysis"
        elif any(marker in text for marker in ("方", "汤", "丸", "散", "组成", "药材")):
            tools = ["graph_query", "sql_query", "literature_search", "formula_explanation",
                     "knowledge_explanation", "safety_review"]
            intent = "formula_query"
        elif any(marker in text for marker in ("文献", "教材", "药典", "出处", "依据")):
            tools, intent = ["graph_query", "literature_search", "knowledge_explanation", "safety_review"], "literature_query"
        else:
            tools, intent = ["graph_query", "literature_search", "knowledge_explanation", "safety_review"], "knowledge_query"
        return {"intent": intent, "tools": tools, "planner": "local-dynamic", "reason": "按问题意图选择必要工具"}

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
            if "safety_review" not in tools:
                tools.append("safety_review")
            return {**plan, "tools": tools, "planner": "llm-dynamic", "model": response["model"]}
        except (json.JSONDecodeError, TypeError):
            return None
