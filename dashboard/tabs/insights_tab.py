"""🧠 인사이트 탭 — Interest Drift · Reactivation Debugger · Knowledge Universe."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.api_client import (
    cached_get_drift,
    cached_get_embeddings,
    cached_get_reactivation,
)
from dashboard.colors import CATEGORY_COLORS
from dashboard.logger import logger


def render() -> None:
    jwt_token: str = st.session_state["jwt_token"]
    with st.spinner("인사이트 로딩 중..."):
        try:
            drift = cached_get_drift(jwt_token)
            reactivation = cached_get_reactivation(jwt_token)
            embeddings = cached_get_embeddings(jwt_token)
        except Exception as e:
            logger.error(f"Insights tab data load failed: {e}")
            st.error(f"데이터 로딩 실패: {e}")
            return

    # ── Interest Drift ────────────────────────────────────────────
    st.subheader("📈 Interest Drift — 관심사 변화")
    st.caption("최근 7일 vs 7~30일 전 카테고리 분포 비교")

    current_dist = drift.get("current_distribution", {})
    past_dist = drift.get("past_distribution", {})
    tvd = drift.get("tvd", 0)
    delta = drift.get("delta", {})
    all_cats = sorted(set(list(current_dist.keys()) + list(past_dist.keys())))

    if all_cats:
        stability_label = (
            "급격한 변화" if tvd > 0.3
            else "서서히 이동 중" if tvd > 0.1
            else "안정적"
        )
        st.metric("TVD (관심사 변화량)", f"{tvd:.3f}", help="0에 가까울수록 안정, 0.3 이상이면 급변")
        st.caption(f"현재 상태: **{stability_label}**")

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=[current_dist.get(c, 0) for c in all_cats] + [current_dist.get(all_cats[0], 0)],
            theta=all_cats + [all_cats[0]],
            fill="toself", name="최근 7일", line_color="royalblue",
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=[past_dist.get(c, 0) for c in all_cats] + [past_dist.get(all_cats[0], 0)],
            theta=all_cats + [all_cats[0]],
            fill="toself", name="7~30일 전", opacity=0.5, line_color="tomato",
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            height=380,
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        if delta:
            df_delta = pd.DataFrame([
                {
                    "카테고리": k,
                    "변화량": round(v, 3),
                    "방향": "▲ 증가" if v > 0 else "▼ 감소",
                }
                for k, v in sorted(delta.items(), key=lambda x: x[1], reverse=True)
                if abs(v) > 0.01
            ])
            if not df_delta.empty:
                st.dataframe(df_delta, use_container_width=True, hide_index=True)
    else:
        st.info("분석할 데이터가 부족합니다. 링크를 더 저장해주세요.")

    st.divider()

    # ── Reactivation Debugger ─────────────────────────────────────
    st.subheader("🔁 Reactivation Debugger — 추천 알고리즘 투명성")
    st.caption("Score = (유사도 × 0.6) + (시간 감쇠 × 0.4) 공식으로 오늘의 추천 순위를 계산합니다")

    items = reactivation.get("items", [])
    if items:
        df_rank = pd.DataFrame([
            {
                "순위": idx + 1,
                "제목": item.get("title", "")[:40],
                "카테고리": item.get("category", ""),
                "유사도": round(item.get("similarity", 0), 3),
                "시간감쇠": round(item.get("recency", 0), 3),
                "최종점수": round(item.get("score", 0), 3),
            }
            for idx, item in enumerate(items[:15])
        ])
        st.dataframe(
            df_rank,
            use_container_width=True,
            hide_index=True,
            column_config={
                "최종점수": st.column_config.ProgressColumn("최종점수", min_value=0, max_value=1),
                "유사도": st.column_config.ProgressColumn("유사도", min_value=0, max_value=1),
                "시간감쇠": st.column_config.ProgressColumn("시간감쇠", min_value=0, max_value=1),
            },
        )
        st.caption(f"총 {reactivation.get('total', 0)}개 후보 중 상위 15개 표시")
    else:
        st.info("재활성화 후보가 없습니다. 링크를 더 저장하거나 3일 후에 다시 확인하세요.")

    st.divider()

    # ── Knowledge Universe ────────────────────────────────────────
    st.subheader("🌌 Knowledge Universe — 나의 지식 공간")

    pca_items = embeddings.get("items", [])
    explained = embeddings.get("explained_variance")

    if pca_items:
        caption_text = f"저장한 링크 {len(pca_items)}개를 2D 벡터 공간에 시각화"
        if explained:
            caption_text += f"  ·  설명 분산 {explained:.1%}"
        st.caption(caption_text)

        df_pca = pd.DataFrame(pca_items)
        fig_pca = px.scatter(
            df_pca, x="x", y="y",
            color="category",
            color_discrete_map=CATEGORY_COLORS,
            hover_name="title",
            hover_data={"x": False, "y": False},
            labels={"category": "카테고리"},
        )
        fig_pca.update_traces(marker=dict(size=8, opacity=0.8))
        fig_pca.update_layout(
            height=480,
            margin=dict(t=10, b=10),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_pca, use_container_width=True)
    else:
        st.info("임베딩 데이터가 3개 이상이어야 Knowledge Universe 시각화가 가능합니다.")
