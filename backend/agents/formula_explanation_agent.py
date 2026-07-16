from __future__ import annotations

from backend.services.local_graphrag_service import Entity, Relation, get_local_graphrag_service


class FormulaExplanationAgent:
    """Explain formula composition, effects and teaching notes.

    Only verified knowledge-graph entities and relationships are used. Unknown
    formulas return an explicit evidence-insufficient result.
    """

    def run(self, formulas: list[str]) -> dict:
        print("[FormulaExplanationAgent] start")
        explanations = []
        for formula in self._unique(formulas):
            explanation = self._explain_from_kg(formula)
            if explanation is None:
                explanation = {"name": formula, "composition": [], "effects": [],
                               "main_indications": [], "evidence_status": "insufficient",
                               "notes": "证据不足：该方剂不在当前正式知识图谱中，未使用非正式数据补全。"}
            explanations.append(explanation)

        result = {"formula_explanations": explanations}
        print("[FormulaExplanationAgent] completed")
        return result

    def _explain_from_kg(self, formula_name: str) -> dict | None:
        try:
            service = get_local_graphrag_service()
        except Exception:
            return None

        formula = self._find_formula(service.entities, formula_name)
        if formula is None:
            return None

        outgoing = service.outgoing.get(formula.id, [])
        incoming = service.incoming.get(formula.id, [])

        herbs = self._collect_targets(service, outgoing, target_type="药材")
        indications = self._collect_indications(service, formula, outgoing, incoming)
        sources = self._collect_sources([*outgoing, *incoming])

        properties = formula.properties or {}
        note = str(properties.get("note") or "").strip()
        source = str(properties.get("source") or "").strip()

        notes = []
        if note:
            notes.append(note)
        if source:
            notes.append(f"来源：{source}")
        if sources:
            notes.append("关系依据：" + "、".join(sources[:3]))

        return {
            "name": formula.name,
            "composition": herbs,
            "effects": [formula.description] if formula.description else [],
            "main_indications": indications,
            "notes": "；".join(notes) if notes else "来自 entities_relations 知识图谱。",
        }

    @staticmethod
    def _find_formula(entities: list[Entity], formula_name: str) -> Entity | None:
        formula_name = formula_name.strip()
        for entity in entities:
            if entity.type != "方剂":
                continue
            if entity.name == formula_name or entity.alias == formula_name:
                return entity
        for entity in entities:
            if entity.type == "方剂" and (entity.name in formula_name or formula_name in entity.name):
                return entity
        return None

    @staticmethod
    def _collect_targets(service, relations: list[Relation], target_type: str) -> list[str]:
        values = []
        for relation in relations:
            target = service.entities_by_id.get(relation.target_id)
            if target and target.type == target_type:
                values.append(target.name)
        return FormulaExplanationAgent._unique(values)

    @staticmethod
    def _collect_indications(service, formula: Entity, outgoing: list[Relation], incoming: list[Relation]) -> list[str]:
        indications = []

        for relation in outgoing:
            target = service.entities_by_id.get(relation.target_id)
            if target and target.type == "证候":
                indications.append(target.name)

        for relation in incoming:
            source = service.entities_by_id.get(relation.source_id)
            if source and source.type == "证候":
                indications.append(source.name)

        # Some data stores 方剂 -> 证候 as "主治", others stores 证候 -> 方剂 as
        # "对应"; the two loops above intentionally support both.
        return FormulaExplanationAgent._unique(indications)

    @staticmethod
    def _collect_sources(relations: list[Relation]) -> list[str]:
        return FormulaExplanationAgent._unique(
            [relation.evidence for relation in relations if relation.evidence]
        )

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        result = []
        for value in values:
            value = str(value).strip()
            if value and value not in result:
                result.append(value)
        return result
