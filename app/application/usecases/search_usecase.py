from app.infrastructure.rag.reranker import SimpleReranker
from app.infrastructure.rag.retriever import HybridRetriever

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
_COMPOUND_SPLIT_MAP = {
    "채용공고": "채용 공고",
}


class SearchUseCase:
    def __init__(self, retriever: HybridRetriever, reranker: SimpleReranker) -> None:
        self._retriever = retriever
        self._reranker = reranker

    async def execute(self, user_id: int, query: str, top_k: int = 5) -> list[dict]:
        """Search-first retrieval with query normalization fallback."""
        queries = _build_search_queries(query)
        merged = []
        seen_queries = set()

        for candidate in queries:
            if candidate in seen_queries:
                continue
            seen_queries.add(candidate)

            raw_results = await self._retriever.retrieve(user_id, candidate, top_k * 2)
            merged = _merge_best_results(merged, raw_results)

            if len(self._reranker.rerank(merged, top_k)) >= top_k:
                break

        return self._reranker.rerank(merged, top_k)


def _build_search_queries(query: str) -> list[str]:
    base = query.strip()
    if not base:
        return []

    queries = [base]

    tokens = [_strip_trailing_punctuation(t) for t in base.split()]
    tokens = [t for t in tokens if t]
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

        split_tokens = [_split_known_compound_token(token) for token in core_tokens]
        split_query = " ".join(split_tokens)
        if split_query not in queries:
            queries.append(split_query)

    return queries


def _strip_trailing_punctuation(token: str) -> str:
    return token.rstrip(_TRAILING_PUNCTUATION)


def _split_known_compound_token(token: str) -> str:
    return _COMPOUND_SPLIT_MAP.get(token, token)


def _merge_best_results(existing: list[dict], incoming: list[dict]) -> list[dict]:
    best: dict[object, dict] = {}

    for result in existing + incoming:
        link_id = result.get("link_id")
        key = link_id if link_id is not None else (result.get("url"), result.get("title"))
        prev = best.get(key)
        if prev is None or result.get("similarity", 0) > prev.get("similarity", 0):
            best[key] = result

    return list(best.values())
