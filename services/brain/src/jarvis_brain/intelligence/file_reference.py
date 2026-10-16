"""Displayed-result references are addresses in a page, never filesystem search terms."""

from __future__ import annotations

import re


def numbered_reference(text: str) -> int | None:
    """Recognize numeric list notation without inferring an action from the sentence.

    A reference constrains later semantic planning; it never authorizes opening. Ordinary
    quantities and filenames (2 tane, 2.pdf, 2026 raporu) remain ordinary model input.
    """
    value = text.casefold().replace("\u0307", "")
    marked = re.match(r"^\s*([+-]?\d+)\s*[.)](?:\s+|$)", value)
    if marked:
        return int(marked[1])
    plain = re.match(r"^\s*([+-]?\d+)(?:\s+|$)", value)
    if plain and (
        not value[plain.end() :].strip()
        or re.match(
            r"(?:olan|numara|nolu|no\b|sıra|sira|aç\b|açar\b|ac\b|acar\b|open\b)",
            value[plain.end() :].lstrip(),
        )
    ):
        return int(plain[1])
    return None
