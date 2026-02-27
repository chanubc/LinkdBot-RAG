"""Reactivation Score 계산 — 순수 함수 (외부 의존성 없음).

Score = (Similarity × 0.6) + (Recency × 0.4)
"""
from __future__ import annotations

import math
from datetime import datetime, timezone


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """두 벡터의 코사인 유사도 (-1 ~ 1)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def compute_interest_centroid(embeddings: list[list[float]]) -> list[float] | None:
    """임베딩 목록의 평균 벡터(centroid) 계산.

    Args:
        embeddings: 임베딩 벡터 목록.

    Returns:
        centroid 벡터. 목록이 비어있으면 None 반환.
    """
    if not embeddings:
        return None
    dim = len(embeddings[0])
    centroid = [0.0] * dim
    for emb in embeddings:
        for i, v in enumerate(emb):
            centroid[i] += v
    n = len(embeddings)
    return [v / n for v in centroid]


def calculate_forgetting_score(created_at: datetime) -> float:
    """망각 점수 — 오래될수록 1에 수렴.

    recency = 1 - 1 / (1 + days_since_created)
    """
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - created_at).total_seconds() / 86400)
    return 1.0 - 1.0 / (1.0 + days)


def calculate_reactivation_score(
    link_embedding: list[float],
    interest_centroid: list[float],
    created_at: datetime,
) -> float:
    """재활성화 점수 계산.

    Score = (Similarity × 0.6) + (Recency × 0.4)

    Args:
        link_embedding:     링크 summary_embedding 벡터.
        interest_centroid:  현재 관심사 centroid 벡터.
        created_at:         링크 생성 시각.

    Returns:
        0~1 범위 점수.
    """
    similarity = (cosine_similarity(link_embedding, interest_centroid) + 1) / 2  # -1~1 → 0~1
    recency = calculate_forgetting_score(created_at)
    return similarity * 0.6 + recency * 0.4


def select_reactivation_link(
    candidates: list[dict],
    interest_centroid: list[float],
) -> dict | None:
    """재활성화 점수가 가장 높은 링크 1개 반환.

    Args:
        candidates: [{"link_id", "summary_embedding", "created_at", ...}] 목록.
                    summary_embedding이 None인 항목은 무시.
        interest_centroid: 현재 관심사 centroid.

    Returns:
        점수가 가장 높은 candidate dict (score 키 추가), 없으면 None.
    """
    scored: list[tuple[float, dict]] = []
    for c in candidates:
        emb = c.get("summary_embedding")
        created_at = c.get("created_at")
        if emb is None or created_at is None:
            continue
        score = calculate_reactivation_score(emb, interest_centroid, created_at)
        scored.append((score, c))

    if not scored:
        return None

    best_score, best = max(scored, key=lambda t: t[0])
    return {**best, "score": best_score}
