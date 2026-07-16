from __future__ import annotations

import re
from dataclasses import dataclass

from backend.domain.clinical_terms import PULSE_KEYWORDS, SYMPTOM_KEYWORDS, TONGUE_KEYWORDS
from backend.services.local_graphrag_service import Entity, get_local_graphrag_service


@dataclass(frozen=True)
class EntityMatch:
    name: str
    entity_id: str
    entity_type: str
    score: float
    reason: str


class SymptomAnalysisAgent:
    """Extract and normalize symptoms, tongue and pulse data.

    The previous version only used a tiny hard-coded keyword table, so a small
    wording change such as “胸胁胀痛” vs “胁痛” broke the main graph pipeline.
    This version works as a lightweight entity linker over the full KG symptom
    table:

    1. exact canonical-name / alias matching;
    2. curated synonym normalization for common clinical wording;
    3. description phrase matching from KG entity descriptions;
    4. conservative character-overlap matching inside short text clauses.
    """

    CURATED_ALIASES: dict[str, list[str]] = {
        "失眠": ["不寐", "睡眠不安", "睡眠不好", "睡眠不佳", "睡不着", "睡不安稳", "夜寐不安", "入睡困难"],
        "多梦": ["梦多", "梦扰", "夜梦多"],
        "心悸": ["心慌", "心跳不安", "心跳不适", "怔忡"],
        "健忘": ["记忆力下降", "记忆力减退", "容易忘事"],
        "心烦": ["烦热", "烦躁", "心中烦躁", "五心烦热"],
        "神疲": ["精神疲倦", "精神疲乏", "精神差", "疲倦"],
        "乏力": ["体倦", "疲乏", "无力", "四肢无力", "全身乏力"],
        "食少": ["食欲下降", "食欲不振", "食欲减退", "胃口差", "胃纳差", "不想吃饭", "纳少", "纳呆"],
        "纳差": ["食欲下降", "食欲不振", "食欲减退", "胃口差", "胃纳差", "纳呆"],
        "腹胀": ["腹部胀满", "肚子胀", "脘腹胀满", "胃胀"],
        "便溏": ["大便稀", "稀便", "大便不成形", "便软"],
        "腹泻": ["拉肚子", "泄泻", "大便次数增多"],
        "便秘": ["大便干结", "排便困难"],
        "胁痛": ["胸胁胀痛", "胸胁痛", "胁肋胀痛", "两胁胀痛", "胁胀", "胁肋不舒", "胸胁不舒"],
        "胸闷": ["胸部满闷", "胸口闷", "胸中郁闷"],
        "胸痛": ["胸部疼痛", "胸口痛"],
        "情志抑郁": ["情绪抑郁", "情绪低落", "抑郁", "郁闷", "心情低落", "心情郁闷"],
        "烦躁易怒": ["易怒", "急躁", "烦躁", "容易发脾气"],
        "善太息": ["容易叹气", "叹气", "太息", "频频叹气", "总叹气"],
        "腰膝酸软": ["腰膝酸", "腰酸膝软", "腰膝无力", "腰腿酸软"],
        "盗汗": ["夜间出汗", "睡后汗出", "入睡后出汗"],
        "自汗": ["白天出汗", "动则汗出"],
        "潮热": ["阵阵发热", "午后潮热"],
        "手足心热": ["五心烦热", "手心脚心热", "手足烦热"],
        "口燥咽干": ["口干咽燥", "口干", "咽干", "咽燥", "口咽干燥"],
        "口苦": ["嘴苦", "口中发苦"],
        "头晕": ["眩晕", "头昏", "头部昏沉"],
        "头痛": ["头疼", "头部疼痛"],
        "耳鸣": ["耳中鸣响"],
        "咳嗽": ["咳", "咳声"],
        "气喘": ["喘", "喘息", "呼吸困难", "气急"],
        "痰多": ["咳痰多", "痰量多"],
        "恶寒": ["怕冷", "畏冷"],
        "畏寒肢冷": ["四肢不温", "手脚冰凉", "肢冷"],
        "面色萎黄": ["面黄", "面色黄", "面色少华"],
        "面色苍白": ["脸色苍白", "面白"],
        "面色红赤": ["面红", "面部潮红", "脸红"],
        "舌淡": ["淡舌", "舌质淡"],
        "舌红": ["红舌", "舌质红", "舌质红赤"],
        "舌胖大": ["胖大舌", "舌体胖大"],
        "舌有齿痕": ["齿痕舌", "舌边齿痕"],
        "舌苔白": ["苔白", "白苔", "苔薄白", "薄白苔", "舌苔薄白"],
        "舌苔黄": ["苔黄", "黄苔"],
        "舌苔腻": ["苔腻", "腻苔", "黄腻苔", "白腻苔"],
        "舌苔少": ["少苔", "舌红少苔", "苔少"],
        "脉细": ["细脉"],
        "脉弱": ["弱脉"],
        "脉沉": ["沉脉"],
        "脉数": ["数脉", "脉细数", "细数"],
        "脉弦": ["弦脉"],
        "脉滑": ["滑脉"],
        "脉紧": ["紧脉"],
    }

    SUPPLEMENTAL_SYMPTOMS: dict[str, list[str]] = {
        "牙龈肿痛": ["牙龈肿痛", "牙龈肿", "牙龈痛", "齿龈肿痛", "牙痛", "齿痛"],
        "口臭": ["口臭", "口气臭", "口气重", "口中臭秽"],
        "口渴喜冷饮": ["口渴喜冷饮", "喜冷饮", "渴喜冷饮", "喜欢喝冷饮"],
    }

    TONGUE_MARKERS = ("舌", "苔")
    PULSE_MARKERS = ("脉",)

    GENERIC_NOISE = {
        "患者",
        "近期",
        "近来",
        "近两周",
        "请进行中医辨证教学分析",
        "请进行中医辨证分析",
        "中医辨证教学分析",
    }

    def run(self, case_text: str) -> dict:
        print("[SymptomAnalysisAgent] start")

        matches = self._link_kg_symptoms(case_text)

        symptoms = self._unique(
            [
                *self._match_keywords(case_text, SYMPTOM_KEYWORDS),
                *[
                    match.name
                    for match in matches
                    if not self._is_tongue(match.name) and not self._is_pulse(match.name)
                ],
                *self._match_supplemental_symptoms(case_text),
            ]
        )
        symptoms = self._prune_subsumed_terms(symptoms)
        tongue = self._unique(
            [
                *self._match_keywords(case_text, TONGUE_KEYWORDS),
                *[match.name for match in matches if self._is_tongue(match.name)],
            ]
        )
        pulse = self._unique(
            [
                *self._match_keywords(case_text, PULSE_KEYWORDS),
                *[match.name for match in matches if self._is_pulse(match.name)],
            ]
        )
        raw_entities = symptoms + tongue + pulse

        result = {
            "symptoms": symptoms,
            "tongue": tongue,
            "pulse": pulse,
            "raw_entities": raw_entities,
            "normalized_matches": [
                {
                    "name": match.name,
                    "entity_id": match.entity_id,
                    "score": match.score,
                    "reason": match.reason,
                }
                for match in matches
            ],
        }
        print("[SymptomAnalysisAgent] completed")
        return result

    def _link_kg_symptoms(self, text: str) -> list[EntityMatch]:
        try:
            service = get_local_graphrag_service()
        except Exception:
            return []

        symptom_entities = [entity for entity in service.entities if entity.type == "症状"]
        clauses = self._extract_clauses(text)
        matches: dict[str, EntityMatch] = {}

        for entity in symptom_entities:
            for alias in self._entity_aliases(entity):
                if not alias:
                    continue
                if alias in text:
                    if self._is_contextually_blocked(entity.name, alias, text):
                        continue
                    self._keep_best(
                        matches,
                        EntityMatch(entity.name, entity.id, entity.type, 1.0, f"exact:{alias}"),
                    )

        for clause in clauses:
            if len(clause) < 2 or clause in self.GENERIC_NOISE:
                continue
            normalized_clause = self._normalize_text(clause)

            for entity in symptom_entities:
                if self._is_contextually_blocked(entity.name, "", text):
                    continue
                entity_terms = self._entity_aliases(entity)

                for alias in entity_terms:
                    normalized_alias = self._normalize_text(alias)
                    if not normalized_alias:
                        continue

                    if normalized_alias in normalized_clause:
                        self._keep_best(
                            matches,
                            EntityMatch(entity.name, entity.id, entity.type, 0.92, f"normalized:{clause}->{alias}"),
                        )
                        continue
                    if normalized_clause in normalized_alias:
                        self._keep_best(
                            matches,
                            EntityMatch(entity.name, entity.id, entity.type, 0.92, f"normalized:{clause}->{alias}"),
                        )
                        continue

                    score = self._char_overlap_score(normalized_clause, normalized_alias)
                    threshold = self._threshold_for(alias)
                    if score >= threshold:
                        self._keep_best(
                            matches,
                            EntityMatch(entity.name, entity.id, entity.type, score, f"fuzzy:{clause}->{alias}"),
                        )

        return sorted(matches.values(), key=lambda item: (-item.score, item.entity_id))

    def _entity_aliases(self, entity: Entity) -> list[str]:
        aliases = [entity.name, entity.alias]
        aliases.extend(self.CURATED_ALIASES.get(entity.name, []))

        # Use short KG description fragments as weak aliases.  Example:
        # "食欲减退，进食量少" helps normalize "食欲下降".
        # Imported descriptions can be broad, so only short fragments are used
        # as weak aliases.
        source = ""
        if entity.properties:
            source = str(entity.properties.get("source") or "")
        if not source.lower().startswith("external"):
            for part in re.split(r"[，、；;。\s]+", entity.description or ""):
                part = part.strip()
                if 2 <= len(part) <= 8:
                    aliases.append(part)

        return self._unique([alias for alias in aliases if alias])

    def _prune_subsumed_terms(self, terms: list[str]) -> list[str]:
        """Remove noisy external child terms once a more specific term exists."""
        if not terms:
            return []

        sorted_terms = sorted(self._unique(terms), key=lambda item: (-len(item), terms.index(item)))
        keep: list[str] = []
        for term in sorted_terms:
            if any(term in longer and term != longer for longer in keep):
                continue
            keep.append(term)

        keep_set = set(keep)
        return [term for term in terms if term in keep_set]

    @staticmethod
    def _is_contextually_blocked(entity_name: str, alias: str, text: str) -> bool:
        if entity_name == "发热" and alias == "发热":
            local_heat_markers = ["五心烦热", "手心脚心发热", "手足心热", "手足烦热"]
            if any(marker in text for marker in local_heat_markers):
                return True
        return False

    def _extract_clauses(self, text: str) -> list[str]:
        parts = re.split(r"[，,。；;、\n\r\t ]+", text)
        clauses: list[str] = []
        for part in parts:
            part = part.strip("：:！？!?（）()“”\"'")
            if not part or part in self.GENERIC_NOISE:
                continue
            clauses.append(part)

            # Add shorter symptom-like chunks inside longer phrases.
            for marker in ["痛", "胀", "闷", "热", "冷", "汗", "干", "苦", "晕", "咳", "喘", "泻", "秘"]:
                if marker in part and len(part) > 4:
                    clauses.append(part[-4:])
        return self._unique(clauses)

    @staticmethod
    def _normalize_text(text: str) -> str:
        replacements = {
            "下降": "减退",
            "降低": "减退",
            "变差": "不佳",
            "不好": "不佳",
            "不安稳": "不安",
            "容易": "易",
            "经常": "常",
            "胸胁": "胁",
            "胁肋": "胁",
            "咽燥": "咽干",
            "口干": "口燥",
            "手心脚心": "手足心",
            "睡眠": "失眠",
            "胃口": "食欲",
            "食欲": "纳",
            "情绪": "情志",
            "心情": "情志",
            "叹气": "太息",
            "疼": "痛",
        }
        normalized = text
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        return normalized

    @staticmethod
    def _char_overlap_score(left: str, right: str) -> float:
        if not left or not right:
            return 0.0

        left_chars = set(left)
        right_chars = set(right)
        overlap = len(left_chars & right_chars)
        containment = overlap / max(1, min(len(left_chars), len(right_chars)))
        jaccard = overlap / max(1, len(left_chars | right_chars))

        order_bonus = 0.0
        if len(right) <= 3 and all(char in left for char in right):
            order_bonus = 0.25

        return min(1.0, containment * 0.72 + jaccard * 0.28 + order_bonus)

    @staticmethod
    def _threshold_for(alias: str) -> float:
        if len(alias) <= 2:
            return 0.96
        if len(alias) <= 4:
            return 0.82
        return 0.74

    @staticmethod
    def _keep_best(matches: dict[str, EntityMatch], match: EntityMatch) -> None:
        current = matches.get(match.entity_id)
        if current is None or match.score > current.score:
            matches[match.entity_id] = match

    def _match_keywords(self, text: str, keyword_map: dict[str, list[str]]) -> list[str]:
        results = []
        for normalized, aliases in keyword_map.items():
            if any(alias in text for alias in aliases):
                results.append(normalized)
        return results

    def _match_supplemental_symptoms(self, text: str) -> list[str]:
        results = []
        for normalized, aliases in self.SUPPLEMENTAL_SYMPTOMS.items():
            if any(alias in text for alias in aliases):
                results.append(normalized)
        return results

    def _is_tongue(self, name: str) -> bool:
        return any(marker in name for marker in self.TONGUE_MARKERS)

    def _is_pulse(self, name: str) -> bool:
        return any(marker in name for marker in self.PULSE_MARKERS)

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        result = []
        for value in values:
            value = str(value).strip()
            if value and value not in result:
                result.append(value)
        return result
