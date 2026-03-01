"""📈 트렌드 탭 — 소비 패턴 시각화. Advanced ON 시 기술 지표 노출."""
import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import (
    DashboardAPIClient,
    cached_get_drift,
    cached_get_embeddings,
    cached_get_stats,
)
from dashboard.logger import logger


def render(client: DashboardAPIClient, advanced: bool = False) -> None:
    jwt_token: str = st.session_state["jwt_token"]
    with st.spinner("통계 로딩 중..."):
        try:
            stats = cached_get_stats(jwt_token)
        except Exception as e:
            logger.error(f"Trends tab data load failed: {e}")
            st.error(f"데이터 로딩 실패: {e}")
            return

    # ── 월별 저장 추이 ────────────────────────────────────────────
    st.subheader("📅 월별 저장 추이")
    monthly = stats.get("monthly_series", [])
    if monthly:
        df_monthly = pd.DataFrame(monthly)
        fig = px.line(
            df_monthly, x="month", y="count",
            markers=True, labels={"month": "월", "count": "저장 수"},
        )
        fig.update_layout(height=280)
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("아직 데이터가 부족합니다.")

    st.divider()

    # ── 카테고리 분포 ─────────────────────────────────────────────
    st.subheader("🗂 카테고리 분포")
    cat_dist = stats.get("category_dist", [])
    if cat_dist:
        df_cat = pd.DataFrame(cat_dist)
        fig2 = px.bar(
            df_cat, x="category", y="count",
            labels={"category": "카테고리", "count": "링크 수"},
            color="category",
        )
        fig2.update_layout(height=280, showlegend=False)
        st.plotly_chart(fig2, width='stretch')
    else:
        st.info("아직 데이터가 부족합니다.")

    st.divider()

    # ── 상위 키워드 ───────────────────────────────────────────────
    st.subheader("🔑 나의 관심 키워드 Top 20")
    keywords = stats.get("top_keywords", [])
    if keywords:
        df_kw = pd.DataFrame(keywords[:20])
        fig3 = px.bar(
            df_kw, x="count", y="keyword",
            orientation="h",
            labels={"keyword": "", "count": "빈도"},
        )
        fig3.update_layout(height=400, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig3, width='stretch')
    else:
        st.info("키워드 데이터가 없습니다.")

    st.divider()

    # ── 읽기 습관 ─────────────────────────────────────────────────
    st.subheader("📖 읽기 습관")
    col1, col2 = st.columns(2)
    with col1:
        total = stats.get("total", 0)
        unread = stats.get("unread_count", 0)
        st.metric("전체 저장", f"{total}개")
        st.metric("미열람", f"{unread}개")
    with col2:
        read_ratio = stats.get("read_ratio", 0)
        this_month = stats.get("this_month_count", 0)
        st.metric("읽음률", f"{read_ratio:.0%}")
        st.metric("이번 달 저장", f"{this_month}개")

    # ── Advanced: Drift + PCA ─────────────────────────────────────
    if advanced:
        st.divider()
        st.subheader("🔬 Advanced — Drift & Knowledge Universe")

        with st.spinner("고급 분석 로딩 중..."):
            try:
                drift = cached_get_drift(jwt_token)
                embeddings = cached_get_embeddings(jwt_token)
            except Exception as e:
                st.error(f"고급 분석 로딩 실패: {e}")
                return

        # Drift Radar
        current_dist = drift.get("current_distribution", {})
        past_dist = drift.get("past_distribution", {})
        tvd = drift.get("tvd", 0)
        delta = drift.get("delta", {})

        import plotly.graph_objects as go
        all_cats = sorted(set(list(current_dist.keys()) + list(past_dist.keys())))
        if all_cats:
            st.markdown(f"**TVD: `{tvd:.3f}`** — {'급격한 변화' if tvd > 0.3 else '서서히 이동 중' if tvd > 0.1 else '안정적'}")
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
                height=350,
            )
            st.plotly_chart(fig_radar, width='stretch')

            if delta:
                df_delta = pd.DataFrame(
                    [{"카테고리": k, "변화량": round(v, 3)} for k, v in
                     sorted(delta.items(), key=lambda x: x[1], reverse=True)]
                )
                st.dataframe(df_delta, width='stretch', hide_index=True)

        # PCA Scatter
        pca_items = embeddings.get("items", [])
        explained = embeddings.get("explained_variance")
        if pca_items:
            st.markdown(f"**Knowledge Universe** (PCA 2D, 설명 분산: `{explained:.1%}` )")
            df_pca = pd.DataFrame(pca_items)
            fig_pca = px.scatter(
                df_pca, x="x", y="y", color="category",
                hover_name="title",
                hover_data={"x": False, "y": False},
            )
            fig_pca.update_traces(marker=dict(size=7, opacity=0.75))
            fig_pca.update_layout(height=450)
            st.plotly_chart(fig_pca, width='stretch')
        else:
            st.info("임베딩 데이터가 3개 이상이어야 PCA 시각화가 가능합니다.")
