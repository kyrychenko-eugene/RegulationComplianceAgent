"""Split the PRIN 2A text into provisions: `{provision_id, marker, section, text}`."""
from __future__ import annotations

import re
from typing import List

from pydantic import BaseModel

from common.schemas import Marker

PROVISION_RE = re.compile(r"^(2A\.\d+\.\d+)\s+([REG])\b\s*(.*)$")
SECTION_RE = re.compile(r"^(2A\.\d+)\s+([A-Z].*)$")
# Sub-headings in the PDF are indented by exactly one space and carry no final punctuation.
SUBHEADING_RE = re.compile(r"^ [A-Z][^\n]{0,100}[^.;:,\s]\s*$")


class Provision(BaseModel):
    provision_id: str  # e.g. "2A.5.3"
    marker: Marker
    section: str  # e.g. "2A.5 Communications that support understanding"
    text: str  # whitespace-normalised, includes the sub-paragraph labels


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_provisions(prin2a: str) -> List[Provision]:
    provisions: List[Provision] = []
    section = ""
    current = None  # (id, marker, section, [lines])

    def flush() -> None:
        if current:
            pid, marker, sec, lines = current
            provisions.append(
                Provision(provision_id=pid, marker=marker, section=sec, text=normalise(" ".join(lines)))
            )

    in_subheading = False
    for line in prin2a.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "…":
            continue
        m = PROVISION_RE.match(stripped)
        if m:
            in_subheading = False
            flush()
            current = (m.group(1), m.group(2), section, [m.group(3)])
            continue
        s = SECTION_RE.match(stripped)
        if s and not line.startswith(" "):
            in_subheading = False
            flush()
            current = None
            section = stripped
            continue
        if SUBHEADING_RE.match(line):
            in_subheading = True
            continue  # "Application", "Purpose", ... belong to no provision
        if in_subheading:
            continue  # wrapped second line of a sub-heading; a provision always follows
        if current:
            current[3].append(stripped)
    flush()
    return provisions
