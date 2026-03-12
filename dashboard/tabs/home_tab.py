"""🏠 홈 탭 — 관심사 분석 배너 + 지식 그래프 + 주간 요약."""
import math

import plotly.graph_objects as go
import streamlit as st

from dashboard.api_client import (
    DashboardAPIClient,
    cached_get_drift,
    cached_get_graph_view,
    cached_get_stats,
)
from dashboard.colors import CATEGORY_COLORS, DEFAULT_COLOR
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


def render(client: DashboardAPIClient) -> None:
    jwt_token: str = st.session_state["jwt_token"]
    with st.spinner("로딩 중..."):
        try:
            stats = cached_get_stats(jwt_token)
            drift = cached_get_drift(jwt_token)
            graph = cached_get_graph_view(jwt_token)
        except Exception as e:
            logger.error(f"Home tab data load failed: {e}")
            st.error(f"데이터 로딩 실패: {e}")
            return

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
            line={"width": 1, "color": "rgba(148, 163, 184, 0.25)"},
            hoverinfo="none",
            showlegend=False,
        )
    )

    # 카테고리 노드: 카테고리별 고유 색상 + 네온 글로우
    category_nodes = [n for n in nodes if n.get("type") == "category"]
    for node in category_nodes:
        color = CATEGORY_COLORS.get(node.get("category", ""), DEFAULT_COLOR)
        pos = positions.get(node["id"])
        if not pos:
            continue
        fig.add_trace(
            go.Scatter(
                x=[pos[0]],
                y=[pos[1]],
                mode="markers+text",
                text=[node["label"]],
                textposition="top center",
                marker={
                    "size": node.get("size", 22),
                    "color": color,
                    "line": {"width": 2, "color": color},
                    "opacity": 0.95,
                },
                hovertemplate=f"<b>{node['label']}</b><extra></extra>",
                name=node["label"],
                showlegend=True,
            )
        )

    # 링크 노드: 부모 카테고리 색상의 밝은 변형
    link_nodes = [n for n in nodes if n.get("type") == "link"]
    # 카테고리별로 묶어서 한 번에 렌더링
    links_by_category: dict[str, list] = {}
    for node in link_nodes:
        cat = node.get("category", "")
        links_by_category.setdefault(cat, []).append(node)

    for cat, cat_links in links_by_category.items():
        color = CATEGORY_COLORS.get(cat, DEFAULT_COLOR)
        x_vals = []
        y_vals = []
        custom = []
        for node in cat_links:
            pos = positions.get(node["id"])
            if not pos:
                continue
            x_vals.append(pos[0])
            y_vals.append(pos[1])
            custom.append([node.get("title"), node.get("category"), node.get("url")])

        if not x_vals:
            continue
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="markers",
                marker={
                    "size": 7,
                    "color": color,
                    "opacity": 0.6,
                    "line": {"width": 1, "color": color},
                },
                customdata=custom,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>카테고리: %{customdata[1]}"
                    "<br>%{customdata[2]}<extra></extra>"
                ),
                showlegend=False,
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
