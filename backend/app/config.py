"""Settings read from environment variables (and backend/.env when present)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
INDEX_DIR = DATA_DIR / "index"
SOURCES_FILE = DATA_DIR / "sources.json"
EVAL_DIR = BACKEND_DIR / "eval"

load_dotenv(BACKEND_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    azure_endpoint: str
    azure_api_key: str
    azure_api_version: str
    chat_deployment: str
    embedding_deployment: str
    use_fake_llm: bool
    top_k: int
    min_score: float


def get_settings() -> Settings:
    return Settings(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "").strip(),
        azure_api_key=os.getenv("AZURE_OPENAI_API_KEY", "").strip(),
        azure_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21").strip(),
        chat_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "").strip(),
        embedding_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "").strip(),
        use_fake_llm=os.getenv("USE_FAKE_LLM", "0").strip() in {"1", "true", "True"},
        top_k=int(os.getenv("TOP_K", "4")),
        min_score=float(os.getenv("MIN_SCORE", "0.25")),
    )
