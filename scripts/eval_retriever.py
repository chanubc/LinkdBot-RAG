"""검색 성능 평가 스크립트.

비교 기준:
  Dense-only : 벡터 유사도만 사용 (PR#68 이전)
  PR#68      : keyword exact-match 재점수화 (오늘 이전)
  Today      : query 변형 + substring 매칭 + link dedupe (오늘 적용)

사용법:
    python scripts/eval_retriever.py          # mock 데이터로 실행
    python scripts/eval_retriever.py --real   # 실제 DB 연결 (환경변수 필요)
"""

import io
import json
import math
import sys
from dataclasses import dataclass

# Windows cp949 터미널 대응
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ─── 평가 지표 ────────────────────────────────────────────────────────────────

def precision_at_k(ranked_ids: list[int], relevant_ids: set[int], k: int) -> float:
    top_k = ranked_ids[:k]
    return len(set(top_k) & relevant_ids) / k if k else 0.0


def reciprocal_rank(ranked_ids: list[int], relevant_ids: set[int]) -> float:
    for rank, link_id in enumerate(ranked_ids, start=1):
        if link_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids: list[int], relevant_ids: set[int], k: int) -> float:
    def dcg(ids):
        return sum(
            1.0 / math.log2(i + 2)
            for i, lid in enumerate(ids[:k])
            if lid in relevant_ids
        )

    ideal_hits = min(len(relevant_ids), k)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg(ranked_ids) / ideal if ideal else 0.0


# ─── 검색 로직 재현 ───────────────────────────────────────────────────────────

_KEYWORD_WEIGHT_JINA = 0.3
_KEYWORD_WEIGHT_OG = 0.1


def dense_only_rank(candidates: list[dict]) -> list[int]:
    """Dense-only: dense_score만으로 정렬 (PR#68 이전)."""
    sorted_c = sorted(candidates, key=lambda r: r.get("dense_score", 0), reverse=True)
    return [r["link_id"] for r in sorted_c]


def pr68_rank(candidates: list[dict], query: str) -> list[int]:
    """PR#68: keyword exact-match 재점수화. 중복 제거 없음."""
    query_tokens = {t.lower() for t in query.split() if t}
    if not query_tokens:
        return dense_only_rank(candidates)

    rescored = []
    for r in candidates:
        dense_score = r.get("dense_score", 0)
        keyword_weight = (
            _KEYWORD_WEIGHT_JINA if r.get("content_source") == "jina"
            else _KEYWORD_WEIGHT_OG
        )
        overlap = 0.0
        raw_keywords = r.get("keywords")
        if raw_keywords:
            try:
                parsed = json.loads(raw_keywords)
                if isinstance(parsed, list):
                    link_keywords = {k.lower() for k in parsed if isinstance(k, str) and k.strip()}
                    overlap = len(query_tokens & link_keywords) / len(query_tokens)
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        final_score = dense_score * (1 - keyword_weight) + overlap * keyword_weight
        rescored.append({**r, "final_score": round(final_score, 4)})

    return [r["link_id"] for r in sorted(rescored, key=lambda x: x["final_score"], reverse=True)]


def _build_query_variants(query: str) -> list[str]:
    """원문 + 공백제거본 + bi-gram 결합본. 예: '하나 증권 공고' → 4가지 변형."""
    base = query.strip()
    variants = [base]
    compact = "".join(base.split())
    if compact and compact not in variants:
        variants.append(compact)
    tokens = base.split()
    for i in range(len(tokens) - 1):
        combined = tokens[i] + tokens[i + 1]
        variant = " ".join(tokens[:i] + [combined] + tokens[i + 2:])
        if variant not in variants:
            variants.append(variant)
    return variants


def _token_matches(query_token: str, keyword: str) -> bool:
    """부분 문자열 포함 여부. query_token이 keyword 안에 있는 방향만 허용.

    keyword in query_token 방향은 compact variant에서 과도한 boost를 유발하므로 제외.
    """
    q = query_token.lower()
    k = keyword.lower()
    if q == k:
        return True
    if len(q) >= 2 and q in k:
        return True
    return False


def today_rank(candidates: list[dict], query: str) -> list[int]:
    """Today: query 변형 + substring 매칭 + link_id dedupe."""
    all_token_sets = [
        {t.lower() for t in v.split() if t}
        for v in _build_query_variants(query)
    ]
    if not any(all_token_sets):
        return dense_only_rank(candidates)

    rescored = []
    for r in candidates:
        dense_score = r.get("dense_score", 0)
        keyword_weight = (
            _KEYWORD_WEIGHT_JINA if r.get("content_source") == "jina"
            else _KEYWORD_WEIGHT_OG
        )
        overlap = 0.0
        raw_keywords = r.get("keywords")
        if raw_keywords:
            try:
                parsed = json.loads(raw_keywords)
                if isinstance(parsed, list):
                    link_keywords = [k.lower() for k in parsed if isinstance(k, str) and k.strip()]
                    best_overlap = 0.0
                    for query_tokens in all_token_sets:
                        if not query_tokens:
                            continue
                        matched = sum(
                            1 for qt in query_tokens
                            if any(_token_matches(qt, kw) for kw in link_keywords)
                        )
                        variant_overlap = matched / len(query_tokens)
                        if variant_overlap > best_overlap:
                            best_overlap = variant_overlap
                    overlap = best_overlap
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        final_score = dense_score * (1 - keyword_weight) + overlap * keyword_weight
        rescored.append({**r, "final_score": round(final_score, 4)})

    sorted_r = sorted(rescored, key=lambda x: x["final_score"], reverse=True)
    # link_id dedupe
    seen: set[int] = set()
    deduped = []
    for r in sorted_r:
        link_id = r.get("link_id")
        if link_id not in seen:
            seen.add(link_id)
            deduped.append(r)
    return [r["link_id"] for r in deduped]


# ─── Mock 평가 데이터셋 ────────────────────────────────────────────────────────

def _c(link_id, keywords, dense_score, content_source="jina"):
    return {
        "link_id": link_id,
        "keywords": json.dumps(keywords),
        "dense_score": dense_score,
        "content_source": content_source,
    }


# 기존 10개 케이스: PR#68 (keyword exact-match)이 Dense-only 대비 개선한 케이스들
ORIG_EVAL_CASES = [
    {
        "query": "하나증권 채용 공고",
        "relevant": {1},
        "candidates": [
            _c(1, ["하나증권", "채용", "금융", "취업", "공고"], dense_score=0.55),
            _c(2, ["삼성전자", "취업", "공채", "IT"], dense_score=0.70),
            _c(3, ["파이썬", "웹개발", "Django"], dense_score=0.45),
            _c(4, ["카카오", "개발자", "채용"], dense_score=0.60),
            _c(5, ["주식", "ETF", "금융상품"], dense_score=0.50),
        ],
    },
    {
        "query": "파이썬 로깅 모범사례",
        "relevant": {10},
        "candidates": [
            _c(10, ["Python", "로깅", "logging", "모범사례", "개발"], dense_score=0.60),
            _c(11, ["Java", "Spring", "백엔드"], dense_score=0.72),
            _c(12, ["파이썬", "비동기", "asyncio"], dense_score=0.65),
            _c(13, ["데이터베이스", "ORM", "SQLAlchemy"], dense_score=0.55),
            _c(14, ["CI/CD", "GitHub Actions", "배포"], dense_score=0.48),
        ],
    },
    {
        "query": "RAG 벡터 검색 구현",
        "relevant": {20, 21},
        "candidates": [
            _c(20, ["RAG", "벡터검색", "pgvector", "임베딩"], dense_score=0.78),
            _c(21, ["LangChain", "RAG", "OpenAI", "검색증강생성"], dense_score=0.62),
            _c(22, ["머신러닝", "딥러닝", "모델학습"], dense_score=0.80),
            _c(23, ["데이터파이프라인", "ETL", "Airflow"], dense_score=0.58),
            _c(24, ["API설계", "REST", "FastAPI"], dense_score=0.55),
        ],
    },
    {
        "query": "스타트업 투자 시리즈A",
        "relevant": {30},
        "candidates": [
            _c(30, ["스타트업", "투자", "시리즈A", "VC", "펀딩"], dense_score=0.52, content_source="og"),
            _c(31, ["주식", "ETF", "자산배분"], dense_score=0.75),
            _c(32, ["부동산", "투자", "임대수익"], dense_score=0.68),
            _c(33, ["코인", "블록체인", "NFT"], dense_score=0.60),
            _c(34, ["절세", "세금", "연말정산"], dense_score=0.48),
        ],
    },
    {
        "query": "도커 컨테이너 배포",
        "relevant": {40},
        "candidates": [
            _c(40, ["Docker", "컨테이너", "배포", "docker-compose", "DevOps"], dense_score=0.58),
            _c(41, ["Kubernetes", "k8s", "오케스트레이션"], dense_score=0.80),
            _c(42, ["AWS", "클라우드", "EC2", "배포"], dense_score=0.72),
            _c(43, ["nginx", "리버스프록시", "웹서버"], dense_score=0.62),
            _c(44, ["CI/CD", "GitHub Actions", "자동화"], dense_score=0.55),
        ],
    },
    {
        "query": "OpenAI API 비용 최적화",
        "relevant": {50, 51},
        "candidates": [
            _c(50, ["OpenAI", "API", "비용", "토큰", "최적화"], dense_score=0.70),
            _c(51, ["GPT-4", "프롬프트", "비용절감", "OpenAI"], dense_score=0.55),
            _c(52, ["Claude", "Anthropic", "LLM"], dense_score=0.75),
            _c(53, ["Gemini", "구글AI", "멀티모달"], dense_score=0.60),
            _c(54, ["로컬LLM", "Ollama", "오픈소스"], dense_score=0.58),
        ],
    },
    {
        "query": "알고리즘 코딩테스트 준비",
        "relevant": {60},
        "candidates": [
            _c(60, ["알고리즘", "코딩테스트", "LeetCode", "백준", "취업"], dense_score=0.65),
            _c(61, ["자료구조", "그래프", "동적프로그래밍"], dense_score=0.82),
            _c(62, ["CS기초", "운영체제", "네트워크"], dense_score=0.70),
            _c(63, ["면접준비", "기술면접", "프로그래밍"], dense_score=0.62),
            _c(64, ["파이썬문법", "기초", "입문"], dense_score=0.55),
        ],
    },
    {
        "query": "PostgreSQL 인덱스 튜닝",
        "relevant": {70},
        "candidates": [
            _c(70, ["PostgreSQL", "인덱스", "쿼리최적화", "성능튜닝", "DB"], dense_score=0.60),
            _c(71, ["MySQL", "데이터베이스", "쿼리"], dense_score=0.78),
            _c(72, ["Redis", "캐싱", "인메모리"], dense_score=0.68),
            _c(73, ["MongoDB", "NoSQL", "문서DB"], dense_score=0.64),
            _c(74, ["데이터모델링", "ERD", "정규화"], dense_score=0.57),
        ],
    },
    {
        "query": "Next.js SSR 성능",
        "relevant": {80},
        "candidates": [
            _c(80, ["Next.js", "SSR", "성능", "서버사이드렌더링", "React"], dense_score=0.62),
            _c(81, ["React", "SPA", "클라이언트렌더링"], dense_score=0.85),
            _c(82, ["Vue.js", "프론트엔드", "컴포넌트"], dense_score=0.72),
            _c(83, ["TypeScript", "타입시스템", "인터페이스"], dense_score=0.65),
            _c(84, ["웹성능", "Core Web Vitals", "LCP"], dense_score=0.60),
        ],
    },
    {
        "query": "생성형 AI 비즈니스 활용",
        "relevant": {90, 91},
        "candidates": [
            _c(90, ["생성형AI", "ChatGPT", "비즈니스", "자동화", "활용"], dense_score=0.68),
            _c(91, ["AI도입", "업무효율", "생성AI", "ROI"], dense_score=0.56, content_source="og"),
            _c(92, ["딥러닝", "논문", "연구", "AI모델"], dense_score=0.80),
            _c(93, ["ML엔지니어", "MLOps", "모델배포"], dense_score=0.72),
            _c(94, ["데이터분석", "Python", "pandas"], dense_score=0.62),
        ],
    },
]

# 오늘 개선 케이스: 띄어쓰기 query variant + substring matching
NEW_EVAL_CASES = [
    {
        "query": "하나 증권 공고",           # 띄어쓰기 → compound keyword via variant
        "tag": "[variant]",
        "relevant": {101},
        "candidates": [
            _c(101, ["하나증권", "채용공고", "신입사원", "2026"], dense_score=0.52),
            _c(102, ["챗GPT", "자소서", "취업팁", "합격"], dense_score=0.72),
            _c(103, ["파이썬", "로깅", "개발환경"], dense_score=0.65),
            _c(104, ["삼성전자", "채용", "공채"], dense_score=0.60),
            _c(105, ["LLM", "AI", "기술동향"], dense_score=0.55),
        ],
    },
    {
        "query": "채용 공고",                # "채용"+"공고" → "채용공고" via substring
        "tag": "[substring]",
        "relevant": {111},
        "candidates": [
            _c(111, ["채용공고", "신입사원", "IT기업"], dense_score=0.50),
            _c(112, ["면접준비", "자소서", "스펙"], dense_score=0.72),
            _c(113, ["연봉협상", "복지", "워라밸"], dense_score=0.65),
            _c(114, ["경력개발", "커리어", "성장"], dense_score=0.58),
            _c(115, ["포트폴리오", "깃허브", "프로젝트"], dense_score=0.53),
        ],
    },
    {
        "query": "개발 환경 구축",           # "개발환경" + "환경구축" compound via variant
        "tag": "[variant]",
        "relevant": {121},
        "candidates": [
            _c(121, ["개발환경", "환경구축", "DevOps", "설정"], dense_score=0.55),
            _c(122, ["클라우드", "AWS", "인프라"], dense_score=0.78),
            _c(123, ["리눅스", "쉘스크립트", "배포"], dense_score=0.68),
            _c(124, ["IDE", "VSCode", "플러그인"], dense_score=0.62),
            _c(125, ["패키지관리", "pip", "가상환경"], dense_score=0.57),
        ],
    },
    {
        "query": "검색 최적화 구현",         # "검색최적화" + "성능최적화" via substring
        "tag": "[substring+variant]",
        "relevant": {131},
        "candidates": [
            _c(131, ["검색최적화", "성능최적화", "벡터검색", "인덱싱"], dense_score=0.58),
            _c(132, ["딥러닝", "모델학습", "GPU"], dense_score=0.80),
            _c(133, ["데이터파이프라인", "ETL", "배치"], dense_score=0.72),
            _c(134, ["API성능", "캐싱", "Redis"], dense_score=0.65),
            _c(135, ["프론트엔드", "렌더링", "최적화"], dense_score=0.60),
        ],
    },
]


# ─── 평가 실행 ────────────────────────────────────────────────────────────────

@dataclass
class CaseResult:
    query: str
    tag: str
    dense_rank: list[int]
    pr68_rank: list[int]
    today_rank: list[int]
    relevant: set[int]


def _compute_metrics(results: list[CaseResult], mode: str, k: int) -> dict:
    p_vals, mrr_vals, ndcg_vals = [], [], []
    for r in results:
        if mode == "dense":
            ranked = r.dense_rank
        elif mode == "pr68":
            ranked = r.pr68_rank
        else:
            ranked = r.today_rank
        p_vals.append(precision_at_k(ranked, r.relevant, k))
        mrr_vals.append(reciprocal_rank(ranked, r.relevant))
        ndcg_vals.append(ndcg_at_k(ranked, r.relevant, k))
    n = len(p_vals)
    return {
        f"P@{k}": sum(p_vals) / n,
        "MRR": sum(mrr_vals) / n,
        f"NDCG@{k}": sum(ndcg_vals) / n,
    }


def _pct(a: float, b: float) -> str:
    if b == 0:
        return "  N/A"
    delta = (a - b) / b * 100
    arrow = "+" if delta > 0 else ("-" if delta < 0 else " ")
    return f"{arrow}{abs(delta):>5.1f}%"


def evaluate(k: int = 5) -> None:
    # ── Case 결과 계산
    orig_results = [
        CaseResult(
            query=c["query"], tag=c.get("tag", ""),
            dense_rank=dense_only_rank(c["candidates"]),
            pr68_rank=pr68_rank(c["candidates"], c["query"]),
            today_rank=today_rank(c["candidates"], c["query"]),
            relevant=c["relevant"],
        )
        for c in ORIG_EVAL_CASES
    ]
    new_results = [
        CaseResult(
            query=c["query"], tag=c.get("tag", ""),
            dense_rank=dense_only_rank(c["candidates"]),
            pr68_rank=pr68_rank(c["candidates"], c["query"]),
            today_rank=today_rank(c["candidates"], c["query"]),
            relevant=c["relevant"],
        )
        for c in NEW_EVAL_CASES
    ]

    def _print_case_table(results: list[CaseResult], title: str) -> int:
        print(f"\n{'='*72}")
        print(f"  {title}  (K={k})")
        print(f"{'='*72}")
        print(f"{'쿼리':<22}  {'정답':>5}  {'Dense 1위':>9}  {'PR#68 1위':>9}  {'Today 1위':>9}  개선")
        print("-" * 72)
        improved = 0
        for r in results:
            d1 = r.dense_rank[0] if r.dense_rank else "-"
            p1 = r.pr68_rank[0] if r.pr68_rank else "-"
            t1 = r.today_rank[0] if r.today_rank else "-"
            d_hit = d1 in r.relevant
            p_hit = p1 in r.relevant
            t_hit = t1 in r.relevant
            if not p_hit and t_hit:
                status = "[Today+]"
                improved += 1
            elif not d_hit and p_hit:
                status = "[PR68+ ]"
            elif t_hit:
                status = "[유지   ]"
            else:
                status = "[--     ]"
            rel_str = ",".join(str(i) for i in sorted(r.relevant))
            tag = r.tag or ""
            q_display = f"{r.query} {tag}" if tag else r.query
            print(f"{q_display:<26}  {rel_str:>5}  {str(d1):>9}  {str(p1):>9}  {str(t1):>9}  {status}")
        return improved

    # ── 출력
    orig_improved = _print_case_table(orig_results, f"기존 케이스 ({len(orig_results)}개) — PR#68 vs Dense 개선")
    new_improved = _print_case_table(new_results, f"신규 케이스 ({len(new_results)}개) — Today vs PR#68 개선")

    # ── 종합 지표
    all_results = orig_results + new_results
    print(f"\n{'='*72}")
    print("  종합 지표 비교")
    print(f"{'='*72}")
    print(f"{'지표':<10}  {'Dense':>8}  {'PR#68':>8}  {'Today':>8}  {'PR68↑':>8}  {'Today↑':>8}  {'Total↑':>8}")
    print("-" * 72)

    for metric in [f"P@{k}", "MRR", f"NDCG@{k}"]:
        d = _compute_metrics(all_results, "dense", k)[metric]
        p = _compute_metrics(all_results, "pr68", k)[metric]
        t = _compute_metrics(all_results, "today", k)[metric]
        print(f"{metric:<10}  {d:>8.4f}  {p:>8.4f}  {t:>8.4f}  {_pct(p,d):>8}  {_pct(t,p):>8}  {_pct(t,d):>8}")

    print("-" * 72)
    total = len(all_results)
    print(f"\n[기존] 1위 정확도: {orig_improved}/{len(orig_results)} Today 추가 개선")
    print(f"[신규] 1위 정확도: {new_improved}/{len(new_results)} Today 개선 (PR#68 대비)")
    print()
    print("※ 이 수치는 mock 데이터 기반입니다.")
    print("  실제 DB 데이터로 측정하려면 --real 플래그를 사용하세요.")


# ─── 실제 DB 모드 (환경변수 필요) ─────────────────────────────────────────────

REAL_EVAL_QUERIES: list[dict] = [
    # 실제 저장된 링크 기준으로 채워주세요
    # {"query": "하나증권 채용", "relevant_urls": ["https://..."]}
]


async def evaluate_real(user_id: int, k: int = 5) -> None:
    """실제 DB 연결 평가. 환경변수 DATABASE_URL, OPENAI_API_KEY 필요."""
    import sys as _sys
    _sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.infrastructure.rag.retriever import (
        _rescore_with_keywords, _dedupe_by_link,
        _RECALL_MULTIPLIER, _MIN_RECALL_K, _MAX_RECALL_K,
    )
    from app.infrastructure.repository.chunk_repository import ChunkRepository
    from app.infrastructure.llm.openai_client import OpenAIRepository
    from app.core.config import settings

    if not REAL_EVAL_QUERIES:
        print("REAL_EVAL_QUERIES가 비어 있습니다.")
        print("scripts/eval_retriever.py 내 REAL_EVAL_QUERIES를 채워주세요.")
        return

    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        chunk_repo = ChunkRepository(session)
        openai_adapter = OpenAIRepository()

        print(f"실제 DB 평가 시작 (user_id={user_id}, K={k})")
        for case in REAL_EVAL_QUERIES:
            query = case["query"]
            relevant_urls = set(case.get("relevant_urls", []))
            [embedding] = await openai_adapter.embed([query])
            recall_k = min(max(k * _RECALL_MULTIPLIER, _MIN_RECALL_K), _MAX_RECALL_K)
            raw = await chunk_repo.search_similar(
                user_id,
                embedding,
                recall_k,
                query_texts=[query],
            )

            before_urls = [r["url"] for r in sorted(raw, key=lambda x: x.get("dense_score", 0), reverse=True)]
            after_urls = [r["url"] for r in _dedupe_by_link(_rescore_with_keywords(raw, query))]

            p_before = precision_at_k(before_urls, relevant_urls, k)  # type: ignore[arg-type]
            p_after = precision_at_k(after_urls, relevant_urls, k)    # type: ignore[arg-type]
            print(f"  [{query}]  P@{k}: Before={p_before:.2f}  After={p_after:.2f}")


# ─── 진입점 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--real" in sys.argv:
        import asyncio
        user_id = int(sys.argv[sys.argv.index("--user") + 1]) if "--user" in sys.argv else 1
        asyncio.run(evaluate_real(user_id))
    else:
        evaluate(k=5)
