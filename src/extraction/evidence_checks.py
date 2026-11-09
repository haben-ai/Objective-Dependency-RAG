"""Deterministic checks that a quoted piece of evidence really occurs in the text it claims to come from.

These checks are applied identically to the output of all three approaches (so the unsupported-claim rate is
comparable), and are also used inside the verification approach.
"""

import re
import unicodedata
from difflib import SequenceMatcher

MIN_QUOTE_CHARS = 6
FUZZY_THRESHOLD = 0.9


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[`'\"“”‘’]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def quote_in(quote: str | None, text: str) -> bool:
    """True if `quote` occurs in `text`, allowing whitespace/quote-mark differences and minor OCR noise."""
    if not quote:
        return False
    q, t = normalize(quote), normalize(text)
    if len(q) < MIN_QUOTE_CHARS:
        return False
    if q in t:
        return True
    # Sliding-window fuzzy match for small transcription differences (e.g. PDF-extracted formulas).
    n = len(q)
    step = max(1, n // 4)
    best = 0.0
    for i in range(0, max(1, len(t) - n + 1), step):
        best = max(best, SequenceMatcher(None, q, t[i : i + n]).ratio())
        if best >= FUZZY_THRESHOLD:
            return True
    return False


def check_dependency(dep, description: str, passages: dict[str, str]) -> dict:
    """Return where the dependency's quote can actually be found.

    Result keys: quote_in_description, quote_in_cited_passage, quote_found_in (passage id or None),
    supported (bool: the quote was found somewhere the method had access to).
    """
    in_desc = quote_in(dep.evidence, description)
    cited = dep.source_chunk_id
    in_cited = bool(cited and cited in passages and quote_in(dep.evidence, passages[cited]))
    found_in = cited if in_cited else next((cid for cid, txt in passages.items() if quote_in(dep.evidence, txt)), None)
    return {
        "quote_in_description": in_desc,
        "cited_passage_exists": bool(cited and cited in passages),
        "quote_in_cited_passage": in_cited,
        "quote_found_in": found_in,
        "supported": in_desc or found_in is not None,
    }
