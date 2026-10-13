"""Configuration from `.env` (see `.env.example`)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "data" / "rules.json"
PROMPTS_DIR = ROOT / "prompts"

# Not configurable via .env; override per run with `python -m ingest --source <path|url>`.
SOURCE_PDF = "https://www.fca.org.uk/publication/policy/ps22-9.pdf"


@dataclass(frozen=True)
class Config:
    openai_api_key: str
    fast_model: str
    classifier_model: str
    classifier_threshold: float
    strong_model: str
    max_concurrency: int
    prompt_cache: bool


def load_config() -> Config:
    """Read the environment (and `.env`, which never overrides real env vars)."""
    load_dotenv(ROOT / ".env")
    env = os.environ.get
    return Config(
        openai_api_key=env("OPENAI_API_KEY", ""),
        fast_model=env("FAST_MODEL", "gpt-6-luna"),
        classifier_model=env("CLASSIFIER_MODEL", "gpt-6-luna"),
        classifier_threshold=float(env("CLASSIFIER_THRESHOLD", "0.2")),
        strong_model=env("STRONG_MODEL", "gpt-6.1-sol"),
        max_concurrency=int(env("MAX_CONCURRENCY", "5")),
        prompt_cache=env("PROMPT_CACHE", "on").strip().lower() == "on",
    )
