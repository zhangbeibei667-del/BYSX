from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


# 项目根目录：避免 VSCode / PowerShell 工作目录变化导致路径失效
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 自动读取项目根目录下的 .env
load_dotenv(PROJECT_ROOT / ".env")

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8003"))

# Mock 数据路径
ENTITIES_PATH = PROJECT_ROOT / "data" / "entities.json"
RELATIONS_PATH = PROJECT_ROOT / "data" / "relations.json"
DOCS_DIR = PROJECT_ROOT / "data" / "docs"

# 是否调用真实大模型
LLM_ENABLED = os.getenv("LLM_ENABLED", "false").lower() == "true"

# DeepSeek / OpenAI-compatible Chat Completions
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
