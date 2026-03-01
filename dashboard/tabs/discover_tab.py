"""🔍 탐색 탭 — 스마트 검색 + 잊고 있던 글."""
import streamlit as st

from dashboard.api_client import DashboardAPIClient, cached_get_reactivation
from dashboard.logger import logger

CATEGORIES = ["전체", "AI", "Dev", "Career", "Business", "Science", "Other"]


def render(client: DashboardAPIClient) -> None:
    # ── 스마트 검색 ───────────────────────────────────────────────
    st.subheader("🔍 스마트 검색")
    st.caption("저장한 링크를 의미 기반으로 검색합니다")

    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        query = st.text_input("검색어", placeholder="예: 머신러닝, LLM 최적화, 커리어 전환",
                              label_visibility="collapsed")
    with col2:
        search_btn = st.button("검색", type="primary", width='stretch')

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
        with st.spinner("분석 중..."):
            try:
                data = cached_get_reactivation(st.session_state["jwt_token"])
                # 14일 이상만 필터
                items = data.get("items", [])
                from datetime import datetime, timezone, timedelta
                cutoff = datetime.now(timezone.utc) - timedelta(days=14)
                forgotten = [
                    i for i in items
                    if i.get("created_at") and
                    i["created_at"][:10] <= cutoff.date().isoformat()
                ]
                st.session_state["forgotten_data"] = forgotten
            except Exception as e:
                st.error(f"로딩 실패: {e}")
                return

    forgotten = st.session_state.get("forgotten_data", [])

    if not forgotten:
        st.info("14일 이상 된 미열람 글이 없습니다.")
    else:
        st.caption(f"{len(forgotten)}개 발견")
        for item in forgotten[:10]:
            _render_forgotten_card(item)


def _render_result_card(r: dict) -> None:
    with st.container(border=True):
        st.markdown(f"**{r.get('title', '제목 없음')}**")
        col1, col2 = st.columns([0.8, 0.2])
        with col1:
            st.caption(r.get("category", ""))
            chunk = r.get("chunk_content", "")
            if chunk:
                st.write(chunk[:150] + ("..." if len(chunk) > 150 else ""))
        with col2:
            url = r.get("url")
            if url:
                st.link_button("🔗 열기", url, width='stretch')


def _render_forgotten_card(item: dict) -> None:
    with st.container(border=True):
        st.markdown(f"**{item.get('title', '제목 없음')}**")
        col1, col2 = st.columns([0.8, 0.2])
        with col1:
            created = item.get("created_at", "")[:10]
            st.caption(f"{item.get('category', '')}  ·  저장일 {created}")
            summary = item.get("summary", "")
            if summary:
                st.write(summary[:120] + ("..." if len(summary) > 120 else ""))
        with col2:
            url = item.get("url")
            if url:
                st.link_button("🔗 열기", url, width='stretch')
