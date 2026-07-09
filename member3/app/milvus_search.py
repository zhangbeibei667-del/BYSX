from __future__ import annotations

import os

from dotenv import load_dotenv
from pymilvus import MilvusClient

from app.embedding_client import EmbeddingClient
from app.vector_search import RetrievedChunk


# ============================================================
# 先加载 .env
# ============================================================
load_dotenv()


MILVUS_URI = os.getenv(
    "MILVUS_URI",
    "http://127.0.0.1:19530",
)

COLLECTION_NAME = os.getenv(
    "MILVUS_COLLECTION",
    "tcm_rag_chunks",
)


class MilvusVectorSearch:
    """
    TCM GraphRAG 正式 Milvus 向量检索器。

    流程：
    1. Query -> Embedding；
    2. Milvus Dense Retrieval；
    3. 召回较多候选；
    4. Query-aware Rerank；
    5. 截取最终 Top-K；
    6. 转换为 RetrievedChunk；
    7. 直接交给 GraphRAGService。
    """

    def __init__(self) -> None:
        # 连接 Milvus
        self.client = MilvusClient(
            uri=MILVUS_URI,
        )

        # Query Embedding
        self.embedding_client = EmbeddingClient()

        # 检查 Collection
        collections = self.client.list_collections()

        if COLLECTION_NAME not in collections:
            raise RuntimeError(
                "Milvus Collection 不存在: "
                f"{COLLECTION_NAME}"
            )

        # 显式加载 Collection
        self.client.load_collection(
            collection_name=COLLECTION_NAME,
        )

    # ========================================================
    # 1. 从 Query 中提取当前轻量级实体提示
    # ========================================================
    @staticmethod
    def _extract_entity_hint(
        query: str,
    ) -> str:
        """
        当前开发阶段的轻量查询提示提取。

        示例：
        风寒袭肺证有哪些症状？
        ->
        风寒袭肺证

        归脾汤有什么功效？
        ->
        归脾汤

        后续团队正式图谱整合后，
        可替换为 GraphSearch.extract_entities()。
        """
        entity_hint = query.strip().lower()

        suffixes = [
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
            if entity_hint.endswith(suffix):
                entity_hint = entity_hint[
                    :-len(suffix)
                ].strip()
                break

        # 去除部分常见前缀
        prefixes = [
            "请问",
            "我想知道",
            "想了解",
            "请介绍一下",
            "介绍一下",
        ]

        for prefix in prefixes:
            if entity_hint.startswith(prefix):
                entity_hint = entity_hint[
                    len(prefix):
                ].strip()
                break

        return entity_hint

    # ========================================================
    # 2. Query-aware Rerank
    # ========================================================
    def _rerank_hits(
        self,
        query: str,
        hits: list[dict],
    ) -> list[dict]:
        """
        对 Milvus Dense Retrieval 结果进行轻量重排。

        当前规则：
        1. 保留原始 COSINE 分数；
        2. 查询实体提示完整出现在 title：
           +0.08
        3. 查询实体提示完整出现在 content：
           +0.04

        示例：
        Query = 风寒袭肺证有哪些症状？

        风寒袭肺证：定义与典型表现
        会获得 title exact-match bonus。
        """
        entity_hint = self._extract_entity_hint(
            query
        )

        for hit in hits:
            base_score = float(
                hit.get(
                    "score",
                    0.0,
                )
            )

            title = str(
                hit.get(
                    "title",
                    "",
                )
            ).lower()

            content = str(
                hit.get(
                    "content",
                    "",
                )
            ).lower()

            bonus = 0.0

            if entity_hint:
                if entity_hint in title:
                    bonus += 0.08

                elif entity_hint in content:
                    bonus += 0.04

            hit["rerank_bonus"] = bonus

            hit["rerank_score"] = (
                base_score + bonus
            )

        return sorted(
            hits,
            key=lambda item: item.get(
                "rerank_score",
                item.get(
                    "score",
                    0.0,
                ),
            ),
            reverse=True,
        )

    # ========================================================
    # 3. Milvus 原始候选召回
    # ========================================================
    def _search_candidates(
        self,
        query: str,
        candidate_k: int,
    ) -> list[dict]:
        """
        从 Milvus 召回候选文本。

        注意：
        这里返回的是内部 dict，
        暂不直接返回给 GraphRAGService。
        """
        # Query -> 1024维 Embedding
        query_vector = (
            self.embedding_client.embed(
                query
            )
        )

        results = self.client.search(
            collection_name=COLLECTION_NAME,
            anns_field="embedding",
            data=[query_vector],
            limit=candidate_k,
            search_params={
                "metric_type": "COSINE",
            },
            output_fields=[
                "chunk_id",
                "doc_id",
                "title",
                "content",
                "source",
            ],
        )

        hits: list[dict] = []

        if not results:
            return hits

        if not results[0]:
            return hits

        for hit in results[0]:
            entity = hit.get(
                "entity",
                {},
            )

            hits.append(
                {
                    "id": hit.get(
                        "id"
                    ),
                    "score": float(
                        hit.get(
                            "distance",
                            0.0,
                        )
                    ),
                    "chunk_id": str(
                        entity.get(
                            "chunk_id",
                            "",
                        )
                    ),
                    "doc_id": str(
                        entity.get(
                            "doc_id",
                            "",
                        )
                    ),
                    "title": str(
                        entity.get(
                            "title",
                            "",
                        )
                    ),
                    "content": str(
                        entity.get(
                            "content",
                            "",
                        )
                    ),
                    "source": str(
                        entity.get(
                            "source",
                            "",
                        )
                    ),
                }
            )

        return hits

    # ========================================================
    # 4. 正式 GraphRAG 检索接口
    # ========================================================
    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[RetrievedChunk]:
        """
        GraphRAGService 直接调用的正式接口。

        与旧 VectorSearch 保持兼容：

        self.vector_search.search(
            query,
            top_k=3,
        )

        返回：
        list[RetrievedChunk]
        """
        query = query.strip()

        if not query:
            raise ValueError(
                "查询文本不能为空"
            )

        if top_k <= 0:
            raise ValueError(
                "top_k 必须大于 0"
            )

        # ----------------------------------------------------
        # 不直接只召回 top_k。
        #
        # 示例：
        # 用户最终需要 3 条，
        # 先从 Milvus 取至少 10 条候选，
        # 再重排。
        # ----------------------------------------------------
        candidate_k = max(
            10,
            top_k * 3,
        )

        # 1. Dense Retrieval
        hits = self._search_candidates(
            query=query,
            candidate_k=candidate_k,
        )

        if not hits:
            return []

        # 2. Query-aware Rerank
        reranked_hits = self._rerank_hits(
            query=query,
            hits=hits,
        )

        # 3. 截取最终 Top-K
        final_hits = reranked_hits[
            :top_k
        ]

        # 4. 转换成现有 GraphRAGService
        #    已经使用的 RetrievedChunk
        chunks: list[RetrievedChunk] = []

        for hit in final_hits:
            title = hit["title"]
            source = hit["source"]

            # 当前统一 EvidenceItem 只有：
            # title
            # content
            #
            # 为了让前端页面能看到数据来源，
            # 将 source 合并到 title 中。
            if source:
                display_title = (
                    f"{title}（{source}）"
                )
            else:
                display_title = title

            chunks.append(
                RetrievedChunk(
                    title=display_title,
                    content=hit["content"],
                    score=float(
                        hit.get(
                            "rerank_score",
                            hit["score"],
                        )
                    ),
                )
            )

        return chunks

    # ========================================================
    # 5. 调试接口
    # ========================================================
    def search_debug(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        仅用于本地调试。

        和正式 search() 不同：
        - search() 返回 RetrievedChunk
        - search_debug() 返回完整 dict

        可以查看：
        - 原始 score
        - rerank bonus
        - rerank score
        - chunk_id
        - source
        """
        query = query.strip()

        if not query:
            raise ValueError(
                "查询文本不能为空"
            )

        if top_k <= 0:
            raise ValueError(
                "top_k 必须大于 0"
            )

        candidate_k = max(
            10,
            top_k * 3,
        )

        hits = self._search_candidates(
            query=query,
            candidate_k=candidate_k,
        )

        reranked_hits = self._rerank_hits(
            query=query,
            hits=hits,
        )

        return reranked_hits[
            :top_k
        ]


# ============================================================
# 本地独立测试
# ============================================================
def main() -> None:
    searcher = MilvusVectorSearch()

    query = "风寒袭肺证有哪些症状？"

    results = searcher.search_debug(
        query=query,
        top_k=5,
    )

    print("=" * 70)
    print(
        f"查询: {query}"
    )
    print("=" * 70)

    for rank, item in enumerate(
        results,
        start=1,
    ):
        print()

        print(
            f"[Top {rank}]"
        )

        print(
            "score         : "
            f"{item['score']:.6f}"
        )

        print(
            "rerank_bonus  : "
            f"{item.get('rerank_bonus', 0.0):.6f}"
        )

        print(
            "rerank_score  : "
            f"{item.get('rerank_score', item['score']):.6f}"
        )

        print(
            f"chunk_id      : "
            f"{item['chunk_id']}"
        )

        print(
            f"doc_id        : "
            f"{item['doc_id']}"
        )

        print(
            f"title         : "
            f"{item['title']}"
        )

        print(
            f"source        : "
            f"{item['source']}"
        )

        print(
            "content       : "
            f"{item['content'][:300]}"
        )

        print("-" * 70)


if __name__ == "__main__":
    main()