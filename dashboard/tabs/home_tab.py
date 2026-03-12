"""🏠 홈 탭 — 그래프 뷰 + 오늘의 추천 + 주간 요약."""
import math

import plotly.graph_objects as go
import streamlit as st

from dashboard.api_client import (
    DashboardAPIClient,
    cached_get_drift,
    cached_get_graph_view,
    cached_get_reactivation,
    cached_get_stats,
)
from dashboard.logger import logger


GRAPH_COLORS = {
    "category": "#6366F1",
    "link": "#10B981",
}


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
    jwt_token: str = st.session_state["jwt_token"]
    with st.spinner("로딩 중..."):
        try:
            stats = cached_get_stats(jwt_token)
            reactivation = cached_get_reactivation(jwt_token)
            drift = cached_get_drift(jwt_token)
            graph = cached_get_graph_view(jwt_token)
        except Exception as e:
            logger.error(f"Home tab data load failed: {e}")
            st.error(f"데이터 로딩 실패: {e}")
            return

    top3 = reactivation.get("items", [])[:3]

    tvd = drift.get("tvd", 0.0)
    delta = drift.get("delta", {})
    analysis_text = _drift_to_text(tvd, delta)
    st.info(f"🧠 **나의 관심사 분석** — {analysis_text}")

    st.subheader("🕸 지식 그래프")
    st.caption("카테고리와 저장한 링크 관계를 시각화합니다. 읽음 처리는 텔레그램에서만 가능합니다.")
    _render_graph_view(graph)

    st.divider()

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

    st.subheader("🔥 오늘 읽으면 좋은 글")

    if not top3:
        st.info("재활성화 후보가 없습니다. 링크를 더 저장하거나 3일 후에 다시 확인하세요.")
    else:
        for link in top3:
            _render_recommendation_card(link, advanced)

    if advanced:
        with st.expander("🔬 Drift 세부 지표", expanded=False):
            st.metric("TVD", f"{tvd:.3f}")
            if delta:
                import pandas as pd

                df = pd.DataFrame(
                    [
                        {"카테고리": k, "변화량": round(v, 3)}
                        for k, v in sorted(delta.items(), key=lambda x: x[1], reverse=True)
                    ]
                )
                st.dataframe(df, use_container_width=True, hide_index=True)


def _render_graph_view(graph: dict) -> None:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not nodes or not edges:
        st.info("그래프를 그릴 데이터가 아직 부족합니다.")
        return

    positions = _build_graph_positions(nodes, edges)
    edge_x: list[float] = []
    edge_y: list[float] = []
    for edge in edges:
        source = positions.get(edge["source"])
        target = positions.get(edge["target"])
        if not source or not target:
            continue
        edge_x.extend([source[0], target[0], None])
        edge_y.extend([source[1], target[1], None])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line={"width": 1, "color": "rgba(148, 163, 184, 0.45)"},
            hoverinfo="none",
            showlegend=False,
        )
    )

    for node_type in ("category", "link"):
        typed_nodes = [node for node in nodes if node.get("type") == node_type]
        if not typed_nodes:
            continue

        fig.add_trace(
            go.Scatter(
                x=[positions[node["id"]][0] for node in typed_nodes],
                y=[positions[node["id"]][1] for node in typed_nodes],
                mode="markers+text" if node_type == "category" else "markers",
                text=[node["label"] for node in typed_nodes] if node_type == "category" else None,
                textposition="top center",
                marker={
                    "size": [node.get("size", 16) for node in typed_nodes],
                    "color": GRAPH_COLORS[node_type],
                    "line": {"width": 1, "color": "white"},
                    "opacity": 0.9 if node_type == "category" else 0.75,
                },
                customdata=[[node.get("title"), node.get("category"), node.get("url")] for node in typed_nodes],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>카테고리: %{customdata[1]}"
                    "<br>%{customdata[2]}<extra></extra>"
                    if node_type == "link"
                    else "<b>%{text}</b><extra></extra>"
                ),
                name="카테고리" if node_type == "category" else "링크",
            )
        )

    fig.update_layout(
        height=420,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        xaxis={"visible": False},
        yaxis={"visible": False},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    )
    st.plotly_chart(fig, use_container_width=True)


def _build_graph_positions(nodes: list[dict], edges: list[dict]) -> dict[str, tuple[float, float]]:
    categories = [node for node in nodes if node.get("type") == "category"]
    links = [node for node in nodes if node.get("type") == "link"]
    positions: dict[str, tuple[float, float]] = {}

    if not categories:
        for index, node in enumerate(links):
            angle = (2 * math.pi * index) / max(len(links), 1)
            positions[node["id"]] = (math.cos(angle), math.sin(angle))
        return positions

    category_angles: dict[str, float] = {}
    for index, node in enumerate(categories):
        angle = (2 * math.pi * index) / len(categories)
        category_angles[node["id"]] = angle
        positions[node["id"]] = (0.42 * math.cos(angle), 0.42 * math.sin(angle))

    links_by_category: dict[str, list[str]] = {node["id"]: [] for node in categories}
    for edge in edges:
        if edge["source"] in links_by_category:
            links_by_category[edge["source"]].append(edge["target"])

    for category_id, link_ids in links_by_category.items():
        base_angle = category_angles[category_id]
        total = len(link_ids)
        for index, link_id in enumerate(link_ids):
            offset = 0 if total <= 1 else ((index / (total - 1)) - 0.5) * 0.9
            angle = base_angle + offset
            radius = 1.0 + (index % 3) * 0.08
            positions[link_id] = (radius * math.cos(angle), radius * math.sin(angle))

    unplaced_links = [node for node in links if node["id"] not in positions]
    for index, node in enumerate(unplaced_links):
        angle = (2 * math.pi * index) / max(len(unplaced_links), 1)
        positions[node["id"]] = (1.15 * math.cos(angle), 1.15 * math.sin(angle))

    return positions


def _render_recommendation_card(link: dict, advanced: bool) -> None:
    with st.container(border=True):
        col1, col2 = st.columns([0.88, 0.12])

        with col1:
            st.markdown(f"**{link['title']}**")
            cat = link.get("category", "")
            score = link.get("score", 0)

            similarity = link.get("similarity", 0)
            recency = link.get("recency", 0)
            if similarity * 0.6 >= recency * 0.4:
                reason = "✨ 최근 관심사와 유사한 글"
            else:
                reason = "🕐 오랫동안 읽지 않은 글"

            st.caption(f"{cat}  ·  {reason}")
            summary = link.get("summary", "")
            if summary:
                st.write(summary[:120] + ("..." if len(summary) > 120 else ""))

            if advanced:
                st.caption(
                    f"Score: {score:.3f} (유사도 {link.get('similarity', 0):.2f} · 망각 {link.get('recency', 0):.2f})"
                )

        with col2:
            url = link.get("url")
            if url:
                st.link_button("🔗", url, use_container_width=True)
