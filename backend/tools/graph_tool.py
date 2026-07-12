from backend.mock_data.tcm_mock_data import MOCK_GRAPH_CASES
from backend.services.local_graphrag_service import get_local_graphrag_service


class GraphQueryTool:
    """Graph query tool.

    It now prefers the full entities_relations graph through
    LocalGraphRAGService.  The original mock cases remain as fallback for
    incomplete or missing local data.
    """

    def query_by_symptoms(self, symptoms: list[str]) -> dict:
        try:
            result = get_local_graphrag_service().query_by_symptoms(symptoms)
            result = self._apply_supplemental_rules(symptoms, result)
            if result.get("syndromes") or result.get("formulas"):
                return result
        except Exception:
            pass

        best_case = self._select_best_case(symptoms)
        if best_case is None:
            return self._apply_supplemental_rules(symptoms, self._build_insufficient_result(symptoms))
        return self._apply_supplemental_rules(symptoms, self._build_graph_result(symptoms, best_case))

    def _apply_supplemental_rules(self, symptoms: list[str], result: dict) -> dict:
        symptom_set = set(symptoms)

        dental_heat = bool({"牙龈肿痛", "口臭"} & symptom_set) and bool(
            {"口渴", "口渴喜冷饮", "便秘", "舌红", "舌苔黄", "脉数"} & symptom_set
            or {"口渴", "便秘"} <= symptom_set
        )

        if not dental_heat:
            return result

        existing_syndromes = set(result.get("syndromes", []))
        if {"胃火炽盛", "阳明胃热"} & existing_syndromes:
            result["reason"] = "基于 entities_relations 图谱及 clinical_supplement overlay 的症状—证候—方剂路径匹配。"
            result["confidence"] = "local-kg-match"
            return result

        supplemental_syndromes = ["胃火炽盛（补充规则）", "阳明胃热（补充规则）"]
        supplemental_formulas = ["清胃散（待入库）", "黄连解毒汤", "白虎汤"]
        supplemental_herbs = ["黄连", "生地黄", "牡丹皮", "当归", "升麻", "石膏", "知母", "甘草"]

        result["syndromes"] = self._prepend_unique(supplemental_syndromes, result.get("syndromes", []))
        result["formulas"] = self._prepend_unique(supplemental_formulas, result.get("formulas", []))
        result["herbs"] = self._prepend_unique(supplemental_herbs, result.get("herbs", []))
        result["needs_clarification"] = False
        result["confidence"] = "kg+supplemental-rule"
        result["reason"] = (
            "完整图谱缺少牙龈肿痛/口臭对应的胃火证候节点，已依据症状组合加入补充教学规则；"
            "补充规则结果需后续入库为正式图谱关系。"
        )

        graph = result.setdefault("graph", {"nodes": [], "edges": []})
        nodes = graph.setdefault("nodes", [])
        edges = graph.setdefault("edges", [])
        existing_node_ids = {node.get("id") for node in nodes}

        for symptom in ["牙龈肿痛", "口臭", "口渴", "便秘", "口渴喜冷饮"]:
            if symptom in symptom_set:
                node_id = f"supplemental:symptom:{symptom}"
                if node_id not in existing_node_ids:
                    nodes.append({"id": node_id, "label": symptom, "type": "症状"})
                    existing_node_ids.add(node_id)

        for syndrome in supplemental_syndromes:
            node_id = f"supplemental:syndrome:{syndrome}"
            if node_id not in existing_node_ids:
                nodes.append({"id": node_id, "label": syndrome, "type": "证候"})
                existing_node_ids.add(node_id)

        for formula in supplemental_formulas:
            node_id = f"supplemental:formula:{formula}"
            if node_id not in existing_node_ids:
                nodes.append({"id": node_id, "label": formula, "type": "方剂"})
                existing_node_ids.add(node_id)

        for symptom in ["牙龈肿痛", "口臭", "口渴", "便秘", "口渴喜冷饮"]:
            if symptom in symptom_set:
                edges.append(
                    {
                        "source": f"supplemental:symptom:{symptom}",
                        "target": "supplemental:syndrome:胃火炽盛（补充规则）",
                        "label": "提示",
                        "evidence": "补充规则：牙龈肿痛、口臭、口渴便秘、舌红苔黄等偏胃火/胃热教学特征",
                    }
                )

        for formula in supplemental_formulas:
            edges.append(
                {
                    "source": "supplemental:syndrome:胃火炽盛（补充规则）",
                    "target": f"supplemental:formula:{formula}",
                    "label": "参考",
                    "evidence": "补充规则：清胃泻火/清热解毒方向，需后续正式入库校验",
                }
            )

        result["reasoning_paths"] = self._prepend_unique(
            [
                "牙龈肿痛 + 口臭 + 口渴/便秘 -> 胃火炽盛（补充规则）",
                "胃火炽盛（补充规则） -> 清胃散（待入库）/黄连解毒汤/白虎汤",
            ],
            result.get("reasoning_paths", []),
        )
        return result

    def _select_best_case(self, symptoms: list[str]) -> dict | None:
        symptom_set = set(symptoms)
        scored_cases = []
        for case in MOCK_GRAPH_CASES:
            score = len(symptom_set.intersection(case["match_symptoms"]))
            scored_cases.append((score, case))
        scored_cases.sort(key=lambda item: item[0], reverse=True)
        if not scored_cases or scored_cases[0][0] < 2:
            return None
        return scored_cases[0][1]

    def _build_insufficient_result(self, symptoms: list[str]) -> dict:
        nodes = [
            {"id": f"S{index:03d}", "label": symptom, "type": "症状"}
            for index, symptom in enumerate(symptoms, start=1)
        ]
        return {
            "syndromes": [],
            "formulas": [],
            "herbs": [],
            "graph": {"nodes": nodes, "edges": []},
            "reasoning_paths": ["现有症状信息不足，暂不建立证候与方剂推理路径"],
            "reason": "当前信息未达到教学规则的最低匹配条件，建议补充具体症状、诱因、舌象和脉象。",
            "confidence": 0,
            "needs_clarification": True,
        }

    def _build_graph_result(self, symptoms: list[str], case: dict) -> dict:
        syndrome = case["syndrome"]
        formula = case["formula"]
        herbs = case["herbs"]

        nodes = []
        edges = []
        for index, symptom in enumerate(symptoms or case["match_symptoms"][:2], start=1):
            symptom_id = f"S{index:03d}"
            nodes.append({"id": symptom_id, "label": symptom, "type": "症状"})
            edges.append({"source": symptom_id, "target": "Z001", "label": "提示"})

        nodes.extend(
            [
                {"id": "Z001", "label": syndrome, "type": "证候"},
                {"id": "F001", "label": formula, "type": "方剂"},
            ]
        )
        edges.append({"source": "Z001", "target": "F001", "label": "对应"})

        for index, herb in enumerate(herbs[:5], start=1):
            herb_id = f"H{index:03d}"
            nodes.append({"id": herb_id, "label": herb, "type": "药材"})
            edges.append({"source": "F001", "target": herb_id, "label": "包含"})

        return {
            "syndromes": [syndrome],
            "formulas": [formula],
            "herbs": herbs,
            "graph": {"nodes": nodes, "edges": edges},
            "reasoning_paths": [
                f"症状集合 -> {syndrome}",
                f"{syndrome} -> {formula}",
                f"{formula} -> {'、'.join(herbs[:5])}",
            ],
            "reason": case["reason"],
            "confidence": "mock-rule-match",
            "needs_clarification": False,
        }

    @staticmethod
    def _prepend_unique(prefix: list[str], values: list[str]) -> list[str]:
        result = []
        for value in [*prefix, *values]:
            value = str(value).strip()
            if value and value not in result:
                result.append(value)
        return result
