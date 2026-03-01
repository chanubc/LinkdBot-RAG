"""Tab 3: Knowledge Universe — 벡터 공간 시각화 (PCA 2D)."""
import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import DashboardAPIClient


def render(client: DashboardAPIClient) -> None:
    st.header("🌌 Knowledge Universe")
    st.caption("1536차원 임베딩을 PCA로 2D 축소하여 지식 군집 시각화")

    if st.button("시각화 로드", type="primary"):
        st.session_state.pop("embeddings_data", None)

    if "embeddings_data" not in st.session_state:
        with st.spinner("임베딩 데이터 로딩 중 (최대 300개)..."):
            try:
                data = client.get_embeddings()
                st.session_state["embeddings_data"] = data
            except Exception as e:
                st.error(f"데이터 로딩 실패: {e}")
                return
    else:
        data = st.session_state["embeddings_data"]

    items: list[dict] = data.get("items", [])
    explained_variance: float | None = data.get("explained_variance")

    if not items:
        st.info("링크가 3개 이상 저장되어야 시각화가 가능합니다.")
        return

    if explained_variance is not None:
        st.metric("PCA 설명 분산", f"{explained_variance:.1%}", help="2개 주성분이 설명하는 분산 비율")

    df = pd.DataFrame(items)

    # --- Scatter plot ---
    fig = px.scatter(
        df,
        x="x",
        y="y",
        color="category",
        hover_name="title",
        hover_data={"x": False, "y": False, "category": True},
        title="Knowledge Universe (PCA 2D)",
    )
    fig.update_traces(marker=dict(size=8, opacity=0.75))
    fig.update_layout(height=550, legend_title="카테고리")
    st.plotly_chart(fig, use_container_width=True)

    # --- Category count bar ---
    st.subheader("카테고리별 링크 수")
    cat_counts = df["category"].value_counts().reset_index()
    cat_counts.columns = ["카테고리", "링크 수"]
    st.bar_chart(cat_counts.set_index("카테고리"))
