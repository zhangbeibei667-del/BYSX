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

# 当前开发阶段仍然保留：
#
# data/
# ├── entities.json
# └── relations.json

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

# 未来推荐结构：
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
#         ├── relations_syndrome_symptom.json
#         ├── relations_syndrome_formula.json
#         ├── relations_formula_herb.json
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
#   使用：
#   data/entities.json
#   data/relations.json
#
# directory
#   使用：
#   data/graph/entities/
#   data/graph/relations/
#
# custom
#   完全使用：
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
# 9. 根据模式确定图谱路径
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
    # custom 模式仍给默认值，
    # 但实际建议通过 .env 指定路径。
    default_entities_path = (
        GRAPH_ENTITIES_DIR
    )

    default_relations_path = (
        GRAPH_RELATIONS_DIR
    )


# ============================================================
# 10. 最终实体 / 关系数据源
# ============================================================

# 注意：
# GraphSearch 新版本已经支持：
#
# - 单个 JSON 文件
# - JSON 目录
#
# 所以这里统一使用 Path 即可。

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


# ------------------------------------------------------------
# 兼容旧 main.py
# ------------------------------------------------------------
#
# 当前 main.py 很可能仍然：
#
# GraphSearch(
#     entities_path=ENTITIES_PATH,
#     relations_path=RELATIONS_PATH,
# )
#
# 所以继续保留旧变量名。
#
# 后续 main.py 可以不改，
# 也可以改用 GRAPH_ENTITIES_SOURCE。

ENTITIES_PATH = (
    GRAPH_ENTITIES_SOURCE
)

RELATIONS_PATH = (
    GRAPH_RELATIONS_SOURCE
)


# ============================================================
# 11. 旧 Mock 文本目录
# ============================================================

# 当前 Hash VectorSearch fallback 仍可能使用。
#
# 正式 Milvus 模式下，
# 不再作为主 RAG 知识库。

DOCS_DIR = _resolve_path(
    os.getenv(
        "DOCS_DIR"
    ),
    DATA_DIR / "docs",
)


# ============================================================
# 12. Vector Backend
# ============================================================

# 支持：
#
# milvus
#   正式 7951 条真实 RAG 语料
#
# hash
#   旧开发期 Mock / fallback

VECTOR_BACKEND = os.getenv(
    "VECTOR_BACKEND",
    "milvus",
).strip().lower()


if VECTOR_BACKEND not in {
    "milvus",
    "hash",
}:
    raise ValueError(
        "VECTOR_BACKEND 配置错误。"
        "仅支持: milvus / hash，"
        f"当前值: {VECTOR_BACKEND}"
    )


# ============================================================
# 13. Milvus 配置
# ============================================================

MILVUS_URI = os.getenv(
    "MILVUS_URI",
    "http://127.0.0.1:19530",
)

MILVUS_COLLECTION = os.getenv(
    "MILVUS_COLLECTION",
    "tcm_rag_chunks",
)


# ============================================================
# 14. Embedding 配置
# ============================================================

EMBEDDING_API_KEY = os.getenv(
    "EMBEDDING_API_KEY",
    "",
)

EMBEDDING_BASE_URL = os.getenv(
    "EMBEDDING_BASE_URL",
    "",
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "text-embedding-v4",
)

EMBEDDING_DIM = int(
    os.getenv(
        "EMBEDDING_DIM",
        "1024",
    )
)


# ============================================================
# 15. LLM 配置
# ============================================================

LLM_ENABLED = (
    os.getenv(
        "LLM_ENABLED",
        "false",
    ).lower()
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
# 16. 调试辅助
# ============================================================

def get_runtime_config() -> dict[str, str | int | bool]:
    """
    返回当前运行配置摘要。

    注意：
    不返回任何 API Key，
    避免敏感信息泄露。

    可用于：
    - 本地调试
    - FastAPI health
    - 团队集成检查
    """
    return {
        "project_root": str(
            PROJECT_ROOT
        ),
        "app_host": APP_HOST,
        "app_port": APP_PORT,

        "graph_source": GRAPH_SOURCE,

        "entities_source": str(
            ENTITIES_PATH
        ),

        "relations_source": str(
            RELATIONS_PATH
        ),

        "vector_backend": (
            VECTOR_BACKEND
        ),

        "milvus_uri": MILVUS_URI,

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