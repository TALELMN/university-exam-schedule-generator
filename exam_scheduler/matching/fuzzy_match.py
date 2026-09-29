"""Conservative suggestions for likely OCR mistakes in course codes."""

from __future__ import annotations

import re

try:
    from rapidfuzz import fuzz, process
except ImportError:
    fuzz = None
    process = None


def _ocr_variants(code: str) -> list[str]:
    code = code.upper()
    variants = []
    for split in range(2, min(6, len(code) - 2)):
        prefix, suffix = code[:split], code[split:]
        if (re.fullmatch(r"[A-Z]{2,5}", prefix) and 3 <= len(suffix) <= 4
                and re.search(r"\d", suffix) and re.search(r"[IO]", suffix)):
            variants.append(prefix + suffix.replace("I", "1").replace("O", "0").replace("L", "1"))
    return variants or [code]


def suggest_course_code(detected: str, candidates: list[str], threshold: int = 88) -> tuple[str, int] | None:
    """Return the best plausible candidate and confidence, never a silent edit."""
    normalized_candidates = list(dict.fromkeys(c.upper() for c in candidates if c))
    if not normalized_candidates:
        return None
    detected = detected.upper()
    for variant in _ocr_variants(detected):
        if variant != detected and variant in normalized_candidates:
            return (variant, 96) if 96 >= threshold else None
    if process is not None:
        found = process.extractOne(detected, normalized_candidates, scorer=fuzz.ratio)
        if found and found[1] >= threshold:
            return found[0], int(round(found[1]))
    else:
        import difflib
        candidate = max(normalized_candidates, key=lambda item: difflib.SequenceMatcher(None, detected, item).ratio())
        confidence = round(difflib.SequenceMatcher(None, detected, candidate).ratio() * 100)
        if confidence >= threshold:
            return candidate, confidence
    return None
