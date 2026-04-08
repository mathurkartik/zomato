from __future__ import annotations


def cuisine_tokens_equivalent(a: str, b: str) -> bool:
    """Exact match or common Zomato synonyms (coffee <-> cafe)."""
    a = a.strip().lower()
    b = b.strip().lower()
    if a == b:
        return True
    if {a, b} == {"coffee", "cafe"}:
        return True
    return False
