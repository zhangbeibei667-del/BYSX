from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RetrievedChunk:
    title: str
    content: str
    score: float = 0.0


class VectorSearch:
    """
    当前开发阶段的轻量文本向量检索。
    后续接真实 Milvus 时，只需要替换 search() 内部实现，
    GraphRAGService 和 FastAPI 接口无需重写。
    """

    def __init__(
        self,
        docs_dir: Path,
        dim: int = 256,
        chunk_size: int = 220,
    ) -> None:
        self.dim = dim
        self.chunk_size = chunk_size
        self.chunks = self._load_chunks(docs_dir)
        self.chunk_vectors = [
            self._embed(item.content)
            for item in self.chunks
        ]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        text = text.lower().strip()

        # 英文和数字 token
        ascii_tokens = re.findall(r"[a-z0-9_]+", text)

        # 中文 unigram + bigram
        chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
        zh_tokens = list(chinese)
        zh_tokens += [
            chinese[i:i + 2]
            for i in range(max(0, len(chinese) - 1))
        ]

        return ascii_tokens + zh_tokens

    def _embed(self, text: str) -> list[float]:
        """
        把 token 哈希到固定维度向量。
        注意：这是开发期占位方案，不等同于正式语义 Embedding 模型。
        """
        vector = [0.0] * self.dim

        for token in self._tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    def _split_text(self, text: str) -> list[str]:
        """先按段落切分，过长段落再按固定长度切分。"""
        paragraphs = [
            p.strip()
            for p in re.split(r"\n\s*\n", text)
            if p.strip()
        ]

        chunks: list[str] = []

        for paragraph in paragraphs:
            if len(paragraph) <= self.chunk_size:
                chunks.append(paragraph)
            else:
                for i in range(0, len(paragraph), self.chunk_size):
                    piece = paragraph[i:i + self.chunk_size].strip()
                    if piece:
                        chunks.append(piece)

        return chunks

    def _load_chunks(self, docs_dir: Path) -> list[RetrievedChunk]:
        chunks: list[RetrievedChunk] = []

        for path in sorted(docs_dir.glob("*.txt")):
            text = path.read_text(encoding="utf-8")

            for piece in self._split_text(text):
                chunks.append(
                    RetrievedChunk(
                        title=path.stem,
                        content=piece,
                        score=0.0,
                    )
                )

        return chunks

    def search(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        if not self.chunks:
            return []

        query_vector = self._embed(query)
        scored: list[RetrievedChunk] = []

        for chunk, vector in zip(self.chunks, self.chunk_vectors):
            score = self._cosine(query_vector, vector)

            scored.append(
                RetrievedChunk(
                    title=chunk.title,
                    content=chunk.content,
                    score=score,
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]
