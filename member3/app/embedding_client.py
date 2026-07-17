from __future__ import annotations

import os
from typing import Sequence

from openai import OpenAI


class EmbeddingClient:
    """TCM GraphRAG 文本向量化客户端。"""

    def __init__(self) -> None:
        api_key = os.getenv("EMBEDDING_API_KEY")
        base_url = os.getenv(
            "EMBEDDING_BASE_URL",
            "https://api.siliconflow.cn/v1",
        )

        if not api_key:
            raise ValueError(
                "缺少环境变量 EMBEDDING_API_KEY"
            )

        if not base_url:
            raise ValueError(
                "缺少环境变量 EMBEDDING_BASE_URL"
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url=self._normalize_openai_base_url(base_url),
        )

        self.model = os.getenv(
            "EMBEDDING_MODEL",
            "Qwen/Qwen3-VL-Embedding-8B",
        )

        self.dimensions = int(
            os.getenv(
                "EMBEDDING_DIM",
                os.getenv("EMBEDDING_DIMENSIONS", "1024"),
            )
        )

    @staticmethod
    def _normalize_openai_base_url(base_url: str) -> str:
        clean_base_url = base_url.strip().rstrip("/")
        if clean_base_url.endswith("/embeddings"):
            return clean_base_url[: -len("/embeddings")]
        return clean_base_url

    def embed(self, text: str) -> list[float]:
        """
        单条文本向量化。
        """
        text = text.strip()

        if not text:
            raise ValueError(
                "Embedding 输入文本不能为空"
            )

        response = self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
        )

        vector = response.data[0].embedding

        self._validate_vector(vector)

        return vector

    def embed_batch(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """
        批量文本向量化。

        SiliconFlow Qwen embedding 当前按最多 10 条一批调用。
        """
        cleaned_texts = [
            text.strip()
            for text in texts
        ]

        if not cleaned_texts:
            return []

        if any(not text for text in cleaned_texts):
            raise ValueError(
                "批量 Embedding 中存在空文本"
            )

        if len(cleaned_texts) > 10:
            raise ValueError(
                "单批文本数量不能超过 10 条"
            )

        response = self.client.embeddings.create(
            model=self.model,
            input=cleaned_texts,
            dimensions=self.dimensions,
        )

        # 按 API 返回的 index 恢复原始输入顺序
        ordered_items = sorted(
            response.data,
            key=lambda item: item.index,
        )

        vectors = [
            item.embedding
            for item in ordered_items
        ]

        if len(vectors) != len(cleaned_texts):
            raise ValueError(
                "Embedding 返回数量不匹配: "
                f"输入 {len(cleaned_texts)} 条, "
                f"返回 {len(vectors)} 条"
            )

        for vector in vectors:
            self._validate_vector(vector)

        return vectors

    def _validate_vector(
        self,
        vector: list[float],
    ) -> None:
        """
        验证实际向量维度。
        """
        if len(vector) != self.dimensions:
            raise ValueError(
                "Embedding 维度不匹配: "
                f"期望 {self.dimensions}, "
                f"实际 {len(vector)}"
            )
