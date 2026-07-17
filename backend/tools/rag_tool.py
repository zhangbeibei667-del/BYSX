from __future__ import annotations

import json
import re

from backend.services.local_graphrag_service import get_local_graphrag_service
from backend.services.vector_retrieval_service import VectorRetrievalService
from backend.services.llm_client import get_llm_client


class RAGRetrievalTool:
    """Hybrid Qdrant + graph retrieval with evidence-bounded answers."""

    RELATION_INTENTS = {"formula_composition", "symptom_to_formula", "effect_query", "contraindication_query"}
    PERSONAL_CLINICAL_MARKERS = (
        "我最近", "我总是", "我出现", "我有", "患者", "怎么调理", "如何调理", "怎么治疗", "怎么办",
    )

    def query(self, query: str, syndromes: list[str] | None = None,
              formulas: list[str] | None = None, top_k: int = 5,
              generate_answer: bool = True, answer_mode: str = "concise") -> dict:
        graph_service = get_local_graphrag_service()
        unknown = self._unknown_claim_subject(query, graph_service)
        if unknown:
            return self._insufficient(query, f"“{unknown}”不在当前知识图谱实体中，无法验证该治疗关系")
        try:
            result = graph_service.search(query=query, syndromes=syndromes or [], formulas=formulas or [], top_k=top_k)
            graph_evidence = result.get("evidence", [])
            personal_clinical = self.is_personal_clinical_request(query)
            vector_service = VectorRetrievalService()
            document_evidence = vector_service.search(
                query, top_k=max(50, top_k * 10) if personal_clinical else top_k
            )
            if personal_clinical:
                # Long case descriptions often dilute the syndrome name in lexical/vector search.
                # Retrieve once more for the graph's leading candidates, then rerank all documents
                # against the user's actual symptoms and independent tongue/pulse dimensions.
                augmented = list(document_evidence)
                for syndrome in list(dict.fromkeys(result.get("syndromes", [])))[:3]:
                    augmented.extend(vector_service.search(
                        f"不寐 {syndrome} 典型表现 舌象 脉象", top_k=12
                    ))
                by_id: dict[str, dict] = {}
                for item in augmented:
                    key = str(item.get("id") or item.get("identifier") or item.get("title") or "")
                    if key and key not in by_id:
                        by_id[key] = item
                document_evidence = list(by_id.values())
                document_evidence = self._filter_clinical_documents(query, result, document_evidence)
            if self._needs_clinical_clarification(query, graph_service, result.get("intent", "")):
                gated = self._clarification_required(
                    query, result, self._merge_evidence(document_evidence, graph_evidence, top_k), top_k
                )
                gated["retrieval"] = {
                    "mode": "qdrant+graph-evidence-gated",
                    "document_hits": len(document_evidence),
                    "graph_hits": len(graph_evidence),
                    "citations_available": bool(gated.get("evidence")),
                }
                return gated
            has_relation = bool(result.get("graph", {}).get("edges"))
            if result.get("intent") in self.RELATION_INTENTS and not has_relation:
                insufficient = self._insufficient(query, "检索到的实体之间没有带来源依据的目标关系")
                insufficient["evidence"] = document_evidence[:top_k]
                insufficient["citations"] = [item["citation"] for item in document_evidence[:top_k]]
                return insufficient
            needs_expanded_evidence = getattr(graph_service, "_needs_expanded_evidence", lambda _: False)
            evidence_top_k = max(top_k, 10) if needs_expanded_evidence(query) else top_k
            if needs_expanded_evidence(query):
                result["evidence"] = self._merge_expanded_evidence(document_evidence, graph_evidence, evidence_top_k)
            else:
                result["evidence"] = self._merge_evidence(document_evidence, graph_evidence, evidence_top_k)
            if personal_clinical:
                result["clinical_dimensions"] = self.parse_clinical_dimensions(query)
                # Differential rows must come from the richer RAG candidate set, not only the
                # top merged evidence where high-scoring graph edges can crowd documents out.
                result["differential_evidence"] = self.build_differential_evidence(
                    query, {
                        # Keep body reasoning aligned with documents that are also exposed
                        # in the visible evidence drawer and can therefore be cited.
                        "evidence": document_evidence[:max(2, (top_k + 1) // 2)],
                        "syndromes": result.get("syndromes", []),
                    }
                )
            document_mode = (document_evidence[0].get("retrieval_mode")
                             if document_evidence else "no-document-hit")
            result["retrieval"] = {"mode": f"{document_mode}+graph", "document_hits": len(document_evidence),
                                   "graph_hits": len(graph_evidence), "citations_available": bool(result["evidence"])}
            result["citations"] = [item.get("citation") or f"《{item.get('title', '未命名资料')}》"
                                   for item in result["evidence"]]
            if not result["citations"] and not has_relation:
                return self._insufficient(query, "没有召回可验证关系或可定位资料")
            confidence, confidence_score = self._assess_evidence_confidence(
                personal_clinical, document_evidence, graph_evidence
            )
            result["evidence_confidence"] = confidence
            result["evidence_confidence_score"] = confidence_score
            result["answer_mode"] = self._normalize_answer_mode(answer_mode)
            generated = self._generate_answer(query, result, answer_mode) if generate_answer else None
            if generated:
                original_answer = generated["content"]
                result["answer"] = (
                    self.sanitize_clinical_answer(original_answer) if personal_clinical else original_answer
                )
                generation_mode = (
                    "llm-grounded-clinical-sanitized"
                    if personal_clinical and result["answer"] != original_answer else "llm-grounded"
                )
                result["generation"] = {"mode": generation_mode, "provider": generated["provider"],
                                        "model": generated["model"], "usage": generated["usage"], "calls": 1}
            elif generate_answer:
                result["generation"] = {"mode": "local-evidence-template"}
            else:
                result["generation"] = {"mode": "retrieval-only"}
            return result
        except Exception as exc:
            return {**self._insufficient(query, "检索服务暂时不可用"), "error": str(exc), "mode": "retrieval-error"}

    def retrieve(self, case_text: str, syndromes: list[str], formulas: list[str], top_k: int = 5) -> list[dict]:
        return self.query(" ".join([case_text, *syndromes, *formulas]).strip(), syndromes, formulas, top_k).get("evidence", [])[:top_k]

    @staticmethod
    def _unknown_claim_subject(query: str, graph_service) -> str:
        match = re.search(r"([\u4e00-\u9fff]{2,16})(?:能|可以|是否)(?:治疗|主治|用于)", query)
        if not match:
            return ""
        subject = match.group(1).lstrip("请问关于想知道")
        known = any(subject == entity.name or subject == entity.alias for entity in graph_service.entities)
        return "" if known else subject

    @staticmethod
    def _needs_clinical_clarification(query: str, graph_service, intent: str = "") -> bool:
        """Require differentiation before individualized treatment or self-care suggestions."""
        symptom_names = {
            entity.name for entity in graph_service.entities
            if entity.type == "症状" and entity.name and entity.name in query
        }
        syndrome_or_formula_named = any(
            entity.name and entity.name in query
            for entity in graph_service.entities
            if entity.type in {"证候", "方剂"}
        )
        advice_markers = (
            "怎么调理", "如何调理", "怎样调理", "怎么改善", "如何改善", "怎么办", "怎么治疗",
            "如何治疗", "吃什么", "喝什么", "用什么药", "什么方剂", "推荐方剂", "穴位", "按摩",
        )
        asks_for_action = intent == "symptom_to_formula" or any(marker in query for marker in advice_markers)
        discriminators = (
            "舌质", "舌苔", "脉象", "脉沉", "脉浮", "脉细", "脉数", "脉迟", "兼有", "伴有",
            "口苦", "痰黄", "痰白", "心悸", "乏力", "盗汗", "腹胀", "大便", "小便",
        )
        discriminator_count = sum(1 for marker in discriminators if marker in query)
        return bool(symptom_names) and asks_for_action and not syndrome_or_formula_named \
            and discriminator_count < 2

    @staticmethod
    def _assess_evidence_confidence(
        personal_clinical: bool, documents: list[dict], graph_items: list[dict]
    ) -> tuple[str, float]:
        """Score document relevance separately from graph-edge verification.

        A verified graph edge is not a 100% patient-level match.  Personal
        clinical questions are capped at medium because online text cannot
        establish a syndrome diagnosis.
        """
        document_scores = [
            max(0.0, min(1.0, float(item.get("score") or 0.0))) for item in documents
        ]
        document_average = (
            sum(document_scores[:5]) / min(5, len(document_scores)) if document_scores else 0.0
        )
        graph_support = 0.1 if graph_items else 0.0
        combined = round(min(1.0, document_average * 0.85 + graph_support), 4)
        if personal_clinical:
            if not documents:
                return "insufficient", combined
            return "medium", combined
        if documents and graph_items and document_average >= 0.55:
            return "high", combined
        if documents or graph_items:
            return "medium", combined
        return "insufficient", combined

    @staticmethod
    def _merge_evidence(documents: list[dict], graph_items: list[dict], top_k: int) -> list[dict]:
        """Reserve visible evidence slots for both RAG documents and graph relations."""
        if not documents:
            return graph_items[:top_k]
        if not graph_items:
            return documents[:top_k]
        document_limit = max(1, (top_k + 1) // 2)
        graph_limit = max(1, top_k - document_limit)
        merged = documents[:document_limit] + graph_items[:graph_limit]
        if len(merged) < top_k:
            merged.extend(documents[document_limit:document_limit + top_k - len(merged)])
        if len(merged) < top_k:
            merged.extend(graph_items[graph_limit:graph_limit + top_k - len(merged)])
        return merged[:top_k]

    @staticmethod
    def _merge_expanded_evidence(documents: list[dict], graph_items: list[dict], top_k: int) -> list[dict]:
        """For explanation-style answers, keep graph entities and paths visible first."""
        if not graph_items:
            return documents[:top_k]
        graph_limit = min(len(graph_items), max(6, top_k - 3))
        merged = graph_items[:graph_limit]
        merged.extend(documents[:max(0, top_k - len(merged))])
        if len(merged) < top_k:
            merged.extend(graph_items[graph_limit:graph_limit + top_k - len(merged)])
        return merged[:top_k]

    @staticmethod
    def _filter_clinical_documents(query: str, result: dict, items: list[dict]) -> list[dict]:
        """Prefer syndrome/insomnia sources and discard incidental symptom matches in unrelated documents."""
        syndrome_names = [str(item) for item in result.get("syndromes", []) if item]
        syndrome_names.extend(
            str(node.get("label") or "")
            for node in result.get("graph", {}).get("nodes", [])
            if node.get("type") == "证候" and node.get("label")
        )
        syndrome_names = list(dict.fromkeys(syndrome_names))
        topic_terms = [term for term in ("不寐", "失眠", "多梦") if term in query]
        symptom_terms = [
            term for term in (
                "入睡困难", "易醒", "早醒", "多梦", "心悸", "乏力", "口苦", "胸闷", "痰多",
                "盗汗", "腰膝酸软", "口干", "咽干", "五心烦热", "舌红", "舌淡", "苔黄",
                "苔白", "苔腻", "少苔", "脉数", "脉细", "脉滑", "脉弦",
            ) if term in query
        ]
        discriminator_terms = {
            "舌红", "舌淡", "苔黄", "苔白", "苔腻", "少苔", "脉数", "脉细", "脉滑", "脉弦",
            "盗汗", "口干", "咽干", "五心烦热", "口苦", "胸闷", "痰多",
        }
        ranked: list[tuple[int, float, dict]] = []
        for item in items:
            item = RAGRetrievalTool._focus_clinical_document(query, item)
            if item is None:
                continue
            title = str(item.get("title") or "")
            content = str(item.get("content") or "")
            category = str(item.get("category") or "")
            title_syndromes = [name for name in syndrome_names if name and name in title]
            syndrome_rank_bonus = max(
                (max(0, 6 - syndrome_names.index(name)) for name in title_syndromes),
                default=0,
            )
            topic_matches = sum(1 for term in topic_terms if term in title or term in content)
            symptom_matches = sum(1 for term in symptom_terms if term in content)
            discriminator_matches = sum(
                1 for term in symptom_terms if term in discriminator_terms and term in content
            )
            # Generic TCM-QG snippets often mention insomnia only incidentally while
            # discussing another condition.  They remain useful for general QA, but
            # must not drive an individualized syndrome-differentiation flow.
            trusted_clinical_category = category in {
                "证候知识", "教材", "药典", "方剂说明", "科普",
            }
            if not trusted_clinical_category:
                continue
            if not topic_matches:
                continue
            score = (
                syndrome_rank_bonus + topic_matches * 5
                + min(symptom_matches, 5) * 2 + discriminator_matches * 3
            )
            if category == "证候知识" and (title_syndromes or topic_matches):
                score += 2
            # Clinical teaching evidence must match the sleep topic plus enough
            # case-specific symptoms or tongue/pulse discriminators.  Fewer,
            # stronger sources are preferable to padding the answer with a weak third hit.
            minimum_score = 15 if any(term in query for term in discriminator_terms) else 8
            if score >= minimum_score:
                ranked.append((score, float(item.get("score") or 0), item))
        ranked.sort(key=lambda row: (-row[0], -row[1], str(row[2].get("title") or "")))
        return [item for _, _, item in ranked[:5]]

    @staticmethod
    def _focus_clinical_document(query: str, item: dict) -> dict | None:
        """Keep the disease-specific subsection relevant to the current teaching case.

        TCM-SD records can contain several diseases under one syndrome.  Matching
        symptoms across those sections would create a false composite case.
        """
        if not any(term in query for term in ("不寐", "失眠", "多梦", "入睡困难", "易醒", "早醒")):
            return dict(item)
        content = str(item.get("content") or "").replace("\\n", "\n")
        if not content:
            return None
        header_match = re.match(r"\s*(证候[^\n]*\n?)", content)
        syndrome_header = header_match.group(1).strip() if header_match else ""
        numbered_sections = re.split(r"(?m)(?=^\s*\d+[、.．])", content)
        if len(numbered_sections) > 1:
            sleep_sections = []
            for section in numbered_sections[1:]:
                first_line = section.strip().splitlines()[0] if section.strip() else ""
                if any(term in first_line for term in ("不寐", "失眠")):
                    sleep_sections.append(section.strip())
            if not sleep_sections:
                return None
            focused_content = "\n".join(filter(None, [syndrome_header, *sleep_sections]))
        else:
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            sleep_index = next(
                (index for index, line in enumerate(lines) if line in {"不寐", "失眠"}),
                None,
            )
            if sleep_index is None:
                if "定义与典型表现" not in str(item.get("title") or ""):
                    return None
                focused_content = "\n".join(lines)
            else:
                focused_content = "\n".join(lines[:1] + lines[sleep_index:])
        focused = dict(item)
        focused["content"] = focused_content
        focused["clinical_section"] = "不寐"
        return focused

    @staticmethod
    def parse_clinical_dimensions(text: str) -> dict[str, dict]:
        """Parse the latest tongue/coating/pulse observation for each independent dimension."""
        definitions = {
            "tongue_body": ("舌质", (("舌质红", "红"), ("舌红", "红"), ("舌质淡", "淡"), ("舌淡", "淡"),
                                            ("舌紫", "紫"), ("舌暗", "暗"), ("舌胖", "胖"), ("舌瘦", "瘦"), ("齿痕", "齿痕"))),
            "coat_color": ("苔色", (("苔黄", "黄"), ("黄苔", "黄"), ("苔白", "白"), ("白苔", "白"),
                                         ("苔灰", "灰"), ("灰苔", "灰"), ("苔黑", "黑"), ("黑苔", "黑"))),
            "coat_amount": ("苔量", (("少苔", "少"), ("苔少", "少"), ("无苔", "无"), ("剥苔", "剥脱"))),
            "coat_texture": ("苔质", (("薄苔", "薄"), ("苔薄", "薄"), ("厚苔", "厚"), ("苔厚", "厚"),
                                           ("腻苔", "腻"), ("苔腻", "腻"), ("苔黄腻", "腻"), ("苔润", "润"),
                                           ("苔燥", "燥"), ("燥苔", "燥"), ("腐苔", "腐"), ("苔腐", "腐"))),
            "pulse_rate": ("脉率", (("脉迟", "迟"), ("迟脉", "迟"), ("脉数", "数"), ("数脉", "数"),
                                          ("脉缓", "缓"), ("缓脉", "缓"), ("脉细数", "数"), ("脉弦数", "数"),
                                          ("脉滑数", "数"), ("脉象偏慢", "迟"), ("脉偏慢", "迟"),
                                          ("脉搏偏慢", "迟"), ("脉象偏快", "数"), ("脉偏快", "数"),
                                          ("脉搏偏快", "数"))),
            "pulse_shape": ("脉形", (("脉细", "细"), ("脉细数", "细"), ("脉弦", "弦"), ("脉弦数", "弦"),
                                           ("脉滑", "滑"), ("脉滑数", "滑"), ("脉沉", "沉"), ("脉浮", "浮"),
                                            ("脉涩", "涩"), ("脉弱", "弱"), ("脉洪", "洪"))),
        }
        segments = [segment.strip() for segment in re.split(r"[\r\n；;]+", text) if segment.strip()]

        def append(values: list[str], value: str) -> None:
            if value not in values:
                values.append(value)

        def contextual_values(key: str, segment: str) -> list[str]:
            values: list[str] = []
            if key == "tongue_body" and any(marker in segment for marker in ("舌质", "舌象", "舌")):
                if "淡红" in segment:
                    append(values, "淡红")
                else:
                    for marker, value in (("红", "红"), ("淡", "淡"), ("紫", "紫"), ("暗", "暗"),
                                          ("胖", "胖"), ("瘦", "瘦"), ("齿痕", "齿痕")):
                        if marker in segment:
                            append(values, value)
            if key.startswith("coat_") and "苔" in segment:
                if key == "coat_color":
                    for marker, value in (("薄白", "白"), ("白色", "白"), ("黄色", "黄"),
                                          ("灰色", "灰"), ("黑色", "黑")):
                        if marker in segment:
                            append(values, value)
                elif key == "coat_texture":
                    for marker, value in (("薄白", "薄"), ("薄", "薄"), ("厚", "厚"),
                                          ("润度适中", "润"), ("湿润", "润"), ("润", "润"),
                                          ("干燥", "燥"), ("燥", "燥"), ("不发腻", "不腻"), ("不腻", "不腻")):
                        if marker in segment:
                            append(values, value)
                    if "腻" in segment and not any(marker in segment for marker in ("不腻", "不发腻")):
                        append(values, "腻")
            if key.startswith("pulse_") and "脉" in segment:
                if key == "pulse_rate":
                    if any(marker in segment for marker in ("不迟不数", "脉率平", "快慢适中", "快慢正常")):
                        append(values, "平")
                    else:
                        if (
                            ("迟" in segment and "不迟" not in segment)
                            or re.search(r"(?:脉象|脉搏|脉).{0,8}(?:偏慢|较慢|缓慢)", segment)
                        ):
                            append(values, "迟")
                        if (
                            ("数" in segment and "不数" not in segment)
                            or re.search(r"(?:脉象|脉搏|脉).{0,8}(?:偏快|较快|较数|快速)", segment)
                        ):
                            append(values, "数")
                elif key == "pulse_shape":
                    if any(marker in segment for marker in ("脉象平和", "脉象平稳", "浮沉适中", "无明显异常")):
                        append(values, "平和")
                    shape_markers = (("略细", "细"), ("细", "细"), ("弦", "弦"), ("滑", "滑"),
                                     ("沉", "沉"), ("浮", "浮"), ("涩", "涩"), ("弱", "弱"),
                                     ("无力", "弱"), ("洪", "洪"))
                    negative_context = any(marker in segment for marker in ("无明显", "不见", "没有"))
                    for marker, value in shape_markers:
                        if marker in {"浮", "沉"} and "浮沉适中" in segment:
                            continue
                        if marker in segment and not (
                            negative_context
                            and marker != "无力"
                            and re.search(rf"(?:无明显|不见|没有).{{0,24}}{marker}", segment)
                        ):
                            append(values, value)
            return values

        def normal_in_segment(key: str, segment: str) -> bool:
            if re.search(r"舌质.{0,8}舌苔.{0,8}脉象.{0,8}(?:都)?正常", segment):
                return True
            pattern = {
                "tongue_body": r"(?:舌质|舌象).{0,12}(?:接近|基本|都)?正常",
                "coat_color": r"舌苔.{0,12}(?:接近|基本|都)?正常",
                "coat_amount": r"舌苔.{0,12}(?:接近|基本|都)?正常",
                "coat_texture": r"舌苔.{0,12}(?:接近|基本|都)?正常",
                "pulse_rate": r"脉象.{0,12}(?:接近|基本|都)?正常",
                "pulse_shape": r"脉象.{0,12}(?:接近|基本|都)?正常",
            }[key]
            return bool(re.search(pattern, segment))

        result: dict[str, dict] = {}
        for key, (label, markers) in definitions.items():
            values: list[str] = []
            normal = False
            # Newer replies override older observations for the same dimension.
            for segment in reversed(segments):
                segment_values: list[str] = []
                for marker, value in markers:
                    if marker in segment:
                        append(segment_values, value)
                for value in contextual_values(key, segment):
                    append(segment_values, value)
                segment_normal = normal_in_segment(key, segment)
                if segment_values or segment_normal:
                    values = segment_values or ["自述正常"]
                    normal = segment_normal and not segment_values
                    break
            result[key] = {
                "label": label,
                "values": values,
                "observed": bool(values),
                "confidence": "low" if normal else "self_reported" if values else "missing",
            }
        return result

    @classmethod
    def build_differential_evidence(cls, query: str, result: dict) -> list[dict]:
        """Build support/difference/missing fields using same-dimension comparisons only."""
        user_dimensions = cls.parse_clinical_dimensions(query)
        symptom_terms = (
            "失眠", "不寐", "多梦", "入睡困难", "易醒", "早醒", "乏力", "腰膝酸软", "心悸",
            "口苦", "胸闷", "痰多", "五心烦热", "潮热", "盗汗", "口干", "咽干", "头晕", "耳鸣", "易怒",
            "胆怯", "易惊", "善惊", "心烦",
            "食欲不振", "食少", "腹胀", "便溏", "面色萎黄", "面色少华",
        )
        graph_candidates = {
            str(value).removesuffix("证") for value in result.get("syndromes", []) if value
        }
        conflict_pairs = {
            "tongue_body": ({"红", "淡"}, {"红", "紫"}, {"淡", "紫"}),
            "coat_color": ({"黄", "白"}, {"黄", "灰"}, {"黄", "黑"}),
            "coat_amount": ({"少", "无"},),
            "coat_texture": ({"薄", "厚"}, {"润", "燥"}),
            "pulse_rate": ({"迟", "数"},),
        }
        rows_by_candidate: dict[str, dict] = {}
        for item in result.get("evidence", []):
            if not item.get("category"):
                continue
            content = str(item.get("content") or "")
            document_dimensions = cls.parse_clinical_dimensions(content)
            support = [term for term in symptom_terms if term in query and term in content][:5]
            differences: list[str] = []
            missing: list[str] = []
            dimension_support_score = 0.0
            for key, document_dimension in document_dimensions.items():
                document_values = set(document_dimension["values"])
                if not document_values:
                    continue
                user_dimension = user_dimensions[key]
                user_values = set(user_dimension["values"])
                overlap = user_values & document_values
                if overlap:
                    support.append(f"{document_dimension['label']}：{'/'.join(sorted(overlap))}")
                    neutral_values = {
                        "tongue_body": {"淡红"},
                        "coat_color": {"白"},
                        "coat_texture": {"薄", "润", "不腻"},
                        "pulse_rate": {"平"},
                        "pulse_shape": {"平和"},
                    }
                    for value in overlap:
                        if value in neutral_values.get(key, set()):
                            dimension_support_score += 0.5
                        elif key == "pulse_shape" and value == "细":
                            dimension_support_score += 1.5
                        else:
                            dimension_support_score += 3.0
                    continue
                if not user_values or user_values == {"自述正常"}:
                    missing.append(f"{document_dimension['label']}（资料为{'/'.join(sorted(document_values))}）")
                    continue
                for pair in conflict_pairs.get(key, ()):
                    if user_values & pair and document_values & pair and user_values != document_values:
                        differences.append(
                            f"{document_dimension['label']}：现有{'/'.join(sorted(user_values))}，资料为{'/'.join(sorted(document_values))}"
                        )
                        break
            missing_symptoms = [
                term for term in symptom_terms if term in content and term not in query
                and not (term == "不寐" and "失眠" in query)
                and not (term == "失眠" and "不寐" in query)
            ][:5]
            missing.extend(missing_symptoms)
            support = list(dict.fromkeys(support))
            differences = list(dict.fromkeys(differences))
            missing = list(dict.fromkeys(missing))
            candidate = str(item.get("title") or "候选证候").split("：", 1)[0]
            symptom_support = sum(1 for value in support if "：" not in value)
            candidate_key = candidate.removesuffix("证")
            graph_bonus = 2.0 if candidate_key in graph_candidates else 0.0
            required_clue_groups = {
                "心胆气虚": ({"胆怯", "易惊", "善惊"},),
                "心脾两虚": ({"乏力", "食欲不振", "食少", "腹胀", "便溏", "面色萎黄", "面色少华"},),
                "心肾不交": (
                    {"五心烦热", "潮热", "盗汗", "口干", "咽干", "舌红", "脉数", "心烦"},
                    {"腰膝酸软", "耳鸣"},
                ),
                "心气阴两虚": ({"五心烦热", "盗汗", "口干", "舌红", "脉数", "心悸"},),
            }
            clue_adjustment = 0.0
            for group in required_clue_groups.get(candidate_key, ()):
                clue_adjustment += 1.0 if any(term in query for term in group) else -2.5
            score = round(
                symptom_support * 2.0 + dimension_support_score + graph_bonus + clue_adjustment
                - len(differences) * 3.0 - len(missing) * 0.35,
                2,
            )
            row = {
                "candidate": candidate,
                "source_title": str(item.get("title") or "资料"),
                "support": support,
                "differences": differences,
                "missing": missing,
                "score": score,
                "evidence_strength": "较强" if score >= 7 else "中等" if score >= 4 else "较弱",
            }
            previous = rows_by_candidate.get(candidate)
            if previous is None or score > float(previous.get("score") or 0):
                rows_by_candidate[candidate] = row
        rows = sorted(
            rows_by_candidate.values(),
            key=lambda row: (-float(row.get("score") or 0), len(row.get("differences") or []), row["candidate"]),
        )
        return rows[:2]

    @staticmethod
    def _clarification_required(query: str, result: dict, graph_evidence: list[dict], top_k: int) -> dict:
        graph_service = get_local_graphrag_service()
        symptom_names = [
            entity.name for entity in graph_service.entities
            if entity.type == "症状" and entity.name and entity.name in query
        ]
        symptom_names = list(dict.fromkeys(symptom_names))
        symptom_text = "、".join(symptom_names) if symptom_names else "目前描述的症状"
        syndromes = result.get("syndromes", [])[:4]
        candidate_text = "、".join(syndromes) if syndromes else "多个不同证候"
        progress = RAGRetrievalTool.clarification_progress(query, "")
        questions = progress["remaining_questions"]
        if any(name in {"失眠", "多梦", "易醒", "早醒"} for name in symptom_names):
            general_advice = (
                "在信息补充前，可以先保持固定作息，睡前减少咖啡因、酒精和电子屏幕刺激。"
                "如果睡眠问题持续存在、明显影响白天功能，或伴有持续情绪低落等情况，建议及时就医评估。"
            )
        else:
            general_advice = "在信息补充前，先记录症状变化并避免自行使用中药、方剂或穴位治疗；症状明显或持续加重时应及时就医。"
        evidence = graph_evidence[:top_k]
        citations = [item.get("citation") or f"《{item.get('title', '知识图谱关系')}》" for item in evidence]
        graph = result.get("graph", {"nodes": [], "edges": []})
        nodes_by_id = {node.get("id"): node for node in graph.get("nodes", [])}
        safe_edges = [
            edge for edge in graph.get("edges", [])
            if nodes_by_id.get(edge.get("source"), {}).get("type") == "症状"
            and nodes_by_id.get(edge.get("target"), {}).get("type") == "证候"
            and edge.get("label") == "提示"
        ]
        safe_node_ids = {value for edge in safe_edges for value in (edge.get("source"), edge.get("target"))}
        safe_graph = {"nodes": [node for node in graph.get("nodes", []) if node.get("id") in safe_node_ids],
                      "edges": safe_edges}
        return {
            **result,
            "query": query,
            "mode": "evidence-needs-clarification",
            "answer": (
                f"仅凭“{symptom_text}”这些信息，还不能可靠判断具体证候或适合的调理方法。"
                f"当前知识图谱关系与RAG知识库资料提示可能涉及{candidate_text}等不同证候；它们的治法并不相同，"
                "这些关联不能直接当作处方、用药或穴位建议。请先补充症状特点、持续时间、伴随表现、舌象和脉象。"
                + general_advice
            ),
            "formulas": [],
            "herbs": [],
            "follow_up_questions": questions,
            "needs_clarification": True,
            "graph": safe_graph,
            "evidence": evidence,
            "citations": citations,
            "evidence_confidence": "insufficient",
            "retrieval": {"mode": "graph-evidence-gated", "document_hits": 0,
                          "graph_hits": len(evidence), "citations_available": bool(citations)},
            "generation": {"mode": "evidence-gated-clarification"},
            "clarification_topic": query,
            "clarification_progress": progress,
            "clinical_dimensions": progress["clinical_dimensions"],
            "differential_evidence": RAGRetrievalTool.build_differential_evidence(query, {**result, "evidence": evidence}),
        }

    @staticmethod
    def clarification_progress(topic_query: str, collected_text: str) -> dict:
        """Track structured observations and expose only the next highest-information question."""
        full_text = f"{topic_query}\n{collected_text}"
        dimensions = RAGRetrievalTool.parse_clinical_dimensions(full_text)
        is_sleep_topic = any(marker in topic_query for marker in ("失眠", "多梦", "易醒", "早醒"))
        unavailable_text = full_text.replace("不了解", "不清楚")
        all_exam_unavailable = bool(re.search(r"舌质.{0,8}舌苔.{0,8}脉象.{0,8}不清楚", unavailable_text))
        unavailable = []
        low_confidence = [
            key for key, value in dimensions.items() if value.get("confidence") == "low"
        ]

        if is_sleep_topic:
            has_pattern = any(marker in full_text for marker in ("入睡困难", "易醒", "早醒", "多梦"))
            has_course = bool(re.search(r"\d+\s*(?:天|周|月|年|次)|每(?:天|周|月)|持续|长期|偶尔|频繁", full_text))
            has_companions = any(marker in full_text for marker in (
                "心悸", "乏力", "口苦", "胸闷", "痰", "盗汗", "腰膝酸软", "没有伴随", "无伴随", "都没有",
            ))
            checks = [
                ("sleep_pattern", has_pattern and has_course,
                 "主要是入睡困难、易醒、早醒还是多梦？持续多久、每周大约出现几次？"),
                ("companions", has_companions,
                 "是否伴有心悸、乏力、口苦、胸闷痰多、盗汗或腰膝酸软？如果都没有也请说明。"),
                ("tongue_body", dimensions["tongue_body"]["observed"],
                 "舌质主要是淡、红、暗紫，还是接近正常？"),
                ("tongue_coat", dimensions["coat_color"]["observed"] and (
                    dimensions["coat_amount"]["observed"] or dimensions["coat_texture"]["observed"]
                 ), "舌苔是什么颜色？是薄还是厚、润还是燥，是否发腻？"),
                ("pulse", dimensions["pulse_rate"]["observed"] and dimensions["pulse_shape"]["observed"],
                 "脉象快慢如何？是否同时表现为细、弦、滑、沉或浮？"),
            ]
        else:
            has_course = bool(re.search(r"\d+\s*(?:天|周|月|年|次)|持续|长期|偶尔|频繁", full_text))
            has_companions = any(marker in full_text for marker in ("伴有", "同时", "没有伴随", "无伴随"))
            checks = [
                ("course", has_course, "症状从什么时候开始、出现频率和严重程度如何？"),
                ("companions", has_companions, "还有哪些伴随症状，什么情况会加重或缓解？"),
                ("tongue_body", dimensions["tongue_body"]["observed"], "舌质的颜色和形态如何？"),
                ("tongue_coat", dimensions["coat_color"]["observed"] and (
                    dimensions["coat_amount"]["observed"] or dimensions["coat_texture"]["observed"]
                 ), "舌苔的颜色、薄厚、润燥和是否腻分别如何？"),
                ("pulse", dimensions["pulse_rate"]["observed"] and dimensions["pulse_shape"]["observed"],
                 "脉象快慢如何，是否兼细、弦、滑、沉或浮？"),
            ]

        if all_exam_unavailable:
            unavailable.extend(["tongue_body", "tongue_coat", "pulse"])
        else:
            if re.search(r"(?:舌质|舌象).{0,6}不清楚|不清楚.{0,6}(?:舌质|舌象)", unavailable_text):
                unavailable.append("tongue_body")
            if re.search(r"舌苔.{0,6}不清楚|不清楚.{0,6}舌苔", unavailable_text):
                unavailable.append("tongue_coat")
            if re.search(r"(?:脉象|脉).{0,6}不清楚|不清楚.{0,6}(?:脉象|脉)", unavailable_text):
                unavailable.append("pulse")
        answered = [key for key, matched, _ in checks if matched]
        # A short standalone uncertainty reply answers the single question that was
        # pending on the previous turn.  Without this, "不清楚" has no dimension word
        # and the state machine repeats the same tongue/pulse question forever.
        latest_reply = next(
            (line.strip() for line in reversed(collected_text.splitlines()) if line.strip()),
            "",
        )
        if re.fullmatch(r"(?:不清楚|不知道|不了解|不会看|无法判断)[。.!！]?", latest_reply):
            already_resolved = set(answered) | set(unavailable)
            pending_key = next((key for key, _, _ in checks if key not in already_resolved), None)
            if pending_key and pending_key not in unavailable:
                unavailable.append(pending_key)
        resolved = set(answered) | set(unavailable)
        all_remaining = [question for key, _, question in checks if key not in resolved]
        next_questions = all_remaining[:1]
        return {
            "answered": answered,
            "remaining_questions": next_questions,
            "all_remaining_questions": all_remaining,
            "unavailable": unavailable,
            "finished": not all_remaining,
            "low_confidence": low_confidence,
            "complete": not all_remaining and not unavailable,
            "is_sleep_topic": is_sleep_topic,
            "clinical_dimensions": dimensions,
            "next_question_key": next((key for key, _, _ in checks if key not in resolved), None),
        }

    @classmethod
    def is_personal_clinical_request(cls, query: str) -> bool:
        return any(marker in query for marker in cls.PERSONAL_CLINICAL_MARKERS)

    @staticmethod
    def sanitize_clinical_answer(answer: str) -> str:
        """Remove report-style wording and downgrade certainty without replacing the answer."""
        replacements = (
            ("高度契合", "有部分表现相符"),
            ("高度呼应", "有一定对应"),
            ("高度提示", "可作为一种线索"),
            ("整体指向", "可见到相关线索"),
            ("整体偏向", "可以优先讨论"),
            ("整体偏于", "可以优先从"),
            ("整体呈现", "可见到"),
            ("显然", "相对"),
            ("典型表现", "常见线索"),
            ("明确包含", "提及"),
            ("基本确定", "目前仍不能确定"),
            ("更倾向于", "可优先作为候选理解"),
            ("更倾向", "可优先作为候选理解"),
            ("更符合", "有较多表现可以对照"),
            ("较符合", "有部分表现可以对照"),
            ("可能性较大", "较值得进一步核对"),
            ("RAG资料", "相关资料"),
            ("RAG文献", "相关文献"),
            ("RAG召回", "资料检索"),
            ("RAG检索", "资料检索"),
            ("知识库检索", "资料检索"),
            ("文献片段", "资料内容"),
            ("支持点", "相符之处"),
            ("缺失项", "还需确认的信息"),
            ("证据等级", "现有把握"),
            ("图谱路径", "关联线索"),
            ("从教学性辨证角度看", "结合你目前提供的信息"),
            ("从教学性辨证角度", "结合你目前提供的信息"),
        )
        sanitized = answer
        for source, target in replacements:
            sanitized = sanitized.replace(source, target)
        sanitized = re.sub(r"(?:资料内容|资料)(?:对照)?显示[：:]?", "", sanitized)
        sanitized = re.sub(
            r"(?:本轮)?(?:召回|参与比对|检索到)的资料(?:包括|有)[：:]?[^。！？]*[。！？]",
            "",
            sanitized,
        )
        sanitized = re.sub(r"(?:本轮)?资料检索(?:结果)?(?:显示|表明)[：:]?", "", sanitized)
        sanitized = re.sub(r"图谱中的[^，。；]*属于宽泛关联[，。；]?", "相关关系只能作为初步线索，", sanitized)
        sanitized = re.sub(r"(?:相关)?资料(?:内容)?(?:中|里)的候选证候", "可供鉴别的证候", sanitized)
        sanitized = re.sub(
            r"建议以[^。！？；]{0,80}(?:作为|为)(?:主要)?(?:调理|治疗|治法)方向[，。！？；]?",
            "",
            sanitized,
        )
        sanitized = re.sub(r"[^。！？]*(?:泡脚|引火归元)[^。！？]*[。！？]", "", sanitized)
        sanitized = re.sub(r"[^。！？]*需在[^。！？]*(?:调理|治疗)[^。！？]*[。！？]", "", sanitized)
        sanitized = re.sub(r"\s{2,}", " ", sanitized).strip()
        sanitized = re.sub(r"([。！？])\s+", r"\1", sanitized)
        if len(sanitized) > 540:
            boundary = max(sanitized.rfind("。", 0, 500), sanitized.rfind("！", 0, 500), sanitized.rfind("？", 0, 500))
            sanitized = sanitized[:boundary + 1 if boundary >= 260 else 500].rstrip()
            if not sanitized.endswith(("。", "！", "？")):
                sanitized += "。"
        return sanitized

    @staticmethod
    def clinical_output_violations(answer: str) -> list[str]:
        """Return compact, auditable reasons for rejecting a clinical answer."""
        service = get_local_graphrag_service()
        concrete_names = {
            entity.name for entity in service.entities
            if entity.type in {"方剂", "药材"} and len(entity.name) >= 2
        }
        violations = [f"具体实体:{name}" for name in concrete_names if name in answer][:5]
        unsafe_markers = (
            "穴位", "取穴", "按摩", "食疗", "代茶饮", "加减", "重用", "建议服用",
            "证据等级", "图谱路径", "候选方剂", "关联方剂", "高度提示", "八段锦", "气功", "导引",
            "高度契合", "整体指向", "整体呈现", "明确包含", "基本确定", "更倾向", "更符合", "较符合",
            "指向阴虚", "高度呼应",
            "不宜单用", "重在滋阴", "治法应", "治宜", "调理方向", "治疗方向", "泡脚", "引火归元",
            "调理心脾", "兼顾固本",
        )
        violations.extend(f"风险措辞:{marker}" for marker in unsafe_markers if marker in answer)
        # 苔色与苔量是不同维度；“苔黄”和“少苔”可同时出现，不能写成二选一或冲突。
        cross_dimension_conflict = re.search(
            r"(?:苔[‘’“”]?黄[‘’“”]?).{0,30}(?:而非|不一致|矛盾|冲突|不同于).{0,20}(?:少苔|苔少)"
            r"|(?:少苔|苔少).{0,30}(?:而非|不一致|矛盾|冲突|不同于).{0,20}(?:苔[‘’“”]?黄[‘’“”]?)",
            answer,
        )
        if cross_dimension_conflict:
            violations.append("跨维度误判")
        if "<br" in answer.lower():
            violations.append("HTML残留")
        if len(answer) > 550:
            violations.append("正文过长")
        if re.search(r"\d+(?:\.\d+)?\s*(?:克|g|mg|毫克|毫升|ml|粒|片)", answer, re.IGNORECASE):
            violations.append("具体剂量")
        return list(dict.fromkeys(violations))

    @staticmethod
    def clinical_output_is_safe(answer: str) -> bool:
        """Reject individualized outputs containing concrete treatments or unsafe certainty."""
        return not RAGRetrievalTool.clinical_output_violations(answer)

    @classmethod
    def remove_unsafe_clinical_sentences(cls, answer: str) -> str:
        """Keep a grounded LLM answer while removing only unsafe treatment sentences."""
        safe_parts: list[str] = []
        for part in re.split(r"(?<=[。！？])", answer):
            sentence = part.strip()
            if not sentence:
                continue
            if cls.clinical_output_violations(sentence):
                continue
            safe_parts.append(sentence)
        filtered = "".join(safe_parts).strip()
        return filtered if len(filtered) >= 50 else ""

    @staticmethod
    def ensure_clinical_citation(answer: str, evidence_count: int) -> str:
        """Attach one visible citation to the main conclusion when the model omitted all markers."""
        if evidence_count <= 0 or re.search(r"\[\d+\]", answer):
            return answer
        if "。" in answer:
            return answer.replace("。", "[1]。", 1)
        return answer + "[1]"

    @staticmethod
    def relocate_trailing_clinical_citations(answer: str, differential_evidence: list[dict]) -> str:
        """Move citations out of the disclaimer and onto the candidate claims they support."""
        citations = re.findall(r"\[\d+\]", answer)
        if not citations:
            return answer
        disclaimer_match = re.search(
            r"[^。！？]*(?:仅用于|知识学习|不能替代|不替代)[^。！？]*" +
            r"(?:" + "|".join(re.escape(value) for value in citations) + r")+[^。！？]*[。！？]?\s*$",
            answer,
        )
        if not disclaimer_match or not all(answer.find(value) >= disclaimer_match.start() for value in citations):
            return answer

        cleaned = answer
        for value in citations:
            cleaned = cleaned.replace(value, "", 1)
        parts = [part for part in re.split(r"(?<=[。！？])", cleaned) if part]
        used: set[int] = set()
        rows = differential_evidence[:len(citations)]
        for citation, row in zip(citations, rows):
            candidate = str(row.get("candidate") or "").removesuffix("证")
            target = next(
                (index for index, part in enumerate(parts)
                 if index not in used and candidate and candidate in part),
                None,
            )
            if target is None:
                continue
            parts[target] = re.sub(r"([。！？])$", citation + r"\1", parts[target], count=1)
            if not parts[target].endswith(("。", "！", "？")):
                parts[target] += citation
            used.add(target)

        remaining = [value for value in citations if value not in "".join(parts)]
        if remaining:
            target = max(
                (index for index, part in enumerate(parts)
                 if not any(marker in part for marker in ("仅用于", "不能替代", "不替代"))),
                default=0,
            )
            marker = "".join(remaining)
            parts[target] = re.sub(r"([。！？])$", marker + r"\1", parts[target], count=1)
        return "".join(parts)

    @staticmethod
    def clinical_safety_fallback(query: str, result: dict) -> str:
        result["clinical_dimensions"] = RAGRetrievalTool.parse_clinical_dimensions(query)
        if not result.get("differential_evidence"):
            result["differential_evidence"] = RAGRetrievalTool.build_differential_evidence(query, result)
        candidate_summary = RAGRetrievalTool._clinical_candidate_summary(query, result)
        rows = result.get("differential_evidence") or []
        directions = []
        seen_candidates = set()
        for row in rows:
            candidate = str(row.get("candidate") or "候选证候")
            if candidate in seen_candidates:
                continue
            seen_candidates.add(candidate)
            support = (row.get("support") or [])[:4]
            missing = (row.get("missing") or [])[:2]
            sentence = f"{candidate}可以作为一个教学性辨证方向"
            if support:
                sentence += f"，因为现有的{'、'.join(support)}与其常见表现有交集"
            if missing:
                sentence += f"；不过还需要结合{'、'.join(missing)}进一步区分"
            directions.append(sentence + "。")
            if len(directions) == 2:
                break
        natural_synthesis = (
            "在教学辨证上，可先关注以下两个方向。" + "".join(directions)
            if directions else candidate_summary
        )
        sleep_note = (
            "目前可以继续保持规律作息，减少睡前咖啡因、酒精和电子屏幕刺激。"
            if any(marker in query for marker in ("失眠", "多梦", "易醒", "早醒")) else ""
        )
        normal_labels = [
            dimension["label"] for dimension in result.get("clinical_dimensions", {}).values()
            if dimension.get("values") == ["自述正常"]
        ]
        normal_note = (
            f"你自述{'、'.join(normal_labels)}接近正常，这项信息已记录，但其证据强度低于专业面诊观察，"
            "不能单独用于排除某一证候。"
            if normal_labels else ""
        )
        heat_note = (
            "舌红、苔黄、脉数可以作为“有热象”的观察线索，但不能仅凭这三项直接确定阴虚火旺。"
            "苔黄还需区分薄厚、润燥与是否腻，脉数也需结合是否细、弦或滑；这些差异分别可能支持"
            "虚热、郁热或痰热等不同解释。"
            if all(marker in query for marker in ("舌红", "苔黄", "脉数")) else ""
        )
        return (
            "现有信息已经可以支持一轮教学性辨证分析，但还不能据此确定主证。"
            f"{heat_note}{natural_synthesis}这些方向需要结合完整病史和面诊四诊继续鉴别，不能仅凭线上文字定证。"
            f"{normal_note}{sleep_note}本平台不会据此提供具体方剂、药材、剂量、穴位或食疗方案；"
            "如果症状持续存在或明显影响日常功能，建议及时就医评估。"
        )

    @staticmethod
    def _clinical_evidence_comparison(query: str, result: dict) -> str:
        rows = result.get("differential_evidence") or RAGRetrievalTool.build_differential_evidence(query, result)
        comparisons = []
        for row in rows[:2]:
            support = row.get("support") or []
            differences = row.get("differences") or []
            missing = row.get("missing") or []
            if not support and not differences:
                continue
            sentence = f"《{row.get('source_title') or '资料'}》"
            sentence += f"支持{'、'.join(support)}" if support else "未形成直接支持"
            if differences:
                sentence += f"；同维度差异为{'、'.join(differences)}"
            if missing:
                sentence += f"；仍需核对{'、'.join(missing)}"
            comparisons.append(sentence + "。")
        if not comparisons:
            return ""
        return "文献片段对照显示：" + "".join(comparisons[:2])

    @staticmethod
    def _clinical_candidate_summary(query: str, result: dict) -> str:
        graph = result.get("graph", {})
        nodes = {str(node.get("id")): node for node in graph.get("nodes", [])}
        syndrome_names = [str(item) for item in result.get("syndromes", []) if item]
        syndrome_names.extend(
            str(node.get("label") or "")
            for node in graph.get("nodes", [])
            if node.get("type") == "证候" and node.get("label")
        )
        syndrome_names = list(dict.fromkeys(syndrome_names))
        support: dict[str, set[str]] = {name: set() for name in syndrome_names}
        for edge in graph.get("edges", []):
            source = nodes.get(str(edge.get("source")), {})
            target = nodes.get(str(edge.get("target")), {})
            if source.get("type") == "症状" and target.get("type") == "证候":
                symptom = str(source.get("label") or "")
                syndrome = str(target.get("label") or "")
                if symptom and symptom in query and syndrome in support:
                    support[syndrome].add(symptom)

        document_support: dict[str, list[dict]] = {name: [] for name in syndrome_names}
        for item in result.get("evidence", []):
            text = f"{item.get('title', '')}\n{item.get('content', '')}"
            for syndrome in syndrome_names:
                if syndrome and syndrome in text:
                    document_support[syndrome].append(item)

        ranked = sorted(
            syndrome_names,
            key=lambda name: (-(len(support.get(name, set())) * 2 + len(document_support.get(name, []))), name),
        )
        ranked = [name for name in ranked if support.get(name) or document_support.get(name)][:3]
        if not ranked:
            ranked = syndrome_names[:3]
        differentiators = (
            "心悸", "食欲减退", "便溏", "口干", "咽干", "五心烦热", "盗汗", "耳鸣",
            "口苦", "胸闷", "痰多", "舌红", "少苔", "脉细数",
        )
        lines = []
        for syndrome in ranked:
            matched = sorted(support.get(syndrome, set()))
            docs = document_support.get(syndrome, [])
            doc_text = " ".join(str(item.get("content") or "") for item in docs)
            missing = [term for term in differentiators if term in doc_text and term not in query][:3]
            support_text = "、".join(matched) if matched else "文献中的相似表现"
            line = f"{syndrome}：现有支持点为{support_text}"
            if docs:
                line += "，相关资料中也有相似描述"
            if missing:
                line += f"；仍需核对{'、'.join(missing)}等鉴别信息"
            lines.append(line + "。")
        if not lines:
            return "现有信息尚未形成足够一致的候选证候，暂不强行归纳主证。"
        return "教学性候选鉴别为：" + "".join(lines)

    @staticmethod
    def _sanitize_clinical_evidence(content: str) -> str:
        safe_lines = []
        for raw_line in content.splitlines():
            line = re.split(r"(?:治宜|方用|选方|药用|汤药：|可用|加减)[:：]?", raw_line, maxsplit=1)[0].strip()
            if line:
                safe_lines.append(line)
        return "\n".join(safe_lines)

    @staticmethod
    def _insufficient(query: str, reason: str) -> dict:
        return {"query": query, "mode": "evidence-insufficient", "answer": f"证据不足：{reason}，当前不能给出可靠结论。",
                "graph": {"nodes": [], "edges": []}, "evidence": [], "citations": [], "syndromes": [],
                "formulas": [], "herbs": [], "evidence_confidence": "insufficient",
                "retrieval": {"mode": "evidence-gated", "document_hits": 0, "graph_hits": 0,
                              "citations_available": False}}

    @staticmethod
    def _normalize_answer_mode(answer_mode: str) -> str:
        return answer_mode if answer_mode in {"concise", "teaching", "deep"} else "concise"

    @classmethod
    def build_generation_messages(cls, query: str, result: dict,
                                  answer_mode: str = "concise") -> list[dict]:
        """Build the single evidence-grounded generation prompt used by sync and SSE APIs."""
        answer_mode = cls._normalize_answer_mode(answer_mode)
        clinical_request = cls.is_personal_clinical_request(query)
        clinical_dimensions = result.get("clinical_dimensions") or (
            cls.parse_clinical_dimensions(query) if clinical_request else {}
        )
        differential_evidence = result.get("differential_evidence") or (
            cls.build_differential_evidence(query, result) if clinical_request else []
        )
        candidate_names = {
            str(row.get("candidate") or "").removesuffix("证")
            for row in differential_evidence[:2] if row.get("candidate")
        }
        evidence_items = list(result.get("evidence", []))[:5]
        if clinical_request and candidate_names:
            selected_documents = [
                item for item in evidence_items
                if any(name and name in str(item.get("title") or "") for name in candidate_names)
            ]
            if selected_documents:
                evidence_items = selected_documents[:5]
        evidence_lines = []
        for index, item in enumerate(evidence_items, 1):
            content = str(item.get("content", ""))[:900]
            if clinical_request:
                content = cls._sanitize_clinical_evidence(content)
            evidence_lines.append(
                f"[{index}] 来源：{item.get('citation') or item.get('title')}\n"
                f"内容：{content}"
            )
        graph_edges = list(result.get("graph", {}).get("edges", []))[:12]
        if clinical_request and candidate_names:
            graph_edges = [
                edge for edge in graph_edges
                if any(
                    name and (name in str(edge.get("source_name") or "")
                              or name in str(edge.get("target_name") or ""))
                    for name in candidate_names
                )
            ]
        graph_lines = [
            f"{edge.get('source_name', '')} --{edge.get('label', '')}--> {edge.get('target_name', '')}；依据：{edge.get('evidence', '')}"
            for edge in graph_edges
        ]
        heat_markers = ("五心烦热", "潮热", "盗汗", "口干", "咽干", "舌红", "苔黄", "脉数")
        heat_instruction = (
            "用户当前没有提供明确热象，禁止写成心火偏亢、阴虚火旺或虚热已成立；"
            "若相关资料提到这些表现，只能把它们作为尚需询问的鉴别信息。"
            if clinical_request and not any(marker in query for marker in heat_markers) else ""
        )
        mode_instructions = {
            "concise": (
                "默认用2至3个连贯的自然段回答，总长度控制在350个汉字以内。先直接回答，再补充最必要的解释。"
                "除非问题明确要求列举、对比或步骤，否则不要使用标题、固定模板、项目符号或表格。"
            ),
            "teaching": (
                "面向学习者解释结论背后的配伍、病机或辨证逻辑。可以使用少量小标题，"
                "但仍以连贯讲解为主，避免把资料逐条改写成清单。"
            ),
            "deep": (
                "给出较完整的分析，并清楚区分直接证据、图谱关系和需要谨慎理解的推断。"
                "只有在比较、层级或多步骤内容确实更清楚时才使用表格或分点。"
            ),
        }
        if any(marker in query for marker in ("对比", "比较", "区别", "异同")):
            question_style = "这是比较类问题：先用一句话概括核心差异，再用紧凑表格呈现真正可比的维度。"
        elif any(marker in query for marker in ("详细", "深入", "为什么", "机理", "原理")):
            question_style = "这是解释类问题：按因果顺序讲清依据和逻辑，不要只罗列结论。"
        elif any(marker in query for marker in ("组成", "有哪些", "是什么", "功效", "作用")):
            question_style = "这是事实查询：直接用自然段回答核心事实，内容较少时不要强行拆成清单。"
        else:
            question_style = "根据问题本身选择最自然的表达，不套用固定栏目。"
        messages = [
            {"role": "system", "content": (
                "你是面向中医药知识学习和辨证辅助的智能问答助手。先理解用户真正想知道什么，再自然作答。"
                + mode_instructions[answer_mode] + question_style +
                "只能使用给定图谱关系和资料片段，不得补造方剂、功效、剂量或适应证。"
                "不要复述检索过程，不要说“根据知识库检索到”，不要在正文末尾重复完整参考文献列表。"
                "正文必须像教师与学习者自然交流：先直接回应用户当前最关心的问题，再用连贯语言解释至多两个候选方向及区分点。"
                "检索结果只是你的内部依据，不是回答的叙事主角；正文不要汇报查到了什么、哪条资料支持什么，也不要逐项做数据库式对照。"
                "优先写成两到三个自然段：第一段给出当前辨证范围，第二段解释为什么以及怎样区分；信息不足时再用一句话说明还缺什么。"
                "默认只选一条最值得讨论的辨证主线，再补充一个确有必要排除的替代方向；正文最多出现两个候选证候名称。"
                "这个上限包含鉴别句中出现的名称；禁止按A证、B证、C证依次罗列，也不要在结尾顺带追加第三或第四个证候。"
                "不得给出滋阴、清热、降火、交通心肾等个体化治法或调理方向，只能给规律作息等低风险通用建议。"
                + heat_instruction +
                "候选证据对照已经按同维度舌脉和症状匹配排序；应优先解释分数最高者，较低分候选只能作为待排除方向。"
                "不要逐条抄写资料标题，不要出现“RAG”“文献片段对照显示”“参与比对的资料”“支持点”“缺失项”"
                "“图谱中的某关系属于宽泛关联”等系统内部报告用语；这些结构化内容只放在界面的“查看依据”和“详情”中。"
                "每个自然段最多集中标注一次引用，引用必须放在该段最后一句的句末，不能插在段落中间；"
                "多个来源合并写成[1][2]。详细来源由界面的“查看依据”展示。"
                "若证据支持不同证候，应解释需要哪些舌脉或兼症才能区分，不能直接给患者开方。"
                "用户自述舌质、舌苔或脉象“正常”时，应接受为低精度自述信息，"
                "但必须说明它不等同于专业面诊确认，也不能据此排除证候。"
                "若问题描述的是用户本人或具体患者，即使资料看似充分，也禁止输出任何具体方剂名、"
                "药材名、剂量、加减法、穴位、按摩、食疗或具体功法方案；不能使用“高度提示”“基本确定”"
                "“整体指向”“高度契合”“明确包含”等超出证据强度的表述。候选证候的依据和不确定性应自然融入解释，"
                "不要输出支持点、缺失项、证据等级等报告栏目。舌质、苔色、苔量、苔质、脉率和脉形必须分维度理解；"
                "苔黄属于苔色、少苔属于苔量，二者可以同时存在，禁止把它们写成互相矛盾。"
                "只能说明教学性候选证候、鉴别边界和低风险通用生活建议。"
                "只有涉及诊疗选择、用药或个体化建议时，才在结尾简短说明用于知识学习、不替代医师诊断处方；"
                "纯粹的药材或方剂知识查询不必机械添加同一句免责声明。")},
            {"role": "user", "content": f"问题：{query}\n\n图谱关系：\n" + "\n".join(graph_lines)
             + "\n\n资料片段：\n" + "\n\n".join(evidence_lines)
             + ("\n\n结构化四诊：\n" + json.dumps(clinical_dimensions, ensure_ascii=False)
                + "\n\n候选证据对照（支持/同维度差异/缺失）：\n"
                + json.dumps(differential_evidence, ensure_ascii=False) if clinical_request else "")},
        ]
        return messages

    @classmethod
    def _generate_answer(cls, query: str, result: dict, answer_mode: str = "concise") -> dict | None:
        client = get_llm_client()
        if not client.available:
            return None
        messages = cls.build_generation_messages(query, result, answer_mode)
        return client.complete(messages, temperature=0.25)
