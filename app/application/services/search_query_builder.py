_TRAILING_PUNCTUATION = "!?.,:;)]}\"'”’"
_SEARCH_FILLER_TAILS = {
    "링크",
    "관련",
    "자료",
    "내용",
}
_SEARCH_COMMAND_TAILS = {
    "가져와",
    "가져와줘",
    "찾아줘",
    "보여줘",
    "알려줘",
    "줘",
    "좀",
}


def strip_trailing_punctuation(token: str) -> str:
    """Drop common sentence-ending punctuation from a token."""
    return token.rstrip(_TRAILING_PUNCTUATION)


def build_search_queries(query: str) -> list[str]:
    """Build a search-oriented query family shared across search entry points.

    The router may classify intent, but lexical fallback expansion should stay
    below the router so `/search`, natural-language search, and direct
    retriever callers all get the same rewrite behavior.
    """
    base = query.strip()
    if not base:
        return []

    queries = [base]

    tokens = [strip_trailing_punctuation(token) for token in base.split()]
    tokens = [token for token in tokens if token]
    if not tokens:
        return queries

    cleaned = " ".join(tokens)
    if cleaned not in queries:
        queries.append(cleaned)

    core_tokens = tokens[:]
    while core_tokens and core_tokens[-1] in (_SEARCH_FILLER_TAILS | _SEARCH_COMMAND_TAILS):
        core_tokens.pop()

    if core_tokens:
        core = " ".join(core_tokens)
        if core not in queries:
            queries.append(core)

        for size in range(len(core_tokens) - 1, 0, -1):
            progressive = " ".join(core_tokens[:size])
            if progressive not in queries:
                queries.append(progressive)

    return queries
