"""Tab 2: Reactivation Debugger — 알고리즘 투명성."""
import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import DashboardAPIClient


def render(client: DashboardAPIClient) -> None:
    st.header("🔁 Reactivation Debugger")
    st.caption("에이전트가 어떤 기준으로 링크를 추천하는지 Score 공식 세부 항목 공개")

    query = st.text_input(
        "관심사 키워드 입력 (비워두면 최근 활동 기반 centroid 사용)",
        placeholder="예: 머신러닝, LLM, 스타트업",
    )

    if st.button("점수 재계산", type="primary"):
        st.session_state["reactivation_query"] = query
        st.session_state.pop("reactivation_data", None)

    active_query = st.session_state.get("reactivation_query", "")

    if "reactivation_data" not in st.session_state:
        with st.spinner("점수 계산 중..."):
            try:
                data = client.get_reactivation(query=active_query or None)
                st.session_state["reactivation_data"] = data
            except Exception as e:
                st.error(f"데이터 로딩 실패: {e}")
                return
    else:
        data = st.session_state["reactivation_data"]

    centroid_source = data.get("centroid_source", "unknown")
    items: list[dict] = data.get("items", [])
    total = data.get("total", 0)

    source_label = "🔑 키워드 기반" if centroid_source == "keyword" else "📅 최근 활동 기반"
    st.info(f"Centroid 소스: {source_label} | 후보 링크: {total}개")

    if not items:
        st.warning("재활성화 후보 링크가 없습니다. (저장한 링크가 3일 이상 지난 미열람 링크가 필요합니다)")
        return

    # --- DataFrame ---
    df = pd.DataFrame([
        {
            "제목": i["title"],
            "카테고리": i["category"],
            f"유사도(×0.6)": round(i["similarity"] * 0.6, 4),
            f"망각점수(×0.4)": round(i["recency"] * 0.4, 4),
            "최종 점수": i["score"],
            "URL": i.get("url", ""),
            "id": i["id"],
        }
        for i in items
    ])

    st.dataframe(
        df.drop(columns=["id", "URL"]),
        use_container_width=True,
        hide_index=True,
    )

    # --- Bar chart (top 20) ---
    st.subheader("상위 20개 점수 구성")
    top20 = items[:20]
    if top20:
        bar_df = pd.DataFrame([
            {
                "제목": i["title"][:30] + ("…" if len(i["title"]) > 30 else ""),
                "유사도(×0.6)": round(i["similarity"] * 0.6, 4),
                "망각점수(×0.4)": round(i["recency"] * 0.4, 4),
            }
            for i in top20
        ])
        fig = px.bar(
            bar_df,
            x="제목",
            y=["유사도(×0.6)", "망각점수(×0.4)"],
            title="상위 20개 점수 구성",
            barmode="stack",
        )
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
