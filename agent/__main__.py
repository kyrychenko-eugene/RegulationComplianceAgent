"""`python -m agent "<text>"` or `--file path`: check one marketing text, print the Markdown report."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import agent
from agent.report import build_report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agent", description="Check a marketing text against PRIN 2A.")
    ap.add_argument("text", nargs="?", help="the marketing text")
    ap.add_argument("--file", help="read the marketing text from this file")
    ap.add_argument("--json", metavar="OUT", help="also write the full RunResult as JSON to OUT")
    ap.add_argument("--no-log", action="store_true", help="do not append to runs.jsonl")
    args = ap.parse_args(argv)
    if (args.text is None) == (args.file is None):
        ap.error("give either the text or --file")
    if args.file:
        try:
            text = Path(args.file).read_text(encoding="utf-8")
        except OSError as e:
            print(f"cannot read {args.file}: {e}", file=sys.stderr)
            return 2
    else:
        text = args.text

    kwargs = {"log_path": None} if args.no_log else {}
    run = agent.check(text, **kwargs)
    markdown, json_text = build_report(run)
    print(markdown)
    if args.json:
        Path(args.json).write_text(json_text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
