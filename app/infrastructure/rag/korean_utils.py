"""Korean language utilities for particle stripping."""

# Korean particles (조사) commonly attached to nouns
_PARTICLES = {
    "을", "를", "이", "가", "은", "는",  # Object/Subject markers
    "에", "에서", "으로", "로",  # Location/Direction
    "의",  # Possessive
    "와", "과", "도", "만",  # Addition
    "까지", "부터", "처럼", "보다",  # Range/Comparison
    "에게", "한테", "께서",  # Indirect object
}


def strip_particles(token: str) -> str:
    """Remove Korean particles from the end of a token.

    Tries longest-match suffix removal from _PARTICLES.
    Returns stripped form if remaining length >= 2, else returns original.

    Examples:
        "채용공고를" → "채용공고"
        "증권에서" → "증권"
        "을" → "을" (too short after strip)
        "AI" → "AI" (no particle)
    """
    if not token:
        return token

    # Try longest matching particles first (for multi-character particles like "에서")
    for particle in sorted(_PARTICLES, key=len, reverse=True):
        if token.endswith(particle):
            stripped = token[: -len(particle)]
            # Keep stripped form only if it's 2+ characters
            if len(stripped) >= 2:
                return stripped

    # No particle matched, or stripped form too short
    return token


def normalize_korean_query(query: str) -> list[str]:
    """Normalize Korean query by stripping particles from each token.

    Note: Alias expansion is handled separately in _build_query_variants.
    This function only strips particles.

    Examples:
        "채용공고를 찾습니다" → ["채용공고", "찾합니다"] or similar
        "하나 증권" → ["하나", "증권"]
    """
    if not query or not query.strip():
        return []

    tokens = query.strip().split()
    normalized = []

    for token in tokens:
        if token:
            # Strip particles from each token only
            stripped = strip_particles(token)
            normalized.append(stripped)

    return normalized
