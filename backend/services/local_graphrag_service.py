from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


TYPE_TO_FIELD = {
    "症状": "symptoms",
    "证候": "syndromes",
    "方剂": "formulas",
    "药材": "herbs",
}


INTENT_LABELS = {
    "formula_composition": "方剂组成查询",
    "syndrome_manifestation": "证候症状表现查询",
    "symptom_to_formula": "症状到方剂查询",
    "mechanism_explanation": "配伍/机制解释查询",
    "effect_query": "功效作用查询",
    "contraindication_query": "禁忌注意查询",
    "definition_query": "概念定义查询",
    "general": "一般知识查询",
}


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    type: str
    alias: str = ""
    description: str = ""
    properties: dict[str, Any] | None = None


@dataclass(frozen=True)
class Relation:
    source_id: str
    source_name: str
    relation: str
    target_id: str
    target_name: str
    evidence: str = ""
    source_type: str = ""
    target_type: str = ""


@dataclass(frozen=True)
class TextChunk:
    title: str
    source: str
    content: str
    score: float = 0.0


class LocalGraphRAGService:
    """Dependency-light GraphRAG adapter for the teaching agent.

    It intentionally avoids Milvus/OpenAI runtime requirements so the project can
    show an integrated GraphRAG effect immediately.  The data contract mirrors
    the teammate GraphRAG module: text evidence + graph paths + structured
    syndrome/formula/herb output.
    """

    def __init__(self) -> None:
        self.graph_repo_root = Path(__file__).resolve().parents[2]
        self.graph_root = self.graph_repo_root / "data"
        self.member3_root = self.graph_repo_root / "member3"

        self.deleted_entity_ids, self.deleted_relation_keys = self._load_admin_deletions()
        self.entities = [
            entity
            for entity in self._load_entity_sources()
            if entity.id not in self.deleted_entity_ids
        ]
        self.entities_by_id = {entity.id: entity for entity in self.entities}
        self.relations = [
            relation
            for relation in self._load_relation_sources()
            if relation.source_id not in self.deleted_entity_ids
            and relation.target_id not in self.deleted_entity_ids
            and self._relation_key(relation) not in self.deleted_relation_keys
        ]
        self.entities_by_name = self._build_name_index(self.entities)
        self.outgoing = self._build_outgoing(self.relations)
        self.incoming = self._build_incoming(self.relations)
        self.text_chunks = self._load_text_chunks()

    def _load_admin_deletions(self) -> tuple[set[str], set[str]]:
        path = self.graph_root / "admin_overlay.json"
        if not path.exists():
            return set(), set()
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return set(), set()
        return (
            {str(item) for item in data.get("deleted_entity_ids", [])},
            {str(item) for item in data.get("deleted_relation_keys", [])},
        )

    @staticmethod
    def _relation_key(relation: Relation) -> str:
        return f"{relation.source_id}|{relation.relation}|{relation.target_id}"

    def search(
        self,
        query: str,
        syndromes: list[str] | None = None,
        formulas: list[str] | None = None,
        top_k: int = 5,
        max_hops: int = 2,
    ) -> dict:
        intent = self._detect_intent(query)
        seed_names = self._unique([query, *(syndromes or []), *(formulas or [])])
        seed_entities = self._match_entities(" ".join(seed_names))

        candidate_graph = self._expand_graph(seed_entities, max_hops=max_hops)
        graph = self._prune_graph_by_intent(query=query, intent=intent, graph=candidate_graph)
        graph_terms = [node["label"] for node in graph["nodes"]]
        ranked_chunks = self._rank_chunks(
            " ".join([query, *seed_names, *graph_terms]),
            priority_terms=[name for name in seed_names if len(name) >= 2],
        )
        ranked_chunks = self._select_relevant_chunks(
            query=query,
            chunks=ranked_chunks,
            intent=intent,
            top_k=max(top_k, 1),
        )

        if intent == "symptom_to_formula" and graph.get("edges"):
            # 图谱路径已经能说明“症状—证候—方剂”时，压住文本里散落的
            # 养生汤、食疗方或相邻方剂，避免主答案发散。
            ranked_chunks = []

        evidence = [
            {
                "title": chunk.title,
                "source": chunk.source,
                "content": chunk.content,
                "score": round(chunk.score, 4),
            }
            for chunk in ranked_chunks[:top_k]
        ]

        graph_evidence = self._graph_evidence(graph, query=query)
        evidence_limit = max(top_k, 10) if self._needs_expanded_evidence(query) else top_k
        evidence = self._dedupe_evidence([*graph_evidence, *evidence])[:evidence_limit]

        structured = self._structured_from_graph(graph)
        structured = self._filter_structured_by_intent(intent, structured)
        answer = self._build_answer(
            query=query,
            evidence=evidence,
            graph=graph,
            structured=structured,
            intent=intent,
        )

        return {
            "query": query,
            "mode": "local-graphrag",
            "intent": intent,
            "intent_label": INTENT_LABELS.get(intent, "一般知识查询"),
            "graph": graph,
            "related_entities": graph.get("nodes", []),
            "reasoning_paths": self._reasoning_paths(graph),
            "evidence": evidence,
            "answer": answer,
            **structured,
        }

    @staticmethod
    def _detect_intent(query: str) -> str:
        """Lightweight port of teammate feat/graphrag intent detection."""
        text = query.strip().lower()

        if any(
            keyword in text
            for keyword in [
                "包含哪些药材",
                "含有哪些药材",
                "由哪些药材组成",
                "有哪些药材组成",
                "组成是什么",
                "方中有哪些",
                "药物组成",
                "方剂组成",
                "组成药材",
                "包含什么药材",
            ]
        ):
            return "formula_composition"

        if any(
            keyword in text
            for keyword in [
                "有哪些症状",
                "有什么症状",
                "典型症状",
                "主要症状",
                "有哪些表现",
                "典型表现",
                "主要表现",
                "临床表现",
                "体征",
            ]
        ):
            return "syndrome_manifestation"

        if any(
            keyword in text
            for keyword in [
                "有什么方剂",
                "哪些方剂",
                "用什么方剂",
                "推荐什么方剂",
                "对应什么方剂",
                "可用什么方剂",
                "关联哪些方剂",
                "相关方剂",
                "哪些证候和方剂",
            ]
        ):
            return "symptom_to_formula"

        if any(
            keyword in text
            for keyword in [
                "为什么",
                "为何",
                "原因",
                "机制",
                "机理",
                "原理",
                "反佐",
                "配伍",
                "佐制",
                "相须",
                "相使",
                "相畏",
                "相杀",
            ]
        ):
            return "mechanism_explanation"

        if any(
            keyword in text
            for keyword in [
                "有什么功效",
                "有哪些功效",
                "什么功效",
                "有什么作用",
                "有哪些作用",
                "主治什么",
                "功效是什么",
            ]
        ):
            return "effect_query"

        if any(keyword in text for keyword in ["禁忌", "慎用", "不宜", "注意事项", "不能用"]):
            return "contraindication_query"

        if any(keyword in text for keyword in ["是什么", "什么是", "定义", "解释一下", "介绍一下", "概念"]):
            return "definition_query"

        return "general"

    @staticmethod
    def _extract_query_hint(query: str) -> str:
        text = query.strip().lower()
        for prefix in ["请问", "我想知道", "想了解", "请介绍一下", "介绍一下", "请说明"]:
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()
                break

        suffixes = [
            "包含哪些药材？",
            "包含哪些药材",
            "含有哪些药材？",
            "含有哪些药材",
            "由哪些药材组成？",
            "由哪些药材组成",
            "有哪些药材组成？",
            "有哪些药材组成",
            "组成是什么？",
            "组成是什么",
            "药物组成是什么？",
            "药物组成是什么",
            "有哪些典型症状表现？",
            "有哪些典型症状表现",
            "有哪些典型表现？",
            "有哪些典型表现",
            "有哪些症状？",
            "有哪些症状",
            "有什么症状？",
            "有什么症状",
            "主要症状是什么？",
            "主要症状是什么",
            "有什么方剂？",
            "有什么方剂",
            "有哪些方剂？",
            "有哪些方剂",
            "有什么功效？",
            "有什么功效",
            "有哪些功效？",
            "有哪些功效",
            "有什么作用？",
            "有什么作用",
            "有哪些作用？",
            "有哪些作用",
            "是什么？",
            "是什么",
            "为什么？",
            "为什么",
        ]
        for suffix in suffixes:
            if text.endswith(suffix):
                text = text[: -len(suffix)].strip()
                break

        if text.startswith("治疗"):
            text = text[len("治疗") :].strip()
        return text

    def _extract_query_entities(self, query: str) -> list[str]:
        query_text = query.strip().lower()
        result: list[str] = []
        for entity in self.entities:
            for name in [entity.name, entity.alias]:
                if name and name.strip() and name.lower() in query_text and name not in result:
                    result.append(name)
        for match in re.finditer(r"[\u4e00-\u9fff]{2,12}(?:汤|丸|散|方|丹)", query):
            value = match.group(0)
            if value not in result:
                result.append(value)
        return result

    def query_by_symptoms(self, symptoms: list[str]) -> dict:
        seed_entities: list[Entity] = []
        for symptom in symptoms:
            seed_entities.extend(self._find_entities_by_name(symptom))

        graph = self._targeted_symptom_graph(self._unique_entities(seed_entities))
        structured = self._structured_from_graph(graph)

        if not structured["syndromes"] and not structured["formulas"]:
            nodes = [
                {"id": f"input:{index}", "label": symptom, "type": "症状"}
                for index, symptom in enumerate(symptoms, start=1)
            ]
            return {
                "syndromes": [],
                "formulas": [],
                "herbs": [],
                "graph": {"nodes": nodes, "edges": []},
                "reasoning_paths": ["当前症状未能在完整图谱中形成稳定的证候/方剂路径"],
                "reason": "未匹配到足够的症状—证候—方剂关系，可补充舌象、脉象或更具体症状。",
                "confidence": 0,
                "needs_clarification": True,
            }

        reasoning_paths = self._reasoning_paths(graph)
        return {
            "syndromes": structured["syndromes"],
            "formulas": structured["formulas"],
            "herbs": structured["herbs"],
            "graph": graph,
            "reasoning_paths": reasoning_paths,
            "reason": "基于 entities_relations 完整图谱的症状—证候—方剂—药材路径匹配。",
            "confidence": "local-kg-match",
            "needs_clarification": False,
        }

    def _targeted_symptom_graph(self, symptom_entities: list[Entity]) -> dict:
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        syndrome_hits: dict[str, set[str]] = {}
        syndrome_edges: list[Relation] = []

        for symptom in symptom_entities:
            nodes[symptom.id] = {"id": symptom.id, "label": symptom.name, "type": symptom.type}
            direct_syndrome_count = 0
            for relation in self.outgoing.get(symptom.id, []):
                target = self.entities_by_id.get(relation.target_id)
                if target and target.type == "证候":
                    direct_syndrome_count += 1
                    syndrome_hits.setdefault(target.id, set()).add(symptom.id)
                    syndrome_edges.append(relation)

            if direct_syndrome_count:
                continue

            for anchor, score in self._bridge_symptom_to_linked_symptoms(symptom):
                nodes[anchor.id] = {"id": anchor.id, "label": anchor.name, "type": anchor.type}
                edges.append(
                    {
                        "source": symptom.id,
                        "target": anchor.id,
                        "label": "相近症状",
                        "evidence": f"实体桥接：{symptom.name} 与已有图谱症状 {anchor.name} 名称/别名相近，桥接置信度 {score:.2f}",
                    }
                )
                for relation in self.outgoing.get(anchor.id, []):
                    target = self.entities_by_id.get(relation.target_id)
                    if target and target.type == "证候":
                        syndrome_hits.setdefault(target.id, set()).add(anchor.id)
                        syndrome_edges.append(relation)

        ranked_syndrome_ids = sorted(
            syndrome_hits,
            key=lambda syndrome_id: (len(syndrome_hits[syndrome_id]), self.entities_by_id[syndrome_id].name),
            reverse=True,
        )
        if ranked_syndrome_ids and len(syndrome_hits[ranked_syndrome_ids[0]]) >= 2:
            top_syndrome_ids = [
                syndrome_id
                for syndrome_id in ranked_syndrome_ids
                if len(syndrome_hits[syndrome_id]) >= 2
            ][:3]
        else:
            top_syndrome_ids = ranked_syndrome_ids[:3]

        for syndrome_id in top_syndrome_ids:
            for relation in syndrome_edges:
                if relation.target_id != syndrome_id:
                    continue
                syndrome = self.entities_by_id.get(relation.target_id)
                if not syndrome:
                    continue
                nodes[syndrome.id] = {"id": syndrome.id, "label": syndrome.name, "type": syndrome.type}
                edges.append(
                    {
                        "source": relation.source_id,
                        "target": relation.target_id,
                        "label": relation.relation,
                        "evidence": relation.evidence,
                    }
                )

        formula_ids: list[str] = []
        for syndrome_id in top_syndrome_ids:
            related = [*self.outgoing.get(syndrome_id, []), *self.incoming.get(syndrome_id, [])]
            for relation in related:
                source = self.entities_by_id.get(relation.source_id)
                target = self.entities_by_id.get(relation.target_id)
                if source and target and source.type == "证候" and target.type == "方剂":
                    formula_ids.append(target.id)
                    nodes[target.id] = {"id": target.id, "label": target.name, "type": target.type}
                    edges.append(
                        {
                            "source": relation.source_id,
                            "source_name": relation.source_name,
                            "target": relation.target_id,
                            "target_name": relation.target_name,
                            "label": relation.relation,
                            "evidence": relation.evidence,
                        }
                    )
                elif source and target and source.type == "方剂" and target.type == "证候":
                    formula_ids.append(source.id)
                    nodes[source.id] = {"id": source.id, "label": source.name, "type": source.type}
                    edges.append(
                        {
                            "source": relation.source_id,
                            "target": relation.target_id,
                            "label": relation.relation,
                            "evidence": relation.evidence,
                        }
                    )

        for formula_id in self._unique(formula_ids)[:4]:
            herb_count = 0
            for relation in self.outgoing.get(formula_id, []):
                target = self.entities_by_id.get(relation.target_id)
                if not target or target.type != "药材":
                    continue
                nodes[target.id] = {"id": target.id, "label": target.name, "type": target.type}
                edges.append(
                    {
                        "source": relation.source_id,
                        "target": relation.target_id,
                        "label": relation.relation,
                        "evidence": relation.evidence,
                    }
                )
                herb_count += 1
                if herb_count >= 12:
                    break

        return {"nodes": list(nodes.values()), "edges": edges[:80]}

    def _bridge_symptom_to_linked_symptoms(self, symptom: Entity, limit: int = 3) -> list[tuple[Entity, float]]:
        """Map entity-only symptoms to nearby symptoms that already have KG edges.

        Some imported resources provide symptom entities without direct
        symptom→syndrome/formula relations. Instead of
        leaving those entities dead-ended, bridge fine-grained or synonymous
        symptom names to the closest existing linked symptom, then continue the
        normal graph reasoning through the linked symptom's real relations.
        """
        candidates: list[tuple[Entity, float]] = []
        for candidate in self.entities:
            if candidate.id == symptom.id or candidate.type != "症状":
                continue
            if not any(
                (target := self.entities_by_id.get(relation.target_id)) and target.type == "证候"
                for relation in self.outgoing.get(candidate.id, [])
            ):
                continue

            score = self._symptom_bridge_score(symptom, candidate)
            if score >= 0.78:
                candidates.append((candidate, score))

        candidates.sort(key=lambda item: (item[1], len(item[0].name)), reverse=True)
        return candidates[:limit]

    def _symptom_bridge_score(self, source: Entity, target: Entity) -> float:
        source_terms = self._entity_terms_for_bridge(source)
        target_terms = self._entity_terms_for_bridge(target)
        best = 0.0
        for source_term in source_terms:
            for target_term in target_terms:
                best = max(best, self._term_similarity(source_term, target_term))
        return best

    def _entity_terms_for_bridge(self, entity: Entity) -> list[str]:
        terms = [entity.name, entity.alias]
        # Keep descriptions as weak evidence only for the compact curated graph.
        # Imported descriptions may be too broad for safe relation creation.
        source = ""
        if entity.properties:
            source = str(entity.properties.get("source") or "")
        if not source.lower().startswith("external"):
            terms.extend(
                part.strip()
                for part in re.split(r"[，、；;。\s]+", entity.description or "")
                if 2 <= len(part.strip()) <= 8
            )
        return self._unique([term for term in terms if term])

    @staticmethod
    def _term_similarity(left: str, right: str) -> float:
        left = "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", left))
        right = "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", right))
        if len(left) < 2 or len(right) < 2:
            return 0.0
        if left == right:
            return 1.0
        if left in right or right in left:
            shorter = min(len(left), len(right))
            longer = max(len(left), len(right))
            return 0.88 + 0.08 * (shorter / longer)

        left_chars = set(left)
        right_chars = set(right)
        overlap = len(left_chars & right_chars)
        if overlap < 2:
            return 0.0
        containment = overlap / min(len(left_chars), len(right_chars))
        jaccard = overlap / len(left_chars | right_chars)
        # Require high containment so generic words such as "痛/热/渴" do not
        # create noisy syndrome paths.
        if containment < 0.75:
            return 0.0
        return 0.55 * containment + 0.45 * jaccard

    def _load_entity_sources(self) -> list[Entity]:
        entities_dir = self.graph_repo_root / "entities"
        return self._dedupe_entities_by_id(self._load_entities(entities_dir))

    def _load_relation_sources(self) -> list[Relation]:
        relations_dir = self.graph_repo_root / "relations"
        return self._dedupe_relations(self._load_relations(relations_dir))

    def _load_entities(self, entities_dir: Path) -> list[Entity]:
        entities: list[Entity] = []
        if not entities_dir.exists():
            return entities

        paths = sorted(entities_dir.glob("*.json"))
        # 后台编辑采用同 ID 的补充记录覆盖只读基础数据，因此管理补充文件
        # 必须最后加载。否则按字母顺序它会先于 herb/symptom 等原始文件，
        # 随后的去重逻辑又把用户刚保存的内容覆盖回旧值。
        paths.sort(key=lambda path: path.name == "entities_admin_supplement.json")
        for path in paths:
            for item in self._read_json_items(path, "entities"):
                entities.append(
                    Entity(
                        id=str(item.get("id", "")).strip(),
                        name=str(item.get("name", "")).strip(),
                        type=str(item.get("type", "")).strip(),
                        alias=str(item.get("alias", "")).strip(),
                        description=str(item.get("description", "")).strip(),
                        properties=item.get("properties") or {},
                    )
                )
        return [entity for entity in entities if entity.id and entity.name]

    def _load_relations(self, relations_dir: Path) -> list[Relation]:
        relations: list[Relation] = []
        if not relations_dir.exists():
            return relations

        paths = sorted(relations_dir.glob("*.json"))
        paths.sort(key=lambda path: path.name == "relations_admin_supplement.json")
        for path in paths:
            for item in self._read_json_items(path, "relations"):
                source_id = str(item.get("source_id", "")).strip()
                target_id = str(item.get("target_id", "")).strip()
                if not source_id or not target_id:
                    continue

                source = self.entities_by_id.get(source_id) if hasattr(self, "entities_by_id") else None
                target = self.entities_by_id.get(target_id) if hasattr(self, "entities_by_id") else None
                relations.append(
                    Relation(
                        source_id=source_id,
                        source_name=str(item.get("source_name") or (source.name if source else "")).strip(),
                        relation=str(item.get("relation", "")).strip(),
                        target_id=target_id,
                        target_name=str(item.get("target_name") or (target.name if target else "")).strip(),
                        evidence=str(item.get("evidence", "")).strip(),
                        source_type=str(item.get("source_type") or (source.type if source else "")).strip(),
                        target_type=str(item.get("target_type") or (target.type if target else "")).strip(),
                    )
                )
        return relations

    @staticmethod
    def _dedupe_entities_by_id(entities: list[Entity]) -> list[Entity]:
        by_id: dict[str, Entity] = {}
        order: list[str] = []
        for entity in entities:
            if entity.id not in by_id:
                order.append(entity.id)
            by_id[entity.id] = entity
        return [by_id[entity_id] for entity_id in order]

    @staticmethod
    def _dedupe_relations(relations: list[Relation]) -> list[Relation]:
        by_key: dict[tuple[str, str, str], Relation] = {}
        order: list[tuple[str, str, str]] = []
        for relation in relations:
            key = (relation.source_id, relation.relation, relation.target_id)
            if key not in by_key:
                order.append(key)
            by_key[key] = relation
        return [by_key[key] for key in order]

    @staticmethod
    def _read_json_items(path: Path, key: str) -> list[dict]:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict) and isinstance(data.get(key), list):
            return [item for item in data[key] if isinstance(item, dict)]
        return []

    @staticmethod
    def _build_name_index(entities: list[Entity]) -> dict[str, list[Entity]]:
        index: dict[str, list[Entity]] = {}
        for entity in entities:
            for name in [entity.name, entity.alias]:
                name = name.strip()
                if name:
                    index.setdefault(name, []).append(entity)
        return index

    @staticmethod
    def _build_outgoing(relations: list[Relation]) -> dict[str, list[Relation]]:
        outgoing: dict[str, list[Relation]] = {}
        for relation in relations:
            outgoing.setdefault(relation.source_id, []).append(relation)
        return outgoing

    @staticmethod
    def _build_incoming(relations: list[Relation]) -> dict[str, list[Relation]]:
        incoming: dict[str, list[Relation]] = {}
        for relation in relations:
            incoming.setdefault(relation.target_id, []).append(relation)
        return incoming

    def _load_text_chunks(self) -> list[TextChunk]:
        chunks: list[TextChunk] = []

        for path in [
            self.member3_root / "data" / "processed" / "rag_corpus_clean.jsonl",
            self.member3_root / "data" / "samples" / "rag_corpus_sample.jsonl",
        ]:
            chunks.extend(self._read_jsonl_chunks(path))

        docs_dir = self.member3_root / "data" / "docs"
        if docs_dir.exists():
            for path in sorted(docs_dir.glob("*.txt")):
                chunks.append(
                    TextChunk(
                        title=path.stem,
                        source="member3/docs",
                        content=path.read_text(encoding="utf-8-sig").strip(),
                    )
                )

        for entity in self.entities:
            note = ""
            if entity.properties:
                note = str(entity.properties.get("note") or "")
            content = "；".join(part for part in [entity.description, note] if part)
            if content:
                chunks.append(TextChunk(title=entity.name, source=f"图谱实体/{entity.type}", content=content))

        return chunks

    @staticmethod
    def _read_jsonl_chunks(path: Path) -> list[TextChunk]:
        if not path.exists():
            return []

        chunks: list[TextChunk] = []
        with path.open("r", encoding="utf-8-sig") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = str(item.get("content", "")).strip()
                if not content:
                    continue
                chunks.append(
                    TextChunk(
                        title=str(item.get("title") or item.get("chunk_id") or "RAG片段"),
                        source=str(item.get("source") or "RAG语料"),
                        content=content[:900],
                    )
                )
        return chunks

    def _match_entities(self, text: str) -> list[Entity]:
        normalized_text = text.strip()
        if not normalized_text:
            return []

        candidates: list[tuple[int, int, int, Entity]] = []
        for entity in self.entities:
            names = [entity.name, entity.alias]
            for name in names:
                if not name:
                    continue
                start = normalized_text.find(name)
                if start >= 0:
                    candidates.append((start, start + len(name), len(name), entity))
                    break

        candidates.sort(key=lambda item: (item[2], item[0]), reverse=True)
        selected: list[tuple[int, int, Entity]] = []
        for start, end, _, entity in candidates:
            if any(start >= kept_start and end <= kept_end for kept_start, kept_end, _ in selected):
                continue
            selected.append((start, end, entity))
        selected.sort(key=lambda item: item[0])

        return self._unique_entities([entity for _, _, entity in selected])

    def _find_entities_by_name(self, name: str) -> list[Entity]:
        name = name.strip()
        if not name:
            return []
        if name in self.entities_by_name:
            return self.entities_by_name[name]
        return [
            entity
            for entity in self.entities
            if entity.name in name or name in entity.name or (entity.alias and entity.alias in name)
        ]

    def _expand_graph(self, seed_entities: list[Entity], max_hops: int = 2) -> dict:
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        seen_edges: set[tuple[str, str, str]] = set()
        frontier = [(entity.id, 0) for entity in self._unique_entities(seed_entities)]
        visited_depth: dict[str, int] = {}

        for entity in seed_entities:
            nodes[entity.id] = {"id": entity.id, "label": entity.name, "type": entity.type}

        seed_ids = {entity.id for entity in seed_entities}

        while frontier:
            entity_id, depth = frontier.pop(0)
            if depth > max_hops:
                continue
            if entity_id in visited_depth and visited_depth[entity_id] <= depth:
                continue
            visited_depth[entity_id] = depth

            current_entity = self.entities_by_id.get(entity_id)
            relations = self._relations_for_expansion(
                entity_id=entity_id,
                entity_type=current_entity.type if current_entity else "",
                depth=depth,
                seed_ids=seed_ids,
            )
            for relation in relations:
                for node_id in [relation.source_id, relation.target_id]:
                    entity = self.entities_by_id.get(node_id)
                    if entity:
                        nodes[node_id] = {"id": entity.id, "label": entity.name, "type": entity.type}

                edge_key = (relation.source_id, relation.relation, relation.target_id)
                if edge_key not in seen_edges:
                    edges.append(
                        {
                            "source": relation.source_id,
                            "target": relation.target_id,
                            "label": relation.relation,
                            "evidence": relation.evidence,
                        }
                    )
                    seen_edges.add(edge_key)

                if depth + 1 <= max_hops:
                    for next_id in [relation.source_id, relation.target_id]:
                        next_entity = self.entities_by_id.get(next_id)
                        if not next_entity:
                            continue
                        if self._can_expand_next(next_entity, seed_ids):
                            frontier.append((next_id, depth + 1))

        return {"nodes": list(nodes.values()), "edges": edges[:120]}

    def _relations_for_expansion(
        self,
        entity_id: str,
        entity_type: str,
        depth: int,
        seed_ids: set[str],
    ) -> list[Relation]:
        outgoing = self.outgoing.get(entity_id, [])
        incoming = self.incoming.get(entity_id, [])

        if entity_type == "症状":
            return [
                relation
                for relation in outgoing
                if self.entities_by_id.get(relation.target_id, Entity("", "", "")).type == "证候"
            ]

        if entity_type == "证候":
            return [
                relation
                for relation in [*outgoing, *incoming]
                if (
                    self.entities_by_id.get(relation.source_id, Entity("", "", "")).type in {"症状", "方剂"}
                    or self.entities_by_id.get(relation.target_id, Entity("", "", "")).type in {"方剂"}
                )
            ]

        if entity_type == "方剂":
            return [
                relation
                for relation in [*outgoing, *incoming]
                if (
                    self.entities_by_id.get(relation.target_id, Entity("", "", "")).type in {"药材", "证候", "文献"}
                    or self.entities_by_id.get(relation.source_id, Entity("", "", "")).type == "证候"
                )
            ]

        if entity_type == "药材":
            relations = [
                relation
                for relation in outgoing
                if self.entities_by_id.get(relation.target_id, Entity("", "", "")).type in {"功效", "禁忌", "文献"}
            ]
            if entity_id in seed_ids and depth == 0:
                relations.extend(
                    relation
                    for relation in incoming
                    if self.entities_by_id.get(relation.source_id, Entity("", "", "")).type == "方剂"
                )
            return relations

        return outgoing

    def _select_relevant_chunks(
        self,
        query: str,
        chunks: list[TextChunk],
        intent: str,
        top_k: int,
    ) -> list[TextChunk]:
        """Intent-aware text evidence selection, adapted for local TextChunk."""
        if not chunks:
            return []

        hint = self._extract_query_hint(query)
        query_terms = [term for term in [hint, *self._extract_query_entities(query)] if term and len(term) >= 2]

        if intent == "formula_composition":
            direct_composition_patterns = [
                r"药物组成\s*[:：]",
                r"组成\s*[:：]",
                r"处方组成\s*[:：]",
                r"方药组成\s*[:：]",
                r"本方由[^。；\n]{0,80}组成",
                r"由[^。；\n]{0,80}组成",
                r"(?:含有|包含)[^。；\n]{0,30}(?:药材|药味|药物)",
                r"(?:药材|药味|药物)[^。；\n]{0,30}(?:包括|包含|有)",
                r"方中[^。；\n]{0,80}(?:药|味)",
            ]
            selected = []
            for chunk in chunks:
                text = f"{chunk.title}\n{chunk.content}"
                has_target = any(term in text for term in query_terms)
                has_direct_composition = any(re.search(pattern, text) for pattern in direct_composition_patterns)
                if has_target and has_direct_composition:
                    selected.append(chunk)
            return selected[:top_k]

        if intent == "mechanism_explanation":
            mechanism_terms = [
                *query_terms,
                "反佐",
                "配伍",
                "格拒",
                "同气相求",
                "反从其病",
                "辛热太过",
                "佐制",
                "相须",
                "相使",
            ]
            scored: list[tuple[float, TextChunk]] = []
            for chunk in chunks:
                text = f"{chunk.title}\n{chunk.content}"
                score = float(chunk.score) * 0.01
                for term in mechanism_terms:
                    if term and term in text:
                        score += 2.0
                for strong in ["反佐", "格拒", "同气相求", "辛热太过", "配伍"]:
                    if strong in text:
                        score += 2.0
                if score >= 3.0:
                    scored.append((score, chunk))
            scored.sort(key=lambda item: item[0], reverse=True)
            return [chunk for _, chunk in scored[:top_k]]

        if intent == "syndrome_manifestation":
            title_matches = [chunk for chunk in chunks if any(term in chunk.title for term in query_terms)]
            if title_matches:
                return title_matches[:top_k]
            content_matches = [chunk for chunk in chunks if any(term in chunk.content for term in query_terms)]
            if content_matches:
                return content_matches[:top_k]
            return chunks[:top_k]

        if intent == "symptom_to_formula":
            selected = [
                chunk
                for chunk in chunks
                if any(term in f"{chunk.title}\n{chunk.content}" for term in query_terms)
            ]
            return (selected or chunks)[:top_k]

        if query_terms:
            title_matches = [chunk for chunk in chunks if any(term in chunk.title for term in query_terms)]
            if title_matches:
                return title_matches[:top_k]
            content_matches = [chunk for chunk in chunks if any(term in chunk.content for term in query_terms)]
            if content_matches:
                return content_matches[:top_k]

        return chunks[:top_k]

    @staticmethod
    def _node_by_id(graph: dict, node_id: str) -> dict | None:
        for node in graph.get("nodes", []):
            if node.get("id") == node_id:
                return node
        return None

    def _subgraph_from_edges(self, graph: dict, edges: list[dict]) -> dict:
        used_node_ids: set[str] = set()
        for edge in edges:
            used_node_ids.add(edge.get("source", ""))
            used_node_ids.add(edge.get("target", ""))
        nodes = [node for node in graph.get("nodes", []) if node.get("id") in used_node_ids]
        return {"nodes": nodes, "edges": edges}

    def _prune_graph_by_intent(self, query: str, intent: str, graph: dict) -> dict:
        """Keep only graph edges that can answer the detected intent."""
        if not graph.get("edges"):
            return {"nodes": graph.get("nodes", []), "edges": []}

        allowed_edges: list[dict] = []
        query_text = query.strip().lower()

        if self._is_cough_clear_phlegm_query(query):
            syndrome_names = {"风寒表证", "外感风寒", "寒痰", "痰湿内阻", "肺气不足", "肺寒"}
            symptom_names = {"咳嗽", "痰白清稀", "痰多", "胸闷", "舌苔腻"}
            relation_names = {"常见证候", "提示", "表现", "症状", "包含", "来源于"}
            for edge in graph.get("edges", []):
                source = self._node_by_id(graph, edge.get("source", ""))
                target = self._node_by_id(graph, edge.get("target", ""))
                if not source or not target:
                    continue
                source_label = str(source.get("label", ""))
                target_label = str(target.get("label", ""))
                relation = str(edge.get("label", ""))
                if relation not in relation_names:
                    continue

                source_is_symptom = source_label in symptom_names and source.get("type") == "症状"
                target_is_syndrome = target_label in syndrome_names and target.get("type") == "证候"
                syndrome_to_symptom = source_label in syndrome_names and target_label in symptom_names
                source_relation = relation == "来源于" and source_label in {*symptom_names, *syndrome_names}
                if (source_is_symptom and target_is_syndrome) or syndrome_to_symptom or source_relation:
                    allowed_edges.append(edge)
            return self._subgraph_from_edges(graph, allowed_edges)

        formula_entities = [
            entity for entity in self._match_entities(query)
            if entity.type == "方剂" and entity.name in query
        ]
        if formula_entities and any(marker in query for marker in ["组成", "功效", "主治", "适用", "证候", "依据", "来源", "是什么"]):
            formula_ids = {entity.id for entity in formula_entities}
            syndrome_ids: set[str] = set()
            relation_names = {"包含", "组成", "配伍", "主治", "功效", "具有", "来源于", "禁忌", "慎用", "注意"}
            for edge in graph.get("edges", []):
                source = self._node_by_id(graph, edge.get("source", ""))
                target = self._node_by_id(graph, edge.get("target", ""))
                if not source or not target:
                    continue
                relation = str(edge.get("label", ""))
                if relation not in relation_names:
                    continue
                source_is_formula = source.get("id") in formula_ids
                target_is_formula = target.get("id") in formula_ids
                target_type = str(target.get("type", ""))
                source_type = str(source.get("type", ""))
                if source_is_formula and target_type in {"药材", "证候", "功效", "文献", "禁忌"}:
                    allowed_edges.append(edge)
                    if target_type == "证候":
                        syndrome_ids.add(str(target.get("id")))
                elif target_is_formula and source_type == "证候":
                    allowed_edges.append(edge)
                    syndrome_ids.add(str(source.get("id")))

            for edge in graph.get("edges", []):
                source = self._node_by_id(graph, edge.get("source", ""))
                target = self._node_by_id(graph, edge.get("target", ""))
                if not source or not target:
                    continue
                if (
                    str(target.get("id")) in syndrome_ids
                    and source.get("type") == "症状"
                    and edge.get("label") in {"提示", "表现", "症状"}
                ):
                    allowed_edges.append(edge)
            return self._subgraph_from_edges(graph, allowed_edges)

        if intent == "formula_composition":
            for edge in graph.get("edges", []):
                source = self._node_by_id(graph, edge.get("source", ""))
                target = self._node_by_id(graph, edge.get("target", ""))
                if not source or not target:
                    continue
                if (
                    source.get("type") == "方剂"
                    and target.get("type") == "药材"
                    and source.get("label", "").lower() in query_text
                    and edge.get("label") in {"包含", "组成", "配伍"}
                ):
                    allowed_edges.append(edge)
            return self._subgraph_from_edges(graph, allowed_edges)

        if intent == "symptom_to_formula":
            syndrome_support: dict[str, set[str]] = {}
            syndrome_formula_edges: list[dict] = []
            formula_syndrome_edges: list[dict] = []

            for edge in graph.get("edges", []):
                source = self._node_by_id(graph, edge.get("source", ""))
                target = self._node_by_id(graph, edge.get("target", ""))
                if not source or not target:
                    continue
                source_label = str(source.get("label", ""))
                target_label = str(target.get("label", ""))
                source_is_asked_symptom = (
                    source.get("type") == "症状"
                    and source_label
                    and (source_label in query or self._term_similarity(source_label, query) >= 0.72)
                )
                keep_symptom_to_syndrome = (
                    source_is_asked_symptom
                    and target.get("type") == "证候"
                    and edge.get("label") in {"提示", "主治"}
                )
                keep_syndrome_to_formula = (
                    source.get("type") == "证候"
                    and target.get("type") == "方剂"
                    and edge.get("label") in {"对应", "主治", "推荐"}
                )
                keep_formula_to_syndrome = (
                    source.get("type") == "方剂"
                    and target.get("type") == "证候"
                    and edge.get("label") in {"对应", "主治", "治疗"}
                )
                if keep_symptom_to_syndrome:
                    syndrome_support.setdefault(str(target.get("id")), set()).add(str(source.get("id")))
                    allowed_edges.append(edge)
                elif keep_syndrome_to_formula:
                    syndrome_formula_edges.append(edge)
                elif keep_formula_to_syndrome:
                    formula_syndrome_edges.append(edge)

            if syndrome_support:
                ranked_syndrome_ids = sorted(
                    syndrome_support,
                    key=lambda syndrome_id: (
                        len(syndrome_support[syndrome_id]),
                        str(self._node_by_id(graph, syndrome_id).get("label", "") if self._node_by_id(graph, syndrome_id) else ""),
                    ),
                    reverse=True,
                )
                if len(syndrome_support[ranked_syndrome_ids[0]]) >= 2:
                    kept_syndrome_ids = {
                        syndrome_id
                        for syndrome_id in ranked_syndrome_ids
                        if len(syndrome_support[syndrome_id]) >= 2
                    }
                else:
                    kept_syndrome_ids = set(ranked_syndrome_ids[:3])

                allowed_edges = [
                    edge
                    for edge in allowed_edges
                    if edge.get("target") in kept_syndrome_ids
                ]
                for edge in syndrome_formula_edges:
                    if edge.get("source") in kept_syndrome_ids:
                        allowed_edges.append(edge)
                for edge in formula_syndrome_edges:
                    if edge.get("target") in kept_syndrome_ids:
                        allowed_edges.append(edge)
            return self._subgraph_from_edges(graph, allowed_edges)

        if intent == "syndrome_manifestation":
            target_syndrome_names = {
                entity.name
                for entity in self._match_entities(query)
                if entity.type == "证候"
            }
            for edge in graph.get("edges", []):
                source = self._node_by_id(graph, edge.get("source", ""))
                target = self._node_by_id(graph, edge.get("target", ""))
                if not source or not target:
                    continue
                source_label = str(source.get("label", ""))
                target_label = str(target.get("label", ""))
                source_is_target_syndrome = source.get("type") == "证候" and (
                    not target_syndrome_names or source_label in target_syndrome_names or source_label in query
                )
                target_is_target_syndrome = target.get("type") == "证候" and (
                    not target_syndrome_names or target_label in target_syndrome_names or target_label in query
                )
                syndrome_to_symptom = (
                    source_is_target_syndrome
                    and target.get("type") == "症状"
                    and edge.get("label") in {"表现", "症状", "包含", "提示"}
                )
                symptom_to_syndrome = (
                    source.get("type") == "症状"
                    and target_is_target_syndrome
                    and edge.get("label") in {"提示", "主治"}
                )
                if syndrome_to_symptom or symptom_to_syndrome:
                    allowed_edges.append(edge)
            return self._subgraph_from_edges(graph, allowed_edges)

        if intent == "mechanism_explanation":
            mechanism_keywords = ["反佐", "配伍", "制约", "佐制", "相须", "相使", "相畏", "相杀", "机制", "原因", "原理"]
            for edge in graph.get("edges", []):
                text = f"{edge.get('label', '')} {edge.get('evidence', '')}"
                if any(keyword in text for keyword in mechanism_keywords):
                    allowed_edges.append(edge)
            return self._subgraph_from_edges(graph, allowed_edges)

        if intent == "effect_query":
            for edge in graph.get("edges", []):
                target = self._node_by_id(graph, edge.get("target", ""))
                if target and target.get("type") == "功效" and edge.get("label") in {"具有", "功效", "主治"}:
                    allowed_edges.append(edge)
            return self._subgraph_from_edges(graph, allowed_edges)

        if intent == "contraindication_query":
            for edge in graph.get("edges", []):
                target = self._node_by_id(graph, edge.get("target", ""))
                if target and target.get("type") == "禁忌" and edge.get("label") in {"禁忌", "慎用", "注意"}:
                    allowed_edges.append(edge)
            return self._subgraph_from_edges(graph, allowed_edges)

        return graph

    @staticmethod
    def _can_expand_next(entity: Entity, seed_ids: set[str]) -> bool:
        if entity.id in seed_ids:
            return True
        return entity.type in {"证候", "方剂"}

    def _structured_from_graph(self, graph: dict) -> dict:
        id_to_node = {node["id"]: node for node in graph.get("nodes", [])}
        syndromes: list[str] = []
        formulas: list[str] = []
        herbs: list[str] = []

        for edge in graph.get("edges", []):
            source = id_to_node.get(edge["source"])
            target = id_to_node.get(edge["target"])
            if not source or not target:
                continue

            if target.get("type") == "证候" and edge.get("label") in {"提示", "主治", "常见证候"}:
                syndromes.append(target["label"])
            if source.get("type") == "证候" and target.get("type") == "方剂":
                formulas.append(target["label"])
            if source.get("type") == "方剂" and target.get("type") == "证候":
                syndromes.append(target["label"])
                formulas.append(source["label"])
            if source.get("type") == "方剂" and target.get("type") == "药材":
                formulas.append(source["label"])
                herbs.append(target["label"])

        return {
            "syndromes": self._unique(syndromes),
            "formulas": self._unique(formulas),
            "herbs": self._unique(herbs),
        }

    @staticmethod
    def _filter_structured_by_intent(intent: str, structured: dict) -> dict:
        allowed_fields_by_intent = {
            "formula_composition": {"formulas", "herbs"},
            "syndrome_manifestation": {"syndromes"},
            "symptom_to_formula": {"syndromes", "formulas"},
            "mechanism_explanation": {"formulas", "herbs"},
            "effect_query": {"formulas", "herbs"},
            "contraindication_query": {"formulas", "herbs"},
            "definition_query": {"syndromes", "formulas", "herbs"},
            "general": {"syndromes", "formulas", "herbs"},
        }
        allowed = allowed_fields_by_intent.get(intent, {"syndromes", "formulas", "herbs"})
        return {
            "syndromes": structured.get("syndromes", []) if "syndromes" in allowed else [],
            "formulas": structured.get("formulas", []) if "formulas" in allowed else [],
            "herbs": structured.get("herbs", []) if "herbs" in allowed else [],
        }

    def _rank_chunks(self, query: str, priority_terms: list[str] | None = None) -> list[TextChunk]:
        terms = self._query_terms(query)
        priority_terms = [term.lower() for term in (priority_terms or []) if term.strip()]
        ranked: list[TextChunk] = []

        for chunk in self.text_chunks:
            haystack = f"{chunk.title} {chunk.content}".lower()
            score = 0.0
            for term in terms:
                if not term:
                    continue
                if term in chunk.title.lower():
                    score += 6.0
                if term in haystack:
                    score += 1.0 + min(haystack.count(term), 5) * 0.25
            for term in priority_terms:
                if term in chunk.title.lower():
                    score += 20.0
                elif term in haystack:
                    score += 8.0
            if score > 0:
                ranked.append(TextChunk(title=chunk.title, source=chunk.source, content=chunk.content, score=score))

        return sorted(ranked, key=lambda item: item.score, reverse=True)

    @staticmethod
    def _query_terms(text: str) -> list[str]:
        terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]+", text.lower())
        chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
        bigrams = [chinese[index : index + 2] for index in range(max(0, len(chinese) - 1))]
        return list(dict.fromkeys([*terms, *bigrams]))

    @staticmethod
    def _is_cough_clear_phlegm_query(query: str) -> bool:
        text = query.strip()
        return "咳" in text and any(
            keyword in text
            for keyword in ["痰白清稀", "痰白", "白痰", "清稀", "痰清", "咳痰色白", "痰稀"]
        )

    def _is_formula_profile_query(self, query: str) -> bool:
        has_formula = any(entity.type == "方剂" and entity.name in query for entity in self._match_entities(query))
        return has_formula and any(marker in query for marker in ["组成", "功效", "主治", "适用", "证候", "依据", "来源", "是什么"])

    def _is_symptom_analysis_query(self, query: str, structured: dict | None = None) -> bool:
        markers = ["哪些证候", "证候角度", "从哪些", "如何分析", "怎么分析", "相关知识", "辨证", "整理可能"]
        if not any(marker in query for marker in markers):
            return False
        has_symptom = any(entity.type == "症状" and entity.name in query for entity in self._match_entities(query))
        has_syndrome = bool((structured or {}).get("syndromes"))
        return has_symptom or has_syndrome

    def _needs_expanded_evidence(self, query: str) -> bool:
        return self._is_cough_clear_phlegm_query(query) or self._is_formula_profile_query(query) or self._is_symptom_analysis_query(query)

    def _graph_evidence(self, graph: dict, query: str = "") -> list[dict]:
        id_to_node = {node["id"]: node for node in graph.get("nodes", [])}
        evidence = []
        if self._is_cough_clear_phlegm_query(query):
            preferred_entities = ["咳嗽", "痰白清稀", "风寒表证", "痰湿内阻", "寒痰", "肺气不足"]
            entity_rank = {name: index for index, name in enumerate(preferred_entities)}
            seen_entity_labels: set[str] = set()
            entity_nodes = sorted(
                [
                    node
                    for node in graph.get("nodes", [])
                    if node.get("label") in entity_rank
                    and (entity := self.entities_by_id.get(str(node.get("id"))))
                    and entity.description
                ],
                key=lambda node: entity_rank.get(str(node.get("label")), 99),
            )
            for node in entity_nodes:
                entity = self.entities_by_id.get(str(node.get("id")))
                if not entity:
                    continue
                if entity.name in seen_entity_labels:
                    continue
                seen_entity_labels.add(entity.name)
                evidence.append(
                    {
                        "title": entity.name,
                        "source": f"图谱实体/{entity.type}",
                        "content": entity.description,
                        "score": 1.0,
                    }
                )

            preferred_edges = [
                ("咳嗽", "提示", "风寒表证"),
                ("咳嗽", "常见证候", "风寒表证"),
                ("咳嗽", "提示", "痰湿内阻"),
                ("痰白清稀", "提示", "寒痰"),
                ("痰白清稀", "提示", "肺寒"),
                ("咳嗽", "常见证候", "肺气不足"),
            ]
            edge_rank = {item: index for index, item in enumerate(preferred_edges)}
            ranked_edges = sorted(
                graph.get("edges", []),
                key=lambda edge: edge_rank.get(
                    (
                        str(id_to_node.get(edge.get("source"), {}).get("label", "")),
                        str(edge.get("label", "")),
                        str(id_to_node.get(edge.get("target"), {}).get("label", "")),
                    ),
                    99,
                ),
            )
        else:
            if self._is_formula_profile_query(query):
                formula_names = {
                    entity.name for entity in self._match_entities(query)
                    if entity.type == "方剂" and entity.name in query
                }
                formula_nodes = [
                    node for node in graph.get("nodes", [])
                    if node.get("label") in formula_names
                    and (entity := self.entities_by_id.get(str(node.get("id"))))
                    and entity.description
                ]
                for node in formula_nodes:
                    entity = self.entities_by_id.get(str(node.get("id")))
                    if entity:
                        evidence.append(
                            {
                                "title": entity.name,
                                "source": f"图谱实体/{entity.type}",
                                "content": entity.description,
                                "score": 1.0,
                            }
                        )
                formula_edges = [
                    edge for edge in graph.get("edges", [])
                    if id_to_node.get(edge.get("source"), {}).get("label") in formula_names
                ]
                composition_edges = [edge for edge in formula_edges if edge.get("label") in {"包含", "组成", "配伍"}]
                treatment_edges = [edge for edge in formula_edges if edge.get("label") in {"主治", "对应", "治疗"}]
                source_edges = [edge for edge in formula_edges if edge.get("label") == "来源于"]
                caution_edges = [edge for edge in formula_edges if edge.get("label") in {"禁忌", "慎用", "注意"}]
                other_edges = [
                    edge for edge in graph.get("edges", [])
                    if edge not in [*composition_edges, *treatment_edges, *source_edges, *caution_edges]
                ]
                ranked_edges = [
                    *composition_edges[:4],
                    *treatment_edges[:3],
                    *source_edges[:2],
                    *caution_edges[:2],
                    *composition_edges[4:],
                    *other_edges,
                ]
            else:
                ranked_edges = graph.get("edges", [])[:3]
            if self._is_symptom_analysis_query(query):
                id_to_node = {node["id"]: node for node in graph.get("nodes", [])}
                syndrome_names = self._compact_syndrome_names(
                    [
                        str(id_to_node.get(edge.get("target"), {}).get("label", ""))
                        for edge in graph.get("edges", [])
                        if id_to_node.get(edge.get("target"), {}).get("type") == "证候"
                    ],
                    graph,
                    limit=5,
                )
                for name in syndrome_names:
                    description = self._entity_description(name, "证候", limit=90)
                    if description:
                        evidence.append(
                            {
                                "title": name,
                                "source": "图谱实体/证候",
                                "content": description,
                                "score": 1.0,
                            }
                        )
                ranked_edges = sorted(
                    graph.get("edges", []),
                    key=lambda edge: (
                        0 if id_to_node.get(edge.get("source"), {}).get("type") == "症状"
                        and id_to_node.get(edge.get("target"), {}).get("type") == "证候"
                        and edge.get("label") in {"提示", "常见证候"} else 1,
                        0 if str(id_to_node.get(edge.get("source"), {}).get("label", "")) in query else 1,
                        str(id_to_node.get(edge.get("source"), {}).get("label", "")),
                    ),
                )

        edge_limit = 8 if self._needs_expanded_evidence(query) else 3
        for edge in ranked_edges[:edge_limit]:
            source = id_to_node.get(edge["source"], {}).get("label", edge["source"])
            target = id_to_node.get(edge["target"], {}).get("label", edge["target"])
            evidence.append(
                {
                    "title": f"{source} —{edge['label']}→ {target}",
                    "source": edge.get("evidence") or "entities_relations 图谱",
                    "content": f"知识图谱关系：{source} —{edge['label']}→ {target}",
                    "score": 1.0,
                }
            )
        return evidence

    def _entity_description(self, name: str, entity_type: str | None = None, limit: int = 46) -> str:
        for entity in self._find_entities_by_name(name):
            if entity_type and entity.type != entity_type:
                continue
            description = re.split(r"[。；;]", entity.description or "")[0].strip()
            if not description:
                continue
            return description[:limit] + ("..." if len(description) > limit else "")
        return ""

    def _names_from_graph_edges(
        self,
        graph: dict,
        *,
        source_name: str | None = None,
        relation_names: set[str] | None = None,
        target_type: str | None = None,
        source_type: str | None = None,
    ) -> list[str]:
        id_to_node = {node["id"]: node for node in graph.get("nodes", [])}
        names: list[str] = []
        for edge in graph.get("edges", []):
            source = id_to_node.get(edge.get("source"))
            target = id_to_node.get(edge.get("target"))
            if not source or not target:
                continue
            if source_name and source.get("label") != source_name:
                continue
            if relation_names and edge.get("label") not in relation_names:
                continue
            if source_type and source.get("type") != source_type:
                continue
            if target_type and target.get("type") != target_type:
                continue
            names.append(str(target.get("label", "")))
        return self._unique(names)

    def _compact_syndrome_names(self, names: list[str], graph: dict, limit: int = 4) -> list[str]:
        noisy = {"实热", "阴虚证", "阳虚证", "气虚证", "血虚证", "血瘀证"}
        relation_order: list[str] = []
        id_to_node = {node["id"]: node for node in graph.get("nodes", [])}
        for edge in graph.get("edges", []):
            target = id_to_node.get(edge.get("target"))
            if target and target.get("type") == "证候":
                relation_order.append(str(target.get("label", "")))
        ordered = self._unique([name for name in [*relation_order, *names] if name])
        preferred = [name for name in ordered if name not in noisy]
        return (preferred or ordered)[:limit]

    def _natural_formula_answer(self, query: str, graph: dict) -> str:
        formula_entities = [
            entity for entity in self._match_entities(query)
            if entity.type == "方剂" and entity.name in query
        ]
        if not formula_entities:
            return ""
        formula_name = formula_entities[0].name
        herbs = self._names_from_graph_edges(
            graph, source_name=formula_name, relation_names={"包含", "组成", "配伍"}, target_type="药材"
        )
        syndromes = self._names_from_graph_edges(
            graph, source_name=formula_name, relation_names={"主治", "对应", "治疗"}, target_type="证候"
        )
        effect = self._entity_description(formula_name, "方剂", limit=36)

        parts: list[str] = []
        if herbs:
            parts.append(f"{formula_name}的组成在当前图谱中可核到{ '、'.join(herbs[:8]) }。")
        else:
            parts.append(f"关于{formula_name}，当前资料更适合作为方剂知识查询来理解。")
        if effect:
            parts.append(f"方剂说明中将其核心功效概括为{effect}。")
        if syndromes:
            syndrome_text = "、".join(syndromes[:3])
            parts.append(f"适用证候方面，可先围绕{syndrome_text}等方向核对。")
            descriptions = [
                f"{name}多见{name_desc}"
                for name in syndromes[:2]
                if (name_desc := self._entity_description(name, "证候", limit=34))
            ]
            if descriptions:
                parts.append("进一步看，" + "；".join(descriptions) + "。")
        parts.append("下方依据中保留了对应的方剂实体、组成关系、主治路径和资料来源，便于回溯核对；具体使用仍需结合完整辨证，不作为个人用药建议。")
        return "".join(parts)

    def _natural_symptom_answer(self, query: str, graph: dict, structured: dict) -> str:
        syndromes = self._compact_syndrome_names(structured.get("syndromes", []), graph, limit=4)
        formulas = self._unique(structured.get("formulas", []))[:4]
        if not syndromes:
            return ""

        sleep_query = any(term in query for term in ["失眠", "不寐", "多梦", "入睡困难", "易醒"])
        syndrome_text = "、".join(syndromes)
        if sleep_query:
            parts = [
                f"失眠多梦这类问题，中医通常会先看心神是否失养、心肾是否协调，以及是否存在痰热或虚烦等扰动。"
                f"常见的分析方向包括{syndrome_text}。"
            ]
        else:
            parts = [f"从这些表现看，辨证时可以先抓住{syndrome_text}这几条线索。"]

        descriptions = []
        for name in syndromes[:3]:
            desc = self._entity_description(name, "证候", limit=42)
            if not desc:
                continue
            if sleep_query:
                descriptions.append(f"{name}多与{desc}有关")
            else:
                descriptions.append(f"{name}常见线索是{desc}")
        if descriptions:
            parts.append("其中，" + "；".join(descriptions) + "。")
        if formulas:
            parts.append(f"常见方剂可以关注{ '、'.join(formulas) }，但它们分别适合哪一类证候，还要看兼症、舌象和脉象是否相符。")
        parts.append("这里只能作为知识学习和辨证思路参考，不能替代四诊合参；如果要继续细分，还需要补充病程、舌象、脉象以及是否伴有心悸、乏力、口苦、盗汗等表现。")
        return "".join(parts)

    @staticmethod
    def _dedupe_evidence(items: list[dict]) -> list[dict]:
        seen: set[tuple[str, str]] = set()
        result: list[dict] = []
        for item in items:
            key = (str(item.get("title", "")), str(item.get("content", ""))[:80])
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def _reasoning_paths(self, graph: dict) -> list[str]:
        id_to_node = {node["id"]: node for node in graph.get("nodes", [])}
        paths = []
        for edge in graph.get("edges", [])[:12]:
            source = id_to_node.get(edge["source"], {}).get("label", edge["source"])
            target = id_to_node.get(edge["target"], {}).get("label", edge["target"])
            paths.append(f"{source} --{edge['label']}--> {target}")
        return paths

    def _build_answer(self, query: str, evidence: list[dict], graph: dict, structured: dict, intent: str) -> str:
        if self._is_cough_clear_phlegm_query(query):
            return (
                "咳嗽伴痰白清稀时，中医通常会优先从偏寒、痰湿和肺气宣降失常的角度理解。"
                "若同时有恶寒、发热、无汗、头身疼痛等表现，更接近外感风寒或风寒表证；"
                "若痰量较多、胸闷、苔白腻，则可从寒痰或痰湿内阻方向分析；"
                "若咳嗽反复、气短乏力，则需要进一步核对肺气不足。"
                "这里的判断只是知识学习和辨证线索，仍需结合舌象、脉象、病程和伴随症状综合分析。"
            )

        if self._is_formula_profile_query(query):
            formula_answer = self._natural_formula_answer(query, graph)
            if formula_answer:
                return formula_answer

        if self._is_symptom_analysis_query(query, structured):
            symptom_answer = self._natural_symptom_answer(query, graph, structured)
            if symptom_answer:
                return symptom_answer

        if intent == "formula_composition" and structured.get("formulas") and structured.get("herbs"):
            return (
                f"{structured['formulas'][0]}包含的药材包括{'、'.join(structured['herbs'][:12])}。"
                "下方依据保留了对应的组成关系和来源，可展开核对。"
            )

        if intent == "symptom_to_formula" and (structured.get("syndromes") or structured.get("formulas")):
            parts = [f"围绕“{query}”，可以先把症状与证候关系理清，再看是否存在相应方剂路径。"]
            if structured.get("syndromes"):
                parts.append("当前图谱中较相关的证候包括" + "、".join(structured["syndromes"][:4]) + "。")
            if structured.get("formulas"):
                parts.append("可进一步查看" + "、".join(structured["formulas"][:5]) + "等方剂说明。")
            parts.append("这些结果是知识图谱和资料检索给出的学习线索，不构成诊断或用药建议。")
            return "".join(parts)

        if intent == "mechanism_explanation" and evidence:
            mechanism_titles = "；".join(item["title"] for item in evidence[:3])
            return f"当前可用证据主要集中在：{mechanism_titles}。若证据中没有直接机制/配伍说明，应避免把普通功效关系当作机制结论。"

        parts = [f"关于“{query}”，当前资料可以从图谱实体、关系路径和文本片段三方面交叉查看。"]
        if structured.get("syndromes"):
            parts.append("较相关的证候包括" + "、".join(self._compact_syndrome_names(structured["syndromes"], graph, limit=4)) + "。")
        if structured.get("formulas"):
            parts.append("可继续核对的方剂有" + "、".join(structured["formulas"][:4]) + "。")
        if structured.get("herbs"):
            parts.append("涉及的药材实体包括" + "、".join(structured["herbs"][:8]) + "。")
        if evidence or graph.get("edges"):
            parts.append("具体依据和关系路径已放在下方，可展开查看来源片段与图谱关系。")
        if not evidence and not graph.get("edges"):
            parts.append("当前没有检索到足够直接证据，建议补充更具体的方剂、证候、症状或药材名称。")
        return "".join(parts)

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            value = str(value).strip()
            if value and value not in result:
                result.append(value)
        return result

    @staticmethod
    def _unique_entities(entities: list[Entity]) -> list[Entity]:
        result: list[Entity] = []
        seen: set[str] = set()
        for entity in entities:
            if entity.id in seen:
                continue
            seen.add(entity.id)
            result.append(entity)
        return result


@lru_cache(maxsize=1)
def get_local_graphrag_service() -> LocalGraphRAGService:
    return LocalGraphRAGService()
