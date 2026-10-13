"""Append-only run history: one JSON object per line in `runs.jsonl` (spec §7)."""
from __future__ import annotations

from pathlib import Path

from common.config import ROOT
from common.schemas import RunResult

RUNS_PATH = ROOT / "runs.jsonl"


def append_run(run: RunResult, path: Path = RUNS_PATH) -> None:
    line = run.model_dump_json()  # model_dump_json never emits raw newlines, so one line per run
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
