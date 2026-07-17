from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# 1. 项目根目录
# ============================================================

# 当前文件：
# member3/app/config.py
#
# parents[1]：
# member3/
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ============================================================
# 2. 加载 .env
# ============================================================

ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(
    ENV_PATH,
    override=False,
)


# ============================================================
# 3. 路径解析工具
# ============================================================

def _resolve_path(
    value: str | None,
    default: Path,
) -> Path:
    """
    将环境变量中的路径统一转换为绝对路径。

    支持：

    1. 绝对路径
       F:\\data\\graph\\entities

    2. 相对路径
       data/graph/entities

    相对路径统一基于 PROJECT_ROOT：
       member3/
    进行解析。
    """
    if value is None:
        return default.resolve()

    text = value.strip()

    if not text:
        return default.resolve()

    path = Path(text)

    if path.is_absolute():
        return path.resolve()

    return (
        PROJECT_ROOT
        / path
    ).resolve()


# ============================================================
# 4. FastAPI 服务配置
# ============================================================

APP_HOST = os.getenv(
    "APP_HOST",
    "0.0.0.0",
)

APP_PORT = int(
    os.getenv(
        "APP_PORT",
        "8003",
    )
)


# ============================================================
# 5. 数据目录
# ============================================================

DATA_DIR = PROJECT_ROOT / "data"


# ============================================================
# 6. Mock 图谱
# ============================================================

# 暂时保留旧 Mock 图谱兼容：
#
# data/
# ├── entities.json
# └── relations.json
#
# 正式联调阶段推荐使用：
# directory 或 custom。

MOCK_ENTITIES_PATH = (
    DATA_DIR
    / "entities.json"
)

MOCK_RELATIONS_PATH = (
    DATA_DIR
    / "relations.json"
)


# ============================================================
# 7. 团队真实多文件图谱目录
# ============================================================

# 推荐正式结构：
#
# data/
# └── graph/
#     ├── entities/
#     │   ├── entities_symptoms.json
#     │   ├── entities_syndromes.json
#     │   ├── entities_formulas.json
#     │   ├── entities_herbs.json
#     │   ├── entities_effects.json
#     │   ├── entities_contraindications.json
#     │   └── entities_literature.json
#     │
#     └── relations/
#         ├── relations_contains.json
#         ├── relations_contra.json
#         ├── relations_herb_effect.json
#         ├── relations_source.json
#         └── ...

GRAPH_DIR = (
    DATA_DIR
    / "graph"
)

GRAPH_ENTITIES_DIR = (
    GRAPH_DIR
    / "entities"
)

GRAPH_RELATIONS_DIR = (
    GRAPH_DIR
    / "relations"
)


# ============================================================
# 8. 图谱数据源模式
# ============================================================

# 支持：
#
# mock
#   data/entities.json
#   data/relations.json
#
# directory
#   data/graph/entities/
#   data/graph/relations/
#
# custom
#   使用 .env 中：
#   GRAPH_ENTITIES_PATH
#   GRAPH_RELATIONS_PATH

GRAPH_SOURCE = os.getenv(
    "GRAPH_SOURCE",
    "mock",
).strip().lower()


if GRAPH_SOURCE not in {
    "mock",
    "directory",
    "custom",
}:
    raise ValueError(
        "GRAPH_SOURCE 配置错误。"
        "仅支持: "
        "mock / directory / custom，"
        f"当前值: {GRAPH_SOURCE}"
    )


# ============================================================
# 9. 根据模式确定默认图谱路径
# ============================================================

if GRAPH_SOURCE == "mock":
    default_entities_path = (
        MOCK_ENTITIES_PATH
    )

    default_relations_path = (
        MOCK_RELATIONS_PATH
    )

elif GRAPH_SOURCE == "directory":
    default_entities_path = (
        GRAPH_ENTITIES_DIR
    )

    default_relations_path = (
        GRAPH_RELATIONS_DIR
    )

else:
    # custom 模式通常通过 .env
    # 指定外部目录。
    #
    # 未配置时仍给出项目内默认目录，
    # 让错误路径更容易排查。
    default_entities_path = (
        GRAPH_ENTITIES_DIR
    )

    default_relations_path = (
        GRAPH_RELATIONS_DIR
    )


# ============================================================
# 10. 最终实体 / 关系数据源
# ============================================================

# 新版 GraphSearch 已支持：
#
# - 单个 JSON 文件
# - 包含多个 JSON 的目录

GRAPH_ENTITIES_SOURCE = _resolve_path(
    os.getenv(
        "GRAPH_ENTITIES_PATH"
    ),
    default_entities_path,
)

GRAPH_RELATIONS_SOURCE = _resolve_path(
    os.getenv(
        "GRAPH_RELATIONS_PATH"
    ),
    default_relations_path,
)


# 保留现有变量名，
# 避免其他模块额外修改。

ENTITIES_PATH = (
    GRAPH_ENTITIES_SOURCE
)

RELATIONS_PATH = (
    GRAPH_RELATIONS_SOURCE
)


# ============================================================
# 11. Milvus 正式向量数据库配置
# ============================================================

# 当前项目正式 RAG 后端固定使用 Milvus。
#
# 基础语料：
# data/processed/rag_corpus_clean.jsonl
#
# 当前已验证：
# 7951 chunks
#
# HKCMMS 药典增量语料：
# data/pharmacopoeia/processed/hkcmms/index_ready/chunks_for_milvus.jsonl
#
# 当前已验证：
# 1094 chunks

MILVUS_URI = os.getenv(
    "MILVUS_URI",
    "http://127.0.0.1:19530",
)

MILVUS_COLLECTION = os.getenv(
    "MILVUS_COLLECTION",
    "tcm_rag_chunks",
)


# ============================================================
# 12. Embedding 配置
# ============================================================

EMBEDDING_API_KEY = os.getenv(
    "EMBEDDING_API_KEY",
    "",
)

EMBEDDING_BASE_URL = os.getenv(
    "EMBEDDING_BASE_URL",
    "https://api.siliconflow.cn/v1",
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "Qwen/Qwen3-VL-Embedding-8B",
)

EMBEDDING_DIM = int(
    os.getenv(
        "EMBEDDING_DIM",
        os.getenv("EMBEDDING_DIMENSIONS", "1024"),
    )
)


# ============================================================
# 13. LLM 配置
# ============================================================

LLM_ENABLED = (
    os.getenv(
        "LLM_ENABLED",
        "false",
    ).strip().lower()
    == "true"
)

LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://api.deepseek.com",
)

LLM_API_KEY = os.getenv(
    "LLM_API_KEY",
    "",
)

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "deepseek-chat",
)


# ============================================================
# 14. 安全运行配置摘要
# ============================================================

def get_runtime_config() -> dict[
    str,
    str | int | bool,
]:
    """
    返回当前运行配置摘要。

    不返回：
    - LLM_API_KEY
    - EMBEDDING_API_KEY

    可用于：
    - FastAPI health
    - 团队联调
    - 环境检查
    """
    return {
        "project_root": str(
            PROJECT_ROOT
        ),

        "app_host": APP_HOST,

        "app_port": APP_PORT,

        "graph_source": (
            GRAPH_SOURCE
        ),

        "entities_source": str(
            ENTITIES_PATH
        ),

        "relations_source": str(
            RELATIONS_PATH
        ),

        # 正式文本检索固定使用 Milvus
        "vector_backend": "milvus",

        "milvus_uri": (
            MILVUS_URI
        ),

        "milvus_collection": (
            MILVUS_COLLECTION
        ),

        "embedding_model": (
            EMBEDDING_MODEL
        ),

        "embedding_dim": (
            EMBEDDING_DIM
        ),

        "llm_enabled": (
            LLM_ENABLED
        ),

        "llm_model": (
            LLM_MODEL
        ),
    }
