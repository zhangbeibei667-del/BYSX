from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter

from backend.db.database import get_connection


class VectorRetrievalService:
    """Persistent, dependency-free Chinese vector index with source citations.

    Character bigrams are projected into a fixed dimensional vector.  This is
    deterministic, works offline, and is combined with lexical overlap so the
    application remains useful without downloading an embedding model.
    """

    dimensions = 384

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
                 "edition": document["edition"] or "", "publisher": document["publisher"] or "",
                 "identifier": document["identifier"] or "", "source_url": document["source_url"] or ""}
                for i, item in enumerate(chunks)
            ])
        except Exception:
            pass
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

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        query_vector = self.embed(query)
        query_terms = set(self._terms(query))
        semantic: dict[tuple[int, int], dict] = {}
        try:
            from backend.services.qdrant_vector_store import get_qdrant_vector_store
            for hit in get_qdrant_vector_store().search(query, limit=max(20, top_k * 4)):
                semantic[(hit["document_id"], hit["chunk_index"])] = hit
        except Exception:
            pass
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT c.id, c.document_id, c.chunk_index, c.content, c.embedding, c.locator_json,
                          d.title, d.source, d.category, d.edition, d.chapter, d.section,
                          d.publisher, d.identifier, d.source_url
                   FROM document_chunks c JOIN documents d ON d.id = c.document_id"""
            ).fetchall()
        ranked = []
        for row in rows:
            if self._is_disabled_source(row):
                continue
            key = (row["document_id"], row["chunk_index"])
            vector_score = semantic.get(key, {}).get("semantic_score", self._cosine(query_vector, json.loads(row["embedding"])))
            terms = set(self._terms(row["content"]))
            lexical = len(query_terms & terms) / max(1, len(query_terms))
            phrase_bonus = 0.12 if query in row["content"] else 0.0
            source_bonus = 0.03 if row["category"] in {"教材", "药典", "方剂说明"} else 0.0
            score = vector_score * 0.62 + lexical * 0.23 + phrase_bonus + source_bonus
            if lexical == 0 and phrase_bonus == 0 and vector_score < 0.72:
                continue
            if score < 0.30:
                continue
            locator = json.loads(row["locator_json"] or "{}")
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
                    "retrieval_mode": "qdrant-dense+lexical-rerank" if semantic else "local-vector-hybrid",
                    "trace": {"document_id": row["document_id"], "chunk_index": row["chunk_index"], "location": location},
                }
            )
        return sorted(ranked, key=lambda item: item["score"], reverse=True)[:top_k]

    @staticmethod
    def _is_disabled_source(row) -> bool:
        if os.getenv("ENABLE_SYMMAP_DATA", "false").strip().lower() in {"1", "true", "yes", "on"}:
            return False
        source_text = " ".join(
            str(row[field] or "")
            for field in ("title", "source", "identifier", "source_url")
        ).lower()
        return "symmap" in source_text or "中药与药典来源索引" in source_text

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
