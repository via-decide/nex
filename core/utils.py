"""
Shared utilities across core modules to avoid duplication and ensure consistency.
"""

from __future__ import annotations

import re
from typing import Set


def tokenize(text: str) -> Set[str]:
    """Tokenize text into lowercase words of 3+ characters.

    Args:
        text: Input text to tokenize.

    Returns:
        A set of lowercase tokens containing only alphabetic words with
        a minimum length of three characters.

    Raises:
        None.
    """
    return set(re.findall(r"\b[a-z]{3,}\b", text.lower()))


STOP_WORDS: Set[str] = {
    "the", "and", "for", "that", "this", "with", "are", "was",
    "has", "have", "been", "from", "which", "they", "their",
    "can", "may", "also", "more", "will", "its", "not",
}


def claims_are_similar(a: str, b: str, threshold: float = 0.25) -> bool:
    """
    Compute Jaccard similarity between two claims.
    Uses consistent threshold of 0.25 across entire codebase.

    Args:
        a: First claim.
        b: Second claim.
        threshold: Jaccard index threshold (0.0-1.0).

    Returns:
        True if claims are similar enough.

    Raises:
        None.
    """
    ta = tokenize(a) - STOP_WORDS
    tb = tokenize(b) - STOP_WORDS
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= threshold
