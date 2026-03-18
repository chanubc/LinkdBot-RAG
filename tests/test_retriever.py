import json
import pytest
from unittest.mock import AsyncMock
from app.infrastructure.rag.retriever import HybridRetriever


def make_retriever():
    openai = AsyncMock()
    openai.embed.return_value = [[0.1] * 5]
    chunk_repo = AsyncMock()
    chunk_repo.search_og_links.return_value = []
    chunk_repo.search_bm25.return_value = []
    return HybridRetriever(openai=openai, chunk_repo=chunk_repo), chunk_repo


def _make_result(link_id, title, keywords, dense_score, content_source="jina", similarity=None):
    return {
        "link_id": link_id,
        "title": title,
        "keywords": json.dumps(keywords),
        "dense_score": dense_score,
        "similarity": dense_score * 0.7 if similarity is None else similarity,
        "content_source": content_source,
        "url": f"https://example.com/{link_id}",
        "summary": "",
        "category": "AI",
        "chunk_content": "",
    }


@pytest.mark.asyncio
async def test_keyword_overlap_boosts_relevant_result():
    """키워드 매칭 결과가 dense-only 결과보다 높은 final_score를 받아야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "하나증권 AI 직무", ["하나증권", "AI직무", "채용공고", "금융", "취업"], dense_score=0.65),
        _make_result(2, "파이썬 로깅", ["Python", "로깅", "logging", "개발", "모범사례"], dense_score=0.72),
    ]

    results = await retriever.retrieve(user_id=111, query="하나증권 관련 공고", top_k=5)

    assert results[0]["link_id"] == 1, "하나증권 링크가 keyword 매칭으로 1위여야 함"


@pytest.mark.asyncio
async def test_og_source_has_lower_keyword_weight():
    """content_source='og'인 경우 keyword_weight가 0.1로 낮아야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(
            1,
            "테스트",
            ["하나증권", "채용"],
            dense_score=0.5,
            content_source="og",
            similarity=0.5,
        ),
    ]

    results = await retriever.retrieve(user_id=111, query="하나증권 채용", top_k=5)

    # og 가중치: 0.5 * 0.9 + 1.0 * 0.1 = 0.55
    assert abs(results[0]["similarity"] - 0.55) < 0.01


@pytest.mark.asyncio
async def test_jina_source_has_higher_keyword_weight():
    """content_source='jina'인 경우 keyword_weight가 0.3이어야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(
            1,
            "테스트",
            ["하나증권", "채용"],
            dense_score=0.5,
            content_source="jina",
            similarity=0.5,
        ),
    ]

    results = await retriever.retrieve(user_id=111, query="하나증권 채용", top_k=5)

    # jina 가중치: 0.5 * 0.7 + 1.0 * 0.3 = 0.65
    assert abs(results[0]["similarity"] - 0.65) < 0.01


@pytest.mark.asyncio
async def test_no_keyword_match_preserves_dense_order():
    """키워드 매칭 없으면 dense_score 기반 순서가 유지되어야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "A", ["alpha", "beta"], dense_score=0.9),
        _make_result(2, "B", ["gamma", "delta"], dense_score=0.8),
    ]

    results = await retriever.retrieve(user_id=111, query="xyz없는쿼리", top_k=5)

    assert results[0]["link_id"] == 1
    assert results[1]["link_id"] == 2


@pytest.mark.asyncio
async def test_invalid_keywords_json_handled_gracefully():
    """keywords JSON 파싱 실패 시 keyword_score=0으로 처리해야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        {**_make_result(1, "테스트", [], dense_score=0.8), "keywords": "INVALID_JSON"},
    ]

    results = await retriever.retrieve(user_id=111, query="테스트", top_k=5)

    assert len(results) == 1  # 에러 없이 결과 반환


@pytest.mark.asyncio
async def test_keywords_with_non_string_values_handled():
    """keywords에 숫자, None, dict 등 비문자값이 섞여 있어도 처리되어야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        {**_make_result(1, "테스트", [], dense_score=0.8),
         "keywords": json.dumps([1, "AI", None, {"x": 1}, "머신러닝"])},
    ]

    results = await retriever.retrieve(user_id=111, query="AI 머신러닝", top_k=5)

    assert len(results) == 1
    # 문자열 키워드 "AI", "머신러닝" 만 매칭되어야 함
    assert results[0]["similarity"] > 0.8 * 0.7  # keyword boost 적용됨


@pytest.mark.asyncio
async def test_keywords_not_a_list_handled():
    """keywords JSON이 list가 아닌 경우 keyword_score=0으로 처리해야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        {**_make_result(1, "테스트", [], dense_score=0.8),
         "keywords": json.dumps({"a": "b"})},
    ]

    results = await retriever.retrieve(user_id=111, query="테스트", top_k=5)

    assert len(results) == 1


@pytest.mark.asyncio
async def test_keywords_null_handled():
    """keywords가 null/None인 경우 keyword_score=0으로 처리해야 한다."""
    retriever, chunk_repo = make_retriever()
    result = _make_result(1, "테스트", [], dense_score=0.8)
    result["keywords"] = None
    chunk_repo.search_similar.return_value = [result]

    results = await retriever.retrieve(user_id=111, query="테스트", top_k=5)

    assert len(results) == 1


@pytest.mark.asyncio
async def test_same_link_deduped():
    """같은 link_id의 여러 chunk가 결과에 1개만 남아야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "하나증권 공고", ["하나증권", "채용공고"], dense_score=0.80, similarity=0.80),
        _make_result(1, "하나증권 공고", ["하나증권", "채용공고"], dense_score=0.75, similarity=0.75),
        _make_result(2, "파이썬 로깅", ["Python", "로깅"], dense_score=0.80, similarity=0.80),
    ]

    results = await retriever.retrieve(user_id=111, query="하나증권", top_k=5)

    link_ids = [r["link_id"] for r in results]
    assert link_ids.count(1) == 1, "link_id=1은 1번만 나와야 함"
    assert len(results) == 2


@pytest.mark.asyncio
async def test_spaced_query_matches_compound_keyword():
    """'하나 증권' (띄어쓰기) 쿼리가 '하나증권' (붙여쓰기) 키워드와 매칭되어야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "하나증권 공고", ["하나증권", "채용공고"], dense_score=0.50),
        _make_result(2, "무관한 문서", ["Python", "AI"], dense_score=0.70),
    ]

    results = await retriever.retrieve(user_id=111, query="하나 증권 공고", top_k=5)

    assert results[0]["link_id"] == 1, "하나증권 키워드 substring 매칭으로 1위여야 함"


@pytest.mark.asyncio
async def test_substring_match_partial_keyword():
    """query token '공고'가 keyword '채용공고'의 부분 문자열로 매칭되어야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "채용 정보", ["채용공고", "신입사원"], dense_score=0.50),
        _make_result(2, "무관 문서", ["Python", "로깅"], dense_score=0.65),
    ]

    results = await retriever.retrieve(user_id=111, query="공고", top_k=5)

    assert results[0]["link_id"] == 1, "공고 substring 매칭으로 채용공고 링크가 1위여야 함"



@pytest.mark.asyncio
async def test_low_similarity_tail_is_filtered_out():
    """상위 결과와 점수 차이가 큰 tail 결과는 잘려야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        {
            **_make_result(1, "하나증권 2026 신입사원 공개채용", ["하나증권", "채용공고"], dense_score=0.50),
            "category": "Career",
        },
        {
            **_make_result(2, "하나증권 AI 직무 분석", ["하나증권", "AI직무"], dense_score=0.50),
            "category": "AI",
        },
        {
            **_make_result(3, "파이썬 로깅", ["Python", "로깅"], dense_score=0.35),
            "category": "Dev",
        },
    ]

    results = await retriever.retrieve(user_id=111, query="하나증권 공고", top_k=5)

    assert [r["link_id"] for r in results] == [1, 2]


@pytest.mark.asyncio
async def test_recall_k_is_wider_than_top_k():
    """DB 조회 시 recall_k가 top_k보다 충분히 크게 호출되어야 한다."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = []

    await retriever.retrieve(user_id=111, query="테스트", top_k=5)

    called_top_k = chunk_repo.search_similar.call_args[0][2]
    assert called_top_k > 5


@pytest.mark.asyncio
async def test_low_dense_rank_rises_via_keyword_overlap():
    """dense 순위는 낮지만 keyword 매칭으로 최종 top_k 안에 들어오는 케이스."""
    retriever, chunk_repo = make_retriever()

    # DB는 dense 기준 B(0.80) > A(0.50) 순으로 반환
    chunk_repo.search_similar.return_value = [
        _make_result(2, "B dense top", ["random", "stuff"], dense_score=0.80),
        _make_result(1, "A keyword match", ["하나증권", "채용", "금융", "취업", "AI"], dense_score=0.50),
    ]

    # top_k=1로 요청 — dense만 보면 B가 1등
    results = await retriever.retrieve(user_id=111, query="하나증권 채용", top_k=1)

    # keyword 매칭 덕분에 A가 1등
    # A: 0.50 * 0.7 + (2/2) * 0.3 = 0.35 + 0.30 = 0.65
    # B: 0.80 * 0.7 + 0.0  * 0.3  = 0.56
    assert results[0]["link_id"] == 1
    assert len(results) == 1


@pytest.mark.asyncio
async def test_og_link_without_chunks_appears_via_summary_embedding():
    """chunks가 없는 OG 링크가 summary_embedding 경로로 검색 결과에 포함되어야 한다."""
    retriever, chunk_repo = make_retriever()

    # chunk 경로: Jina 링크만 반환
    chunk_repo.search_similar.return_value = [
        _make_result(1, "Jina 링크", ["AI", "Python"], dense_score=0.8, content_source="jina"),
    ]
    # summary_embedding 경로: OG 링크 반환 (chunks 없는 링크)
    chunk_repo.search_og_links.return_value = [
        _make_result(2, "OG 링크", ["Career", "채용"], dense_score=0.7, content_source="og"),
    ]

    results = await retriever.retrieve(user_id=111, query="AI 채용", top_k=5)

    link_ids = [r["link_id"] for r in results]
    assert 1 in link_ids, "Jina 링크(chunk 경로)가 결과에 포함되어야 함"
    assert 2 in link_ids, "OG 링크(summary_embedding 경로)가 결과에 포함되어야 함"


@pytest.mark.asyncio
async def test_og_link_deduped_when_also_in_chunks():
    """OG 링크가 두 경로 모두에서 반환될 경우 중복 제거 후 1개만 남아야 한다."""
    retriever, chunk_repo = make_retriever()

    chunk_repo.search_similar.return_value = [
        _make_result(1, "링크", ["AI"], dense_score=0.8, content_source="og"),
    ]
    chunk_repo.search_og_links.return_value = [
        _make_result(1, "링크", ["AI"], dense_score=0.75, content_source="og"),
    ]

    results = await retriever.retrieve(user_id=111, query="AI", top_k=5)

    assert [r["link_id"] for r in results].count(1) == 1, "같은 link_id는 1개만 나와야 함"


@pytest.mark.asyncio
async def test_og_links_empty_when_no_summary_embeddings():
    """search_og_links가 빈 결과를 반환해도 chunk 결과는 정상 반환되어야 한다."""
    retriever, chunk_repo = make_retriever()

    chunk_repo.search_similar.return_value = [
        _make_result(1, "Jina 링크", ["AI"], dense_score=0.8),
    ]
    chunk_repo.search_og_links.return_value = []

    results = await retriever.retrieve(user_id=111, query="AI", top_k=5)

    assert len(results) == 1
    assert results[0]["link_id"] == 1


@pytest.mark.asyncio
async def test_title_entity_match_boosts_result():
    """브랜드명이 keywords에 없고 title에만 있어도 해당 링크가 1위여야 한다.

    "롯데"가 keywords에 없더라도 title "롯데이노베이트..."에서 매칭되어
    dense가 약간 낮은 하나증권보다 높게 랭킹되어야 한다.
    """
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        # 하나증권: dense 높지만 "롯데" 없음
        _make_result(2, "하나증권 2026 신입사원 공개채용",
                     ["하나증권", "채용공고", "금융", "신입", "취업"], dense_score=0.55),
        # 롯데이노베이트: dense 낮지만 title에 "롯데" 있음 (keywords엔 없음)
        _make_result(1, "롯데이노베이트 2026 신입 공채",
                     ["채용공고", "신입사원", "IT서비스", "취업", "공고"], dense_score=0.50),
    ]

    results = await retriever.retrieve(user_id=111, query="롯데 채용", top_k=5)

    assert results[0]["link_id"] == 1, "title에 '롯데' 있는 링크가 1위여야 함"


@pytest.mark.asyncio
async def test_title_match_works_even_when_keywords_missing():
    """keywords가 비어도 title 매칭으로 overlap 점수가 계산되어야 한다."""
    retriever, chunk_repo = make_retriever()
    no_keyword = _make_result(1, "롯데이노베이트 채용", [], dense_score=0.50)
    no_keyword["keywords"] = None
    unrelated = _make_result(2, "하나증권 채용", [], dense_score=0.55)
    unrelated["keywords"] = None
    chunk_repo.search_similar.return_value = [unrelated, no_keyword]

    results = await retriever.retrieve(user_id=111, query="롯데 채용", top_k=5)

    assert results[0]["link_id"] == 1


@pytest.mark.asyncio
async def test_db_fts_signal_preserved_in_reranking():
    """DB의 FTS(sparse) 점수가 retriever 재랭킹에서 사라지지 않아야 한다.

    query와 keyword/title 매칭이 둘 다 없는 상황에서,
    DB similarity(dense*0.7 + sparse*0.3)를 base로 사용하면
    FTS가 올려준 link1이 dense만 높은 link2보다 높은 최종 순위를 받아야 한다.
    """
    retriever, chunk_repo = make_retriever()

    # link1: dense 낮지만 FTS가 올려줘서 DB similarity 높음
    link1 = {**_make_result(1, "문서 알파", ["알파", "베타", "감마"], dense_score=0.40)}
    link1["similarity"] = 0.65  # FTS boost

    # link2: dense 높지만 FTS 없음 → similarity ≈ dense*0.7
    link2 = {**_make_result(2, "문서 델타", ["델타", "엡실론", "제타"], dense_score=0.58)}
    link2["similarity"] = 0.41

    chunk_repo.search_similar.return_value = [link2, link1]  # DB dense 기준 2→1

    # query가 두 링크 keywords/title 모두에 매칭 안 됨 → overlap=0, base score만으로 승부
    results = await retriever.retrieve(user_id=111, query="무관한XYZ검색어", top_k=5)

    # FTS 보존: similarity 기준 link1(0.65) > link2(0.41) → link1 1위
    # FTS 미보존: dense 기준 link2(0.58) > link1(0.40) → link2 1위
    assert results[0]["link_id"] == 1, "FTS boost된 link1이 1위여야 함"


# ===== Korean-specific tests for particle stripping =====


@pytest.mark.asyncio
async def test_korean_particle_attached_query_matches_keyword():
    """Particle-attached query '채용공고를' should match keyword '채용공고'.

    Demonstrates: _token_matches now handles particle-stripped exact match.
    """
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "채용 정보", ["채용공고", "신입사원"], dense_score=0.50),
        _make_result(2, "무관 문서", ["Python", "로깅"], dense_score=0.65),
    ]

    # Query has particle "를" attached
    results = await retriever.retrieve(user_id=111, query="채용공고를", top_k=5)

    # Particle-stripped '채용공고' should match keyword exactly → boost link1 above link2
    assert results[0]["link_id"] == 1, "Particle-attached query should match stripped keyword"


@pytest.mark.asyncio
async def test_korean_particle_attached_query_matches_title():
    """Particle-attached query '롯데에서' should match title containing '롯데'.

    Demonstrates: Title matching now benefits from particle stripping in query variants.
    """
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "롯데이노베이트 채용공고", ["채용", "신입", "공고"], dense_score=0.50),
        _make_result(2, "하나증권 채용공고", ["하나증권", "채용"], dense_score=0.60),
    ]

    # Query "롯데에서" should strip to "롯데" → match in title
    results = await retriever.retrieve(user_id=111, query="롯데에서", top_k=5)

    assert results[0]["link_id"] == 1, "Particle-stripped query should match title"




@pytest.mark.asyncio
async def test_korean_mixed_korean_english_with_particles():
    """Mixed Korean/English query 'AI개발자를' should match 'AI개발자' keyword.

    Demonstrates: Particle stripping works on mixed text.
    """
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "AI 개발", ["AI개발자", "신입", "기술"], dense_score=0.50),
        _make_result(2, "웹개발", ["웹개발", "풀스택"], dense_score=0.60),
    ]

    # 'AI개발자를' should strip to 'AI개발자' → match keyword
    results = await retriever.retrieve(user_id=111, query="AI개발자를", top_k=5)

    assert results[0]["link_id"] == 1, "Mixed Korean/English query should strip particles"


@pytest.mark.asyncio
async def test_korean_over_match_prevention():
    """Prevent over-matching: query '하나 증권 공고' compact variant should NOT over-match '증권'.

    Demonstrates: Conditional bidirectional matching prevents compact variant over-matching.

    Query variants: "하나 증권 공고", "하나증권공고", "하나증권 공고", ...
    When matching against keywords, "하나증권" should be matched (exact after strip),
    but NOT "증권" alone (would be kw-in-qt, which we restrict).
    """
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "증권 분석", ["증권", "투자", "분석"], dense_score=0.50),
        _make_result(2, "하나증권 채용", ["하나증권", "채용공고"], dense_score=0.50),
    ]

    # Query "하나 증권 공고" generates variants including "하나증권공고"
    # Matching: "하나증권공고" should match "하나증권" (not "증권" alone)
    results = await retriever.retrieve(user_id=111, query="하나 증권 공고", top_k=5)

    # With equal dense scores, proper keyword match should boost link2
    assert results[0]["link_id"] == 2, "Over-match prevention: '증권' alone should not match"


@pytest.mark.asyncio
async def test_korean_particle_stripping_score_range():
    """Particle stripping should produce a meaningful score boost over no-match baseline.

    Regression guard: ensures the final_score after particle-based keyword boost
    stays within expected range and meaningfully exceeds the unmatched document.
    """
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "NH투자증권 신입 공채", ["채용공고", "nh투자증권", "신입"], dense_score=0.58),
        _make_result(2, "무관 문서", ["Python", "백엔드"], dense_score=0.58),
    ]

    results = await retriever.retrieve(user_id=111, query="채용공고를 찾아줘", top_k=5)

    assert results[0]["link_id"] == 1, "Particle-stripped keyword match should rank link1 first"

    top_score = results[0]["similarity"]
    # _make_result sets similarity = dense_score * 0.7 = 0.406 (base_score)
    # _rescore: final = 0.406 * 0.7 + overlap * 0.3
    # With overlap=0.5 ("채용공고를"→"채용공고" matches): 0.406*0.7 + 0.5*0.3 = 0.434
    # Without particle stripping (overlap=0): 0.406 * 0.7 = 0.284
    assert 0.40 <= top_score <= 0.55, f"Expected score in [0.40, 0.55], got {top_score}"

    # Boosted doc should score meaningfully higher than unmatched doc
    if len(results) >= 2:
        assert results[0]["similarity"] > results[1]["similarity"], (
            "Particle-matched doc should score higher than unmatched doc"
        )


@pytest.mark.asyncio
async def test_bare_noun_particle_suffix_does_not_overmatch_other_brand():
    """Brands ending in particle-like syllables should not be stripped into other brands."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "하나증권 채용", ["하나증권", "채용"], dense_score=0.60),
        _make_result(2, "하나로 채용", ["하나로", "채용"], dense_score=0.55),
    ]

    results = await retriever.retrieve(user_id=111, query="하나로 채용", top_k=5)

    assert results[0]["link_id"] == 2, "Bare noun '하나로' should not be stripped to unrelated '하나'"


@pytest.mark.asyncio
async def test_particle_query_with_trailing_punctuation_still_matches():
    """Trailing punctuation should not prevent particle-stripped matching."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "채용 정보", ["채용공고", "신입사원"], dense_score=0.50),
        _make_result(2, "무관 문서", ["Python", "로깅"], dense_score=0.65),
    ]

    results = await retriever.retrieve(user_id=111, query="채용공고를?", top_k=5)

    assert results[0]["link_id"] == 1, "Trailing punctuation should not drop particle-stripped keyword boost"


@pytest.mark.asyncio
async def test_non_kiwi_bm25_path_recovers_relevant_link_when_dense_misses():
    """BM25 fallback should recover a lexical match even when dense/OG paths return nothing."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = []
    chunk_repo.search_og_links.return_value = []
    chunk_repo.search_bm25.return_value = [
        {
            **_make_result(1, "채용공고 링크 모음", ["채용공고", "링크"], dense_score=0.0),
            "summary": "채용공고 링크를 빠르게 찾는 모음집",
            "chunk_content": "채용공고 링크 정리",
            "similarity": 0.82,
            "bm25_score": 0.82,
        },
    ]

    results = await retriever.retrieve(user_id=111, query="채용공고 링크", top_k=5)

    assert [r["link_id"] for r in results] == [1]
    chunk_repo.search_bm25.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_kiwi_bm25_query_normalizes_particles_before_search():
    """BM25 query should use raw non-Kiwi normalization such as particle stripping."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = []
    chunk_repo.search_og_links.return_value = []
    chunk_repo.search_bm25.return_value = []

    await retriever.retrieve(user_id=111, query="채용공고를 찾아줘", top_k=5)

    called_query = chunk_repo.search_bm25.await_args.args[1]
    assert called_query == "채용공고 찾아줘"
