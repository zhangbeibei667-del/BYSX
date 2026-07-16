from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

from backend.db.database import get_connection


class VectorRetrievalService:
    """Persistent, dependency-free Chinese vector index with source citations.

    Character bigrams are projected into a fixed dimensional vector.  This is
    deterministic, works offline, and is combined with lexical overlap so the
    application remains useful without downloading an embedding model.
    """

    dimensions = 384
    _corpus_cache: list[dict] | None = None
    _corpus_search_rows: list[dict] | None = None
    _corpus_question_index: dict[str, set[int]] | None = None
    _corpus_syndrome_index: dict[str, set[int]] | None = None
    _document_cache: list[dict] | None = None
    _qdrant_unavailable = False

    def index_document(self, document_id: int, text: str) -> int:
        chunks = self._chunk_with_locators(text)
        with get_connection() as conn:
            conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
            conn.executemany(
                """INSERT INTO document_chunks(document_id, chunk_index, content, embedding, token_count, locator_json, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (document_id, i, item["content"], json.dumps(self.embed(item["content"])),
                     len(self._terms(item["content"])), json.dumps(item["locator"], ensure_ascii=False),
                     hashlib.sha256(item["content"].encode()).hexdigest())
                    for i, item in enumerate(chunks)
                ],
            )
            conn.commit()
            document = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        try:
            from backend.services.qdrant_vector_store import get_qdrant_vector_store
            store = get_qdrant_vector_store()
            store.delete_document(document_id)
            store.upsert([
                {"point_id": document_id * 1_000_000 + i, "document_id": document_id, "chunk_index": i,
                 "content": item["content"], "locator": item["locator"], "title": document["title"],
                 "source": document["source"] or document["title"], "category": document["category"],
                 "embedding_text": "\n".join(filter(None, [document["category"], document["title"],
                                                           document["source"] or "", item["content"]])),
                 "edition": document["edition"] or "", "publisher": document["publisher"] or "",
                 "identifier": document["identifier"] or "", "source_url": document["source_url"] or ""}
                for i, item in enumerate(chunks)
            ])
        except Exception:
            pass
        self.__class__._document_cache = None
        return len(chunks)

    def delete_document(self, document_id: int) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
            conn.commit()
        try:
            from backend.services.qdrant_vector_store import get_qdrant_vector_store
            get_qdrant_vector_store().delete_document(document_id)
        except Exception:
            pass
        self.__class__._document_cache = None

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        query_vector = self.embed(query)
        query_terms = set(self._terms(query))
        semantic: dict[tuple[int, int], dict] = {}
        if not self._qdrant_unavailable:
            try:
                from backend.services.qdrant_vector_store import get_qdrant_vector_store
                for hit in get_qdrant_vector_store().search(query, limit=max(200, top_k * 40)):
                    key = ((f"corpus:{hit.get('chunk_id') or hit.get('point_id')}"), 0) \
                        if hit.get("corpus_record") else (hit["document_id"], hit["chunk_index"])
                    semantic[key] = hit
            except Exception:
                self.__class__._qdrant_unavailable = True
        # Keep the complete research corpus searchable when the external
        # embedding provider is temporarily unavailable. This is a lexical
        # fallback over the real corpus, never fabricated medical content.
        semantic_ids = {str(hit.get("chunk_id") or hit.get("point_id") or "") for hit in semantic.values()}
        for hit in self._search_corpus_lexical(query, limit=max(80, top_k * 20)):
            if str(hit.get("chunk_id")) not in semantic_ids:
                semantic[(f"corpus:{hit['chunk_id']}", 0)] = hit
        if self._document_cache is None:
            with get_connection() as conn:
                db_rows = conn.execute(
                    """SELECT c.id, c.document_id, c.chunk_index, c.content, c.embedding, c.locator_json,
                              d.title, d.source, d.category, d.edition, d.chapter, d.section,
                              d.publisher, d.identifier, d.source_url
                       FROM document_chunks c JOIN documents d ON d.id = c.document_id"""
                ).fetchall()
            self.__class__._document_cache = [
                {**dict(row), "_embedding": json.loads(row["embedding"]),
                 "_terms": set(self._terms(row["content"])),
                 "_locator": json.loads(row["locator_json"] or "{}")}
                for row in db_rows
            ]
        rows = self._document_cache
        ranked = []
        for row in rows:
            key = (row["document_id"], row["chunk_index"])
            terms = row["_terms"]
            lexical = len(query_terms & terms) / max(1, len(query_terms))
            phrase_bonus = 0.12 if query in row["content"] else 0.0
            semantic_hit = semantic.get(key)
            if lexical == 0 and phrase_bonus == 0 and semantic_hit is None:
                continue
            vector_score = semantic_hit.get("semantic_score") if semantic_hit else self._cosine(query_vector, row["_embedding"])
            source_bonus = 0.08 if row["category"] in {"教材", "药典", "方剂说明"} else 0.0
            category_bonus = 0.18 if row["category"] and row["category"] in query else 0.0
            score = vector_score * 0.68 + lexical * 0.25 + phrase_bonus + source_bonus + category_bonus
            if lexical == 0 and phrase_bonus == 0 and vector_score < 0.72:
                continue
            if score < 0.30:
                continue
            locator = row["_locator"]
            chapter = locator.get("chapter") or row["chapter"] or ""
            section = locator.get("section") or row["section"] or ""
            page = locator.get("page")
            location = " / ".join(filter(None, [chapter, section, f"第 {page} 页" if page else ""]))
            ranked.append(
                {
                    "id": f"doc-{row['document_id']}-chunk-{row['chunk_index']}",
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                    "title": row["title"],
                    "source": row["source"] or row["title"],
                    "category": row["category"], "edition": row["edition"] or "",
                    "chapter": chapter, "section": section, "page": page,
                    "publisher": row["publisher"] or "", "identifier": row["identifier"] or "",
                    "source_url": row["source_url"] or "",
                    "content": row["content"],
                    "score": round(score, 4),
                    "citation": f"《{row['title']}》" + (f"，{location}" if location else "") + f"（片段 {row['chunk_index'] + 1}）",
                    "retrieval_mode": "qdrant-dense+lexical-rerank" if any(
                        hit.get("retrieval_mode") == "qdrant-semantic" for hit in semantic.values()
                    ) else "local-vector-hybrid",
                    "trace": {"document_id": row["document_id"], "chunk_index": row["chunk_index"], "location": location},
                }
            )
        # The 7,951-record research corpus is stored directly in Qdrant rather
        # than duplicated into SQLite. Include those traceable payloads in the
        # same hybrid ranking result.
        for hit in semantic.values():
            if not hit.get("corpus_record"):
                continue
            content = str(hit.get("content") or "")
            questions = [str(question) for question in hit.get("questions", [])]
            ranking_text = "\n".join([*questions, content])
            terms = set(self._terms(ranking_text))
            lexical = len(query_terms & terms) / max(1, len(query_terms))
            vector_score = float(hit.get("semantic_score", 0.0))
            phrase_bonus = 0.18 if query in ranking_text or any(
                re.sub(r"\W+", "", query) == re.sub(r"\W+", "", question) for question in questions
            ) else 0.0
            category = str(hit.get("category") or "补充语料")
            category_bonus = 0.18 if category and category in query else 0.0
            score = vector_score * 0.55 + lexical * 0.35 + phrase_bonus + category_bonus
            if lexical == 0 and phrase_bonus == 0 and vector_score < 0.35:
                continue
            if score < 0.28:
                continue
            locator = hit.get("locator") if isinstance(hit.get("locator"), dict) else {}
            chapter = str(locator.get("chapter") or hit.get("chapter") or "")
            section = str(locator.get("section") or hit.get("section") or "")
            page = locator.get("page") or hit.get("page")
            location = " / ".join(filter(None, [chapter, section, f"第 {page} 页" if page else ""]))
            chunk_id = str(hit.get("chunk_id") or hit.get("point_id") or "")
            title = str(hit.get("title") or chunk_id or "RAG 语料")
            ranked.append({
                "id": chunk_id,
                "document_id": hit.get("document_id"),
                "chunk_index": hit.get("chunk_index", 0),
                "title": title,
                "source": str(hit.get("source") or title),
                "category": category,
                "edition": str(hit.get("edition") or ""),
                "chapter": chapter,
                "section": section,
                "page": page,
                "publisher": str(hit.get("publisher") or ""),
                "identifier": str(hit.get("identifier") or chunk_id),
                "source_url": str(hit.get("source_url") or ""),
                "content": content,
                "score": round(score, 4),
                "citation": f"《{title}》" + (f"，{location}" if location else "") + f"（片段 {chunk_id}）",
                "retrieval_mode": (
                    "qdrant-semantic+lexical-rerank"
                    if hit.get("retrieval_mode") == "qdrant-semantic"
                    else "corpus-lexical-fallback"
                ),
                "trace": {"document_id": hit.get("document_id"), "chunk_id": chunk_id, "location": location},
            })
        return sorted(ranked, key=lambda item: item["score"], reverse=True)[:top_k]

    @classmethod
    def _load_corpus(cls) -> list[dict]:
        if cls._corpus_cache is not None:
            return cls._corpus_cache
        root = Path(__file__).resolve().parents[2]
        path = root / "member3" / "data" / "processed" / "rag_corpus_clean.jsonl"
        records: list[dict] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if line.strip():
                    records.append(json.loads(line))
        cls._corpus_cache = records
        return records

    def _search_corpus_lexical(self, query: str, limit: int) -> list[dict]:
        query_terms = set(self._terms(query))
        normalized_query = re.sub(r"\W+", "", query)
        scored: list[tuple[float, dict]] = []
        if self._corpus_search_rows is None or self._corpus_question_index is None:
            search_rows: list[dict] = []
            question_index: dict[str, set[int]] = {}
            syndrome_index: dict[str, set[int]] = {}
            for index, record in enumerate(self._load_corpus()):
                metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
                questions = [str(value) for value in metadata.get("questions", [])]
                text = "\n".join([str(record.get("title") or ""), *questions, str(record.get("content") or "")])
                search_rows.append({"record": record, "metadata": metadata, "questions": questions,
                                    "text": text, "terms": None})
                for question in questions:
                    question_index.setdefault(re.sub(r"\W+", "", question), set()).add(index)
                syndrome = str(metadata.get("syndrome") or "")
                if syndrome:
                    syndrome_index.setdefault(syndrome, set()).add(index)
            self.__class__._corpus_search_rows = search_rows
            self.__class__._corpus_question_index = question_index
            self.__class__._corpus_syndrome_index = syndrome_index
        candidate_indexes = set(self._corpus_question_index.get(normalized_query, ()))
        for syndrome, indexes in self._corpus_syndrome_index.items():
            if syndrome in query:
                candidate_indexes.update(indexes)
        if not candidate_indexes:
            # Generic fallback: cheap substring filtering first, then tokenize
            # only the reduced candidate set.
            compact_terms = [term for term in query_terms if len(term) >= 2]
            for index, cached in enumerate(self._corpus_search_rows):
                if any(term in cached["text"] for term in compact_terms):
                    candidate_indexes.add(index)
        for index in candidate_indexes:
            cached = self._corpus_search_rows[index]
            record = cached["record"]
            metadata = cached["metadata"]
            questions = cached["questions"]
            if cached["terms"] is None:
                cached["terms"] = set(self._terms(cached["text"]))
            terms = cached["terms"]
            lexical = len(query_terms & terms) / max(1, len(query_terms))
            exact = normalized_query and any(normalized_query == re.sub(r"\W+", "", item) for item in questions)
            syndrome = str(metadata.get("syndrome") or "")
            entity_bonus = 0.28 if syndrome and syndrome in query else 0.0
            section_bonus = 0.9 if metadata.get("section") == "overview" and any(
                marker in query for marker in ("定义", "典型", "辨证要点")
            ) else 0.0
            score = lexical + (0.7 if exact else 0.0) + entity_bonus + section_bonus
            if score < 0.16:
                continue
            chunk_id = str(record.get("chunk_id") or "")
            scored.append((score, {
                "point_id": chunk_id,
                "chunk_id": chunk_id,
                "document_id": str(record.get("doc_id") or chunk_id),
                "chunk_index": 0,
                "corpus_record": True,
                "title": str(record.get("title") or chunk_id),
                "content": str(record.get("content") or ""),
                "source": str(record.get("source") or "补充语料"),
                "category": "文献问答" if record.get("source") == "TCM-QG" else "证候知识",
                "identifier": chunk_id,
                "questions": questions,
                "locator": {"section": str(metadata.get("section") or metadata.get("record_type") or "")},
                "semantic_score": min(1.0, score),
                "retrieval_mode": "corpus-lexical-fallback",
            }))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def embed(self, text: str) -> list[float]:
        counts: Counter[int] = Counter()
        for term in self._terms(text):
            digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest, "big") % self.dimensions
            counts[idx] += 1
        norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
        return [counts.get(i, 0) / norm for i in range(self.dimensions)]

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))

    @staticmethod
    def _terms(text: str) -> list[str]:
        compact = re.sub(r"\s+", "", text.lower())
        chinese = [compact[i : i + 2] for i in range(max(0, len(compact) - 1))]
        words = re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]{1,6}", text.lower())
        return chinese + words

    @staticmethod
    def _chunk(text: str, size: int = 520, overlap: int = 80) -> list[str]:
        text = re.sub(r"\r\n?", "\n", text).strip()
        if not text:
            return []
        paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
        chunks: list[str] = []
        buffer = ""
        for paragraph in paragraphs:
            if len(buffer) + len(paragraph) + 1 <= size:
                buffer = f"{buffer}\n{paragraph}".strip()
                continue
            if buffer:
                chunks.append(buffer)
            while len(paragraph) > size:
                chunks.append(paragraph[:size])
                paragraph = paragraph[size - overlap :]
            buffer = paragraph
        if buffer:
            chunks.append(buffer)
        return chunks

    def _chunk_with_locators(self, text: str) -> list[dict]:
        page = None
        chapter = ""
        section = ""
        blocks: list[dict] = []
        buffer: list[str] = []

        def flush() -> None:
            nonlocal buffer
            if not buffer:
                return
            for chunk in self._chunk("\n".join(buffer)):
                blocks.append({"content": chunk, "locator": {"page": page, "chapter": chapter, "section": section}})
            buffer = []

        for line in text.replace("\r", "").split("\n"):
            page_match = re.match(r"^\[PAGE\s+(\d+)\]$", line.strip(), re.I)
            if page_match:
                flush(); page = int(page_match.group(1)); continue
            heading = line.strip().lstrip("#").strip()
            if re.match(r"^(第[一二三四五六七八九十百\d]+[章节篇]|[一二三四五六七八九十]+、)", heading) and len(heading) <= 60:
                flush(); chapter = heading; section = ""; buffer.append(line); continue
            if (line.startswith("##") or re.match(r"^\d+(\.\d+)+\s", heading)) and len(heading) <= 80:
                flush(); section = heading; buffer.append(line); continue
            buffer.append(line)
        flush()
        return blocks
