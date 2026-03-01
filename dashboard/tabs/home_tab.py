"""🏠 홈 탭 — 오늘의 추천 + 주간 요약 + 관심사 한 줄 분석."""
import streamlit as st

from dashboard.api_client import (
    DashboardAPIClient,
    cached_get_drift,
    cached_get_reactivation,
    cached_get_stats,
)
from dashboard.logger import logger


def _drift_to_text(tvd: float, delta: dict) -> str:
    """TVD/delta → 자연어 (LLM 없이 규칙 기반)."""
    if not delta:
        return "아직 분석할 데이터가 부족합니다."

    if tvd > 0.3:
        stability = "관심사가 빠르게 변화 중입니다"
    elif tvd > 0.1:
        stability = "관심사가 서서히 이동 중입니다"
    else:
        stability = "관심사가 안정적입니다"

    sorted_delta = sorted(delta.items(), key=lambda x: x[1], reverse=True)
    top_up = [c for c, d in sorted_delta if d > 0.05]
    top_down = [c for c, d in sorted_delta if d < -0.05]

    parts = [stability]
    if top_up:
        parts.append(f"{', '.join(top_up[:2])} 분야 관심이 증가했습니다")
    if top_down:
        parts.append(f"{', '.join(top_down[:2])} 관심도는 감소했습니다")

    return ". ".join(parts) + "."


def render(client: DashboardAPIClient, advanced: bool = False) -> None:
    # --- 데이터 로드 (캐시 사용) ---
    jwt_token: str = st.session_state["jwt_token"]
    with st.spinner("로딩 중..."):
        try:
            stats = cached_get_stats(jwt_token)
            reactivation = cached_get_reactivation(jwt_token)
            drift = cached_get_drift(jwt_token)
        except Exception as e:
            logger.error(f"Home tab data load failed: {e}")
            st.error(f"데이터 로딩 실패: {e}")
            return

    top3 = reactivation.get("items", [])[:3]

    # --- 관심사 한 줄 분석 ---
    tvd = drift.get("tvd", 0.0)
    delta = drift.get("delta", {})
    analysis_text = _drift_to_text(tvd, delta)
    st.info(f"🧠 **나의 관심사 분석** — {analysis_text}")

    # --- 주간 통계 ---
    st.subheader("📊 이번 주 요약")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("이번 주 저장", f"{stats.get('this_week_count', 0)}개")
        st.metric("전체 저장", f"{stats.get('total', 0)}개")
    with col2:
        read_ratio = stats.get("read_ratio", 0)
        st.metric("읽음률", f"{read_ratio:.0%}")
        top_cat = stats.get("top_category") or "-"
        st.metric("최다 카테고리", top_cat)

    st.divider()

    # --- 오늘의 추천 ---
    st.subheader("🔥 오늘 읽으면 좋은 글")

    if not top3:
        st.info("재활성화 후보가 없습니다. 링크를 더 저장하거나 3일 후에 다시 확인하세요.")
    else:
        for link in top3:
            _render_recommendation_card(client, link, advanced)

    # --- Advanced: Drift 수치 ---
    if advanced:
        with st.expander("🔬 Drift 세부 지표", expanded=False):
            st.metric("TVD", f"{tvd:.3f}")
            if delta:
                import pandas as pd
                df = pd.DataFrame(
                    [{"카테고리": k, "변화량": round(v, 3)} for k, v in
                     sorted(delta.items(), key=lambda x: x[1], reverse=True)]
                )
                st.dataframe(df, use_container_width=True, hide_index=True)


def _render_recommendation_card(
    client: DashboardAPIClient, link: dict, advanced: bool
) -> None:
    with st.container(border=True):
        col1, col2 = st.columns([0.85, 0.15])

        with col1:
            st.markdown(f"**{link['title']}**")
            cat = link.get("category", "")
            score = link.get("score", 0)

            # 추천 이유 태그 (규칙 기반)
            similarity = link.get("similarity", 0)
            recency = link.get("recency", 0)
            if similarity * 0.6 >= recency * 0.4:
                reason = f"✨ 최근 관심사와 유사한 글"
            else:
                reason = f"🕐 오랫동안 읽지 않은 글"

            st.caption(f"{cat}  ·  {reason}")
            summary = link.get("summary", "")
            if summary:
                st.write(summary[:120] + ("..." if len(summary) > 120 else ""))

            if advanced:
                st.caption(f"Score: {score:.3f} (유사도 {link.get('similarity', 0):.2f} · 망각 {link.get('recency', 0):.2f})")

        with col2:
            url = link.get("url")
            if url:
                st.link_button("🔗", url, use_container_width=True)
            if st.button("✅", key=f"home_read_{link['id']}", help="읽음 처리",
                         use_container_width=True):
                try:
                    client.mark_link_read(link["id"])
                    st.session_state.pop("home_data", None)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
