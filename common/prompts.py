"""Prompts are documents: each lives in `prompts/` as its own `.md` file."""
from __future__ import annotations

import hashlib

from common.config import PROMPTS_DIR


def load_prompt(name: str) -> str:
    """`name` is the path under `prompts/` without extension, e.g. `ingest/filter`."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def prompt_version(name: str) -> str:
    """Short content hash, recorded in `rules.json` meta."""
    return hashlib.sha256(load_prompt(name).encode("utf-8")).hexdigest()[:8]
