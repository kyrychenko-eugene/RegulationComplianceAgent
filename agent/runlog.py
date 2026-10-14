"""Append-only run history: one JSON object per line in `runs.jsonl` (spec §7).

Two kinds of line: a run (a `RunResult`) and, when the judge runs in the background, a later judge record
`{"record": "judge", "run_id", ...}` that `read_runs` merges into the run with the same `run_id`.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import List, Optional

from common.config import ROOT
from common.schemas import JudgeInfo, RunResult, RunUsage

RUNS_PATH = ROOT / "runs.jsonl"
_LOCK = threading.Lock()  # the background judge thread appends to the same file


def _append_line(line: str, path: Path) -> None:
    with _LOCK, path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")  # one write call per line


def append_run(run: RunResult, path: Path = RUNS_PATH) -> None:
    _append_line(run.model_dump_json(), path)  # model_dump_json never emits raw newlines, so one line per run


def append_judge(run_id: str, judge: JudgeInfo, judge_ms: Optional[int], usage: RunUsage, finished_at: str,
                 path: Path = RUNS_PATH) -> None:
    record = {"record": "judge", "run_id": run_id, "finished_at": finished_at, "judge": judge.model_dump(),
              "judge_ms": judge_ms, "usage": usage.model_dump()}
    _append_line(json.dumps(record, ensure_ascii=False), path)


def read_runs(path: Path = RUNS_PATH) -> List[dict]:
    """Runs in file order, as dicts, with background judge records merged in (judge block, `judge_ms`, usage).

    A corrupt line is skipped; a judge record whose run is missing is ignored.
    """
    runs: List[dict] = []
    by_id: dict = {}
    if not path.exists():
        return runs
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("record") == "judge":
            run = by_id.get(obj.get("run_id"))
            if run is None:
                continue
            run["judge"] = obj.get("judge") or {}
            run.setdefault("timings", {})["judge_ms"] = obj.get("judge_ms")
            usage = run.setdefault("usage", {})
            for k, v in (obj.get("usage") or {}).items():
                usage[k] = round(usage.get(k, 0) + v, 6) if k == "cost_usd" else usage.get(k, 0) + v
            continue
        runs.append(obj)
        if obj.get("run_id"):
            by_id[obj["run_id"]] = obj
    return runs
