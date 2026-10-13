"""Load the source PDF and locate PRIN 2A inside Appendix 1 by heading search."""
from __future__ import annotations

import io
import re
from typing import List

import httpx
from pypdf import PdfReader

APPENDIX_RE = re.compile(r"^Appendix 1\s*$", re.M)
CHAPTER_RE = re.compile(r"^2A\s+The Consumer Duty\s*$", re.M)
# The first instruction line after the chapter marks where the inserted PRIN 2A text ends.
CHAPTER_END_RE = re.compile(
    r"^(Amend the following|Insert the following|Delete the following|Annex [A-Z]\s*$)", re.M
)
NOISE_LINE_RE = re.compile(r"^(FCA 2022/31|Page \d+ of \d+)\s*$")


class SourceError(RuntimeError):
    pass


def open_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def read_pdf_pages(source: str) -> List[str]:
    """`source` is a local path or an http(s) URL."""
    if source.startswith(("http://", "https://")):
        resp = httpx.get(source, follow_redirects=True, timeout=120)
        resp.raise_for_status()
        data = io.BytesIO(resp.content)
    else:
        data = io.BytesIO(open_bytes(source))
    reader = PdfReader(data)
    return [page.extract_text() or "" for page in reader.pages]


def locate_prin2a(pages: List[str]) -> str:
    """Return the cleaned text of the PRIN 2A chapter from Appendix 1.

    Heading search, no page numbers: find the Appendix 1 cover page, then the
    `2A The Consumer Duty` chapter heading after it, up to the next instruction.
    """
    start_page = next(
        (i for i, p in enumerate(pages) if APPENDIX_RE.search(p) and "Made rules" in p), None
    )
    if start_page is None:
        raise SourceError("Appendix 1 (Made rules) heading not found in the source")
    text = "\n".join(pages[start_page:])
    m = CHAPTER_RE.search(text)
    if m is None:
        raise SourceError("PRIN 2A chapter heading not found after Appendix 1")
    body = text[m.end():]
    end = CHAPTER_END_RE.search(body)
    if end is None:
        raise SourceError("End of the PRIN 2A chapter not found")
    body = body[: end.start()]
    lines = [ln for ln in body.splitlines() if not NOISE_LINE_RE.match(ln.strip())]
    return "\n".join(lines)
