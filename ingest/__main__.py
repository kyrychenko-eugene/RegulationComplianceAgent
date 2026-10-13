"""`python -m ingest` — one-time build of `data/rules.json` from PS22/9 (PRIN 2A)."""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from common.config import RULES_PATH, SOURCE_PDF, Config, load_config
from common.llm import LLM
from common.prompts import prompt_version
from common.schemas import Meta, RulesFile
from ingest.extract import extract_rules
from ingest.filter import filter_provisions
from ingest.gate import gate_rules
from ingest.load import locate_prin2a, read_pdf_pages
from ingest.split import Provision, normalise, split_provisions

PROMPTS = ("ingest/filter", "ingest/extract", "ingest/critic")


class IngestIncomplete(RuntimeError):
    pass


def assert_quotes_verbatim(rules_file: RulesFile, prin2a: str) -> None:
    """Hard guarantee behind 'verbatim evidence': every approved quote is in the source."""
    source = normalise(prin2a)
    for r in rules_file.rules:
        if r.status == "approved":
            assert normalise(r.source_quote) in source, f"{r.id}: quote not found in source"
        else:
            assert r.rejection_reason, f"{r.id}: rejected without a reason"
    for d in rules_file.dropped_provisions:
        assert d.rationale.strip(), f"{d.provision_id}: dropped without a rationale"


async def run_ingest(
    config: Config,
    llm: LLM,
    pages: List[str],
    source_url: str,
    limit: Optional[int] = None,
    only: Optional[List[str]] = None,
) -> Tuple[RulesFile, dict]:
    """Raises IngestIncomplete if any extraction call failed (nothing is written then)."""
    prin2a = locate_prin2a(pages)
    provisions = split_provisions(prin2a)
    total = len(provisions)
    if only:
        provisions = [p for p in provisions if p.provision_id in only]
    if limit:
        provisions = provisions[:limit]
    print(f"split: {total} provisions ({len(provisions)} processed)", flush=True)

    kept, dropped, filter_failed = await filter_provisions(llm, provisions)
    print(f"filter: kept {len(kept)}, dropped {len(dropped)}, failed (kept) {len(filter_failed)}", flush=True)

    drafts, extract_failed = await extract_rules(llm, kept)
    if extract_failed:
        raise IngestIncomplete("extraction failed for: " + "; ".join(extract_failed))
    n_drafts = sum(len(d) for d in drafts)
    print(f"extract: {n_drafts} draft rules from {len(kept)} provisions", flush=True)

    rules = await gate_rules(llm, drafts, kept)
    approved = sum(r.status == "approved" for r in rules)
    print(f"gate: {approved} approved, {len(rules) - approved} rejected", flush=True)

    rules_file = RulesFile(
        meta=Meta(
            source="FCA PS22/9, Appendix 1 (Consumer Duty Instrument 2022, FCA 2022/31): PRIN 2A",
            source_url=source_url,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            strong_model=config.strong_model,
            prompt_versions={name: prompt_version(name) for name in PROMPTS},
        ),
        rules=rules,
        dropped_provisions=dropped,
    )
    assert_quotes_verbatim(rules_file, prin2a)

    stats = {
        "provisions_total": total,
        "provisions_processed": len(provisions),
        "provisions_kept": len(kept),
        "provisions_dropped": len(dropped),
        "kept_with_zero_rules": sum(1 for d in drafts if not d),
        "rules_approved": approved,
        "rules_rejected": len(rules) - approved,
        "by_severity": dict(Counter(r.severity for r in rules if r.status == "approved")),
        "by_scope": dict(Counter(r.scope for r in rules if r.status == "approved")),
        "tags": dict(Counter(t for r in rules if r.status == "approved" for t in r.tags)),
        "filter_failed_kept": filter_failed,
        "usage": {m: vars(u) for m, u in llm.total_usage.items()},
    }
    return rules_file, stats


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m ingest", description=__doc__)
    ap.add_argument("--limit", type=int, help="process only the first N provisions (dev)")
    ap.add_argument("--out", type=Path, default=RULES_PATH, help="output path")
    ap.add_argument("--only", help="comma-separated provision ids, e.g. 2A.2.3,2A.5.3 (dev)")
    ap.add_argument("--source", default=SOURCE_PDF, help="PDF path or URL (default: PS22/9 on fca.org.uk)")
    args = ap.parse_args(argv)

    config = load_config()
    if not config.openai_api_key:
        print("OPENAI_API_KEY is not set (see .env.example)", file=sys.stderr)
        return 2

    only = [x.strip() for x in args.only.split(",")] if args.only else None
    pages = read_pdf_pages(args.source)
    llm = LLM(config)
    try:
        rules_file, stats = asyncio.run(run_ingest(config, llm, pages, args.source, args.limit, only))
    except IngestIncomplete as e:
        print(f"not writing {args.out}: {e}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rules_file.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
