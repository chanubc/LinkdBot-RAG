"""🔍 탐색 탭 — 오늘의 추천글 + 스마트 검색 + 잊고 있던 글."""
from datetime import datetime, timedelta, timezone
from html import escape

import streamlit as st

from dashboard.api_client import DashboardAPIClient, cached_get_reactivation
from dashboard.logger import logger

CATEGORIES = ["전체", "AI", "Dev", "Career", "Business", "Science", "Design", "Health", "Productivity", "Education", "Other"]


def render(client: DashboardAPIClient) -> None:
    jwt_token: str = st.session_state["jwt_token"]

    # ── 오늘 읽으면 좋은 글 ───────────────────────────────────────
    st.subheader("🔥 오늘 읽으면 좋은 글")
    st.caption("최근 관심사 기반으로 오래 묵혀둔 글을 추천합니다")

    with st.spinner("추천 로딩 중..."):
        try:
            reactivation = cached_get_reactivation(jwt_token)
        except Exception as e:
            logger.error(f"Reactivation load failed: {e}")
            st.error(f"로딩 실패: {e}")
            reactivation = {}

    all_items = reactivation.get("items", [])
    top3 = all_items[:3]
    if not top3:
        st.info("재활성화 후보가 없습니다. 링크를 더 저장하거나 3일 후에 다시 확인하세요.")
    else:
        for link in top3:
            _render_recommendation_card(link)

    st.divider()

    # ── 스마트 검색 ───────────────────────────────────────────────
    st.subheader("🔍 스마트 검색")
    st.caption("저장한 링크를 의미 기반으로 검색합니다")

    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        query = st.text_input("검색어", placeholder="예: 머신러닝, LLM 최적화, 커리어 전환",
                              label_visibility="collapsed")
    with col2:
        search_btn = st.button("검색", type="primary", use_container_width=True)

    if search_btn and query.strip():
        with st.spinner("검색 중..."):
            try:
                data = client.search(q=query.strip())
                st.session_state["search_results"] = data
                st.session_state["search_query"] = query.strip()
                logger.info(f"Search: '{query.strip()}' → {len(data.get('results', []))} results")
            except Exception as e:
                logger.error(f"Search failed: {e}")
                st.error(f"검색 실패: {e}")

    if "search_results" in st.session_state:
        results = st.session_state["search_results"].get("results", [])
        q_label = st.session_state.get("search_query", "")
        st.caption(f"**'{q_label}'** 검색 결과 — {len(results)}개")

        if not results:
            st.info("검색 결과가 없습니다.")
        else:
            seen_link_ids: set[int] = set()
            for r in results:
                link_id = r.get("link_id")
                if link_id in seen_link_ids:
                    continue
                seen_link_ids.add(link_id)
                _render_result_card(r)

    st.divider()

    # ── 잊고 있던 글 ─────────────────────────────────────────────
    st.subheader("🔁 잊고 있던 글")
    st.caption("14일 이상 저장해두고 읽지 않은 글 중 관심사와 유사한 글을 추천합니다")

    if st.button("불러오기", key="forgotten_load"):
        st.session_state.pop("forgotten_data", None)

    if "forgotten_data" not in st.session_state:
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        forgotten = [
            i for i in all_items
            if i.get("created_at") and
            i["created_at"][:10] <= cutoff.date().isoformat()
        ]
        st.session_state["forgotten_data"] = forgotten

    forgotten = st.session_state.get("forgotten_data", [])

    if not forgotten:
        st.info("14일 이상 된 미열람 글이 없습니다.")
    else:
        st.caption(f"{len(forgotten)}개 발견")
        for item in forgotten[:10]:
            _render_forgotten_card(item)


def _safe_link(title: str, url: str | None) -> str:
    """URL scheme 검증 + title 마크다운 이스케이프 후 링크 반환."""
    safe_title = escape(title).replace("[", "\\[").replace("]", "\\]")
    if url and url.startswith(("http://", "https://")):
        safe_url = url.replace(")", "%29").replace('"', "%22")
        return f"**[{safe_title}]({safe_url})**"
    return f"**{safe_title}**"


def _render_recommendation_card(link: dict) -> None:
    with st.container(border=True):
        url = link.get("url")
        title = link.get("title", "제목 없음")
        cat = link.get("category", "")
        summary = link.get("summary", "")
        similarity = link.get("similarity", 0)
        recency = link.get("recency", 0)

        if similarity * 0.6 >= recency * 0.4:
            reason = "✨ 최근 관심사와 유사한 글"
        else:
            reason = "🕐 오랫동안 읽지 않은 글"

        st.markdown(_safe_link(title, url))
        st.caption(f"{cat}  ·  {reason}")
        if summary:
            st.write(summary[:120] + ("..." if len(summary) > 120 else ""))


def _render_result_card(r: dict) -> None:
    with st.container(border=True):
        st.markdown(_safe_link(r.get("title", "제목 없음"), r.get("url")))
        st.caption(r.get("category", ""))
        chunk = r.get("chunk_content", "")
        if chunk:
            st.write(chunk[:150] + ("..." if len(chunk) > 150 else ""))


def _render_forgotten_card(item: dict) -> None:
    with st.container(border=True):
        st.markdown(_safe_link(item.get("title", "제목 없음"), item.get("url")))
        created = item.get("created_at", "")[:10]
        st.caption(f"{item.get('category', '')}  ·  저장일 {created}")
        summary = item.get("summary", "")
        if summary:
            st.write(summary[:120] + ("..." if len(summary) > 120 else ""))
