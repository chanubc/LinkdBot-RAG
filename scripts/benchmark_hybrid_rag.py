"""Hybrid RAG 전체 파이프라인 정확도 벤치마크 (3단계 비교).

실제 사용자가 /search 또는 /ask로 쿼리를 날렸을 때,
올바른 링크가 상위에 오는지를 측정합니다.

Dense(pgvector) + Sparse(FTS) + Keyword Rescoring 전체 파이프라인을
Pre-Phase A / Phase A / Phase B 세 단계로 비교합니다.

Ground truth: 수동 레이블 (쿼리 → 기대 링크 제목 패턴)

Usage:
    python scripts/benchmark_hybrid_rag.py --user-id <USER_ID>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlalchemy as sa
from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.rag.korean_utils import morpheme_tokenize
from app.infrastructure.rag.retriever import _build_query_variants, _token_matches

load_dotenv()

TOP_K = 5

# ---------------------------------------------------------------------------
# Test queries + ground truth (기대 링크 제목에 포함돼야 할 키워드)
# ---------------------------------------------------------------------------
# (query, [relevant_title_keywords], description)
LABELED_QUERIES: list[tuple[str, list[str], str]] = [
    # 복합어 + 조사 (Phase B 핵심 — FTS가 dense 보완)
    ("삼성에서 신입공채 자소서를 써야해",  ["삼성"],                    "삼성+에서+를 조사"),
    ("롯데채용공고를 찾아줘",             ["롯데"],                    "복합어+를 조사"),
    ("한화시스템에서 ICT채용한다는데",     ["한화"],                    "에서+복합어 조사"),
    ("개발자채용을 하는 AI스타트업",       ["채용", "AI"],              "개발자채용을+AI스타트업 복합"),
    ("AI개발자를 뽑는 회사 알려줘",       ["채용", "AI"],              "AI개발자를 복합+조사"),
    # 자연어 조사 포함 (dense 점수 비슷한 다수 문서 → FTS 구분)
    ("Claude코드로 개발하는 방법",        ["Claude Code", "claude"],   "Claude코드로 복합+조사"),
    ("파이썬으로 개발하는 공식 튜토리얼",  ["Python"],                  "파이썬으로 외래어+조사"),
    ("LLM에이전트 개념이 뭐야",           ["Agent", "AI", "LLM"],      "LLM에이전트 복합어"),
    ("AI코딩워크플로우 도구를 찾아줘",     ["AI", "코딩", "워크플로우", "tools"], "AI코딩워크플로우 복합"),
    ("GCP에서 크레딧 관리하는법",         ["GCP"],                     "GCP에서 조사"),
]


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _precision_at_k(ranked: list[int], rel: set[int], k: int) -> float:
    return sum(1 for cid in ranked[:k] if cid in rel) / k if k else 0.0

def _mrr(ranked: list[int], rel: set[int]) -> float:
    for i, cid in enumerate(ranked, 1):
        if cid in rel:
            return 1.0 / i
    return 0.0

def _ndcg_at_k(ranked: list[int], rel: set[int], k: int) -> float:
    dcg = sum(1 / math.log2(i + 1) for i, cid in enumerate(ranked[:k], 1) if cid in rel)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(rel), k) + 1))
    return dcg / ideal if ideal else 0.0

def _top1(ranked: list[int], rel: set[int]) -> float:
    return 1.0 if ranked and ranked[0] in rel else 0.0

def _avg(lst: list[float]) -> float:
    return sum(lst) / len(lst) if lst else 0.0


# ---------------------------------------------------------------------------
# Keyword rescoring helpers
# ---------------------------------------------------------------------------

def _parse_kw(raw) -> list[str]:
    try:
        parsed = json.loads(raw) if raw else []
        return [k.lower() for k in parsed if isinstance(k, str) and k.strip()]
    except Exception:
        return []

def _overlap_pre_a(query: str, kws: list[str], title: str) -> float:
    """Pre-Phase A: raw 토큰, exact/substring만."""
    tokens = {t.lower() for t in query.split() if t}
    if not tokens:
        return 0.0
    matched = sum(
        1 for t in tokens
        if any(t == k or (len(t) >= 2 and t in k) for k in kws)
        or (len(t) >= 2 and t in title.lower())
    )
    return matched / len(tokens)

def _overlap_phase_a(query: str, kws: list[str], title: str) -> float:
    """Phase A+B: morpheme 변형 + _token_matches."""
    best = 0.0
    for variant in _build_query_variants(query):
        tokens = {t.lower() for t in variant.split() if t}
        if not tokens:
            continue
        matched = sum(
            1 for t in tokens
            if any(_token_matches(t, k) for k in kws)
            or (len(t) >= 2 and t in title.lower())
        )
        best = max(best, matched / len(tokens))
    return best


# ---------------------------------------------------------------------------
# Hybrid SQL helpers
# ---------------------------------------------------------------------------

def _make_hybrid_sql(use_morpheme_fts: bool) -> sa.TextClause:
    fts_param = ":morpheme_q" if use_morpheme_fts else ":raw_q"
    return sa.text(f"""
        WITH dense AS (
            SELECT c.id AS chunk_id, l.id AS link_id, l.title, l.keywords,
                   1 - (c.embedding <=> CAST(:emb AS vector)) AS dense_score
            FROM chunks c JOIN links l ON c.link_id = l.id
            WHERE l.user_id = :user_id
        ),
        sparse AS (
            SELECT c.id AS chunk_id,
                   ts_rank(c.tsv, plainto_tsquery('simple', {fts_param})) AS sparse_score
            FROM chunks c JOIN links l ON c.link_id = l.id
            WHERE l.user_id = :user_id
              AND c.tsv IS NOT NULL
              AND c.tsv @@ plainto_tsquery('simple', {fts_param})
        )
        SELECT d.chunk_id, d.link_id, d.title, d.keywords,
               d.dense_score,
               COALESCE(s.sparse_score, 0) AS sparse_score,
               (d.dense_score * 0.7 + COALESCE(s.sparse_score, 0) * 0.3) AS base_score
        FROM dense d LEFT JOIN sparse s ON d.chunk_id = s.chunk_id
        ORDER BY base_score DESC
        LIMIT :recall_k
    """)


async def _run_stage(
    conn, query: str, emb: list[float], user_id: int,
    use_morpheme_fts: bool, keyword_stage: str, recall_k: int = 50
) -> list[int]:
    """한 단계 hybrid 검색 → 상위 link_ids 반환 (by final_score)."""
    emb_str = "[" + ",".join(str(v) for v in emb) + "]"
    morpheme_q = morpheme_tokenize(query)

    rows = (await conn.execute(
        _make_hybrid_sql(use_morpheme_fts),
        {"emb": emb_str, "user_id": user_id,
         "raw_q": query, "morpheme_q": morpheme_q, "recall_k": recall_k},
    )).fetchall()

    # Keyword rescoring + dedupe by link_id
    best_by_link: dict[int, tuple[float, int]] = {}  # link_id → (final_score, chunk_id)
    for r in rows:
        kws = _parse_kw(r.keywords)
        title = (r.title or "").lower()
        if keyword_stage == "pre_a":
            overlap = _overlap_pre_a(query, kws, title)
            kw_weight = 0.3
        else:  # phase_a, phase_b
            overlap = _overlap_phase_a(query, kws, title)
            kw_weight = 0.3

        final = r.base_score * (1 - kw_weight) + overlap * kw_weight
        lid = r.link_id
        if lid not in best_by_link or final > best_by_link[lid][0]:
            best_by_link[lid] = (final, r.chunk_id)

    ranked = sorted(best_by_link.items(), key=lambda x: x[1][0], reverse=True)
    return [lid for lid, _ in ranked[:TOP_K]]


# ---------------------------------------------------------------------------
# Ground truth: link_ids whose title contains ANY of the label keywords
# ---------------------------------------------------------------------------

async def _get_relevant_link_ids(conn, user_id: int, title_keywords: list[str]) -> set[int]:
    conditions = " OR ".join(f"LOWER(l.title) LIKE :k{i}" for i in range(len(title_keywords)))
    params: dict = {"user_id": user_id}
    for i, kw in enumerate(title_keywords):
        params[f"k{i}"] = f"%{kw.lower()}%"
    rows = (await conn.execute(
        sa.text(f"SELECT id FROM links l WHERE l.user_id=:user_id AND ({conditions})"),
        params,
    )).fetchall()
    return {r.id for r in rows}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_benchmark(user_id: int) -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    openai_key   = os.environ.get("OPENAI_API_KEY", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    url = make_url(database_url).set(drivername="postgresql+asyncpg")
    engine = create_async_engine(url)
    client = AsyncOpenAI(api_key=openai_key)

    results = []
    try:
        async with engine.connect() as conn:
            for query, label_kws, description in LABELED_QUERIES:
                print(f"  [{description}] '{query}' ...", end=" ", flush=True)

                relevant = await _get_relevant_link_ids(conn, user_id, label_kws)
                if not relevant:
                    print("SKIP (관련 링크 없음)")
                    continue

                # OpenAI embedding (1회)
                resp = await client.embeddings.create(
                    model="text-embedding-3-small", input=[query]
                )
                emb = resp.data[0].embedding

                # 3단계 실행
                pre_a = await _run_stage(conn, query, emb, user_id,
                                         use_morpheme_fts=False, keyword_stage="pre_a")
                phase_a = await _run_stage(conn, query, emb, user_id,
                                           use_morpheme_fts=False, keyword_stage="phase_a")
                phase_b = await _run_stage(conn, query, emb, user_id,
                                           use_morpheme_fts=True,  keyword_stage="phase_a")

                results.append({
                    "query":       query,
                    "desc":        description,
                    "n_relevant":  len(relevant),
                    "relevant":    relevant,
                    "pre_a":       pre_a,
                    "phase_a":     phase_a,
                    "phase_b":     phase_b,
                })
                print(f"관련={len(relevant)}건 ✓")
    finally:
        await engine.dispose()

    if not results:
        print("\n측정 가능한 쿼리 없음.")
        return

    _print_report(results)


def _print_report(results: list[dict]) -> None:
    print("\n\n" + "=" * 110)
    print(f"{'쿼리':<30} {'관련':>4}  {'------ P@5 ------':^22}  {'------ MRR ------':^22}  {'--- Top-1 ---':^16}")
    print(f"{'':30} {'':4}  {'Pre-A':>6} {'Ph-A':>7} {'Ph-B':>7}  "
          f"{'Pre-A':>6} {'Ph-A':>7} {'Ph-B':>7}  {'Pre-A':>5} {'Ph-A':>5} {'Ph-B':>5}")
    print("-" * 110)

    agg = {s: {"p": [], "m": [], "n": [], "t": []} for s in ["pre_a", "phase_a", "phase_b"]}

    for r in results:
        rel = r["relevant"]
        metrics = {}
        for stage in ["pre_a", "phase_a", "phase_b"]:
            ranked = r[stage]
            metrics[stage] = {
                "p": _precision_at_k(ranked, rel, TOP_K),
                "m": _mrr(ranked, rel),
                "n": _ndcg_at_k(ranked, rel, TOP_K),
                "t": _top1(ranked, rel),
            }
            for k, v in metrics[stage].items():
                agg[stage][k].append(v)

        def top1_icon(val): return "✅" if val == 1.0 else "❌"

        print(
            f"{r['query']:<30} {r['n_relevant']:>4}  "
            f"{metrics['pre_a']['p']:>6.3f} {metrics['phase_a']['p']:>7.3f} {metrics['phase_b']['p']:>7.3f}  "
            f"{metrics['pre_a']['m']:>6.3f} {metrics['phase_a']['m']:>7.3f} {metrics['phase_b']['m']:>7.3f}  "
            f"{top1_icon(metrics['pre_a']['t']):>5} {top1_icon(metrics['phase_a']['t']):>5} {top1_icon(metrics['phase_b']['t']):>5}"
        )

    print("=" * 110)

    n = len(results)
    print(f"\n{'지표':<12} {'Pre-Phase A':>12} {'Phase A':>10} {'Phase B':>10}  {'A→B':>8} {'Pre→B':>8}")
    print("-" * 60)
    for mk, label in [("p", f"P@{TOP_K}"), ("m", "MRR"), ("n", f"NDCG@{TOP_K}"), ("t", "Top-1 정확도")]:
        pre = _avg(agg["pre_a"][mk])
        pa  = _avg(agg["phase_a"][mk])
        pb  = _avg(agg["phase_b"][mk])
        def d(b, a):
            if b == 0: return f"{'∞' if a > 0 else '0%':>8}"
            return f"{(a-b)/b*100:>+7.0f}%"
        print(f"{label:<12} {pre:>12.4f} {pa:>10.4f} {pb:>10.4f}  {d(pa, pb)} {d(pre, pb)}")

    print(f"\n측정 쿼리 수: {n} / {len(LABELED_QUERIES)}")

    # 상위 링크 미리보기
    print("\n\n--- 쿼리별 상위 링크 (Phase B 기준) ---")
    for r in results:
        print(f"\n▶ \"{r['query']}\"")
        for stage, label in [("pre_a", "Pre-A"), ("phase_a", "Ph-A"), ("phase_b", "Ph-B")]:
            ids = r[stage][:3]
            print(f"  {label}: link_ids={ids}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int, required=True)
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.user_id))
