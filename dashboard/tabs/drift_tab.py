"""Tab 1: Interest Drift — 관심사 변화 추적."""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from dashboard.api_client import DashboardAPIClient


def render(client: DashboardAPIClient) -> None:
    st.header("📈 Interest Drift")
    st.caption("최근 7일 vs 7~30일 전 관심사 비교")

    with st.spinner("데이터 로딩 중..."):
        try:
            data = client.get_drift()
        except Exception as e:
            st.error(f"데이터 로딩 실패: {e}")
            return

    tvd: float = data.get("tvd", 0.0)
    delta: dict = data.get("delta", {})
    current_dist: dict = data.get("current_distribution", {})
    past_dist: dict = data.get("past_distribution", {})
    weekly_series: list = data.get("weekly_series", [])

    # --- Metrics ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("관심사 이동 지수 (TVD)", f"{tvd:.3f}", help="0~1, 클수록 관심사 변화가 큼")

    if delta:
        sorted_delta = sorted(delta.items(), key=lambda x: x[1], reverse=True)
        top_up = sorted_delta[0] if sorted_delta else None
        top_down = sorted_delta[-1] if len(sorted_delta) > 1 else None
        with col2:
            if top_up:
                st.metric("최다 증가 카테고리", top_up[0], f"+{top_up[1]:.1%}")
        with col3:
            if top_down and top_down[1] < 0:
                st.metric("최다 감소 카테고리", top_down[0], f"{top_down[1]:.1%}")

    # --- Radar Chart ---
    st.subheader("카테고리 분포 비교 (Radar)")
    all_cats = sorted(set(list(current_dist.keys()) + list(past_dist.keys())))
    if all_cats:
        current_vals = [current_dist.get(c, 0.0) for c in all_cats]
        past_vals = [past_dist.get(c, 0.0) for c in all_cats]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=current_vals + [current_vals[0]],
            theta=all_cats + [all_cats[0]],
            fill="toself",
            name="최근 7일",
            line_color="royalblue",
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=past_vals + [past_vals[0]],
            theta=all_cats + [all_cats[0]],
            fill="toself",
            name="7~30일 전",
            opacity=0.5,
            line_color="tomato",
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            showlegend=True,
            height=400,
        )
        st.plotly_chart(fig_radar, use_container_width=True)
    else:
        st.info("카테고리 데이터가 없습니다.")

    # --- Weekly Line Chart ---
    st.subheader("8주 카테고리 추이")
    if weekly_series:
        rows = []
        for week in weekly_series:
            label = week["week_start"]
            for cat, proportion in week["distribution"].items():
                rows.append({
                    "주차": label,
                    "카테고리": cat,
                    "비중": proportion,
                    "링크 수": round(proportion * week["total"]),
                })
        df = pd.DataFrame(rows)
        if not df.empty:
            fig_line = px.line(
                df,
                x="주차",
                y="비중",
                color="카테고리",
                markers=True,
                title="주차별 카테고리 비중",
            )
            fig_line.update_layout(height=350)
            st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("주차별 데이터가 없습니다.")
