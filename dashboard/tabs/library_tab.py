"""🗂 보관함 탭 — 카드 리스트 + 상단 액션 영역 (모바일 대응)."""
import math

import streamlit as st

from dashboard.api_client import DashboardAPIClient
from dashboard.logger import logger

CATEGORIES = ["전체", "AI", "Dev", "Career", "Business", "Science", "Other", "Memo"]


def render(client: DashboardAPIClient) -> None:
    # ── 필터 (상단 고정) ──────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        read_filter = st.selectbox("읽음 여부", ["전체", "미열람", "열람"], index=0,
                                   label_visibility="collapsed")
    with col2:
        cat_filter = st.selectbox("카테고리", CATEGORIES, index=0,
                                  label_visibility="collapsed")
    with col3:
        page_size = st.selectbox("개수", [20, 50, 100], index=0,
                                 label_visibility="collapsed")

    is_read_param: bool | None = None
    if read_filter == "미열람":
        is_read_param = False
    elif read_filter == "열람":
        is_read_param = True
    cat_param = None if cat_filter == "전체" else cat_filter

    if "lib_page" not in st.session_state:
        st.session_state["lib_page"] = 1

    # ── 데이터 로드 ───────────────────────────────────────────────
    with st.spinner("로딩 중..."):
        try:
            data = client.get_links(
                is_read=is_read_param,
                category=cat_param,
                page=st.session_state["lib_page"],
                page_size=page_size,
            )
        except Exception as e:
            logger.error(f"Library tab data load failed: {e}")
            st.error(f"데이터 로딩 실패: {e}")
            return

    items = data.get("items", [])
    total = data.get("total", 0)
    page = data.get("page", 1)
    total_pages = max(1, math.ceil(total / page_size))

    st.caption(f"총 {total}개")

    # ── 선택 상태 초기화 ──────────────────────────────────────────
    if "lib_selected" not in st.session_state:
        st.session_state["lib_selected"] = set()

    # ── 선택 항목 액션 (상단 배치) ────────────────────────────────
    selected = st.session_state["lib_selected"]
    if selected:
        st.info(f"**{len(selected)}개 선택됨**")
        act_col1, act_col2, act_col3 = st.columns(3)
        with act_col1:
            if st.button("✅ 읽음 처리", use_container_width=True):
                errors = []
                for lid in list(selected):
                    try:
                        client.mark_link_read(lid)
                    except Exception as e:
                        errors.append(str(e))
                st.session_state["lib_selected"] = set()
                if errors:
                    st.error(f"일부 실패: {errors}")
                else:
                    st.success(f"{len(selected)}개 읽음 처리 완료")
                st.rerun()
        with act_col2:
            if st.button("🗑️ 삭제", use_container_width=True, type="secondary"):
                st.session_state["lib_confirm_delete"] = True
                st.rerun()
        with act_col3:
            if st.button("선택 해제", use_container_width=True):
                st.session_state["lib_selected"] = set()
                st.rerun()

    # ── 삭제 확인 ─────────────────────────────────────────────────
    if st.session_state.get("lib_confirm_delete"):
        st.warning(f"정말로 {len(selected)}개를 삭제하시겠습니까?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("확인", type="primary", use_container_width=True):
                errors = []
                for lid in list(selected):
                    try:
                        client.delete_link(lid)
                    except Exception as e:
                        errors.append(str(e))
                st.session_state["lib_selected"] = set()
                st.session_state["lib_confirm_delete"] = False
                if errors:
                    st.error(f"일부 실패: {errors}")
                else:
                    st.success("삭제 완료")
                st.rerun()
        with c2:
            if st.button("취소", use_container_width=True):
                st.session_state["lib_confirm_delete"] = False
                st.rerun()

    # ── 주간 브리핑 강제 실행 ─────────────────────────────────────
    with st.expander("⚡ 주간 브리핑 강제 실행"):
        if st.button("지금 실행", type="primary"):
            try:
                client.trigger_report()
                st.success("요청 완료. 잠시 후 텔레그램으로 전송됩니다.")
            except Exception as e:
                st.error(f"실패: {e}")

    st.divider()

    # ── 카드 리스트 ───────────────────────────────────────────────
    if not items:
        st.info("해당하는 링크가 없습니다.")
    else:
        for link in items:
            _render_link_card(link)

    # ── 페이지네이션 ──────────────────────────────────────────────
    st.divider()
    p1, p2, p3 = st.columns([1, 2, 1])
    with p1:
        if st.button("← 이전", disabled=(page <= 1), use_container_width=True):
            st.session_state["lib_page"] = max(1, page - 1)
            st.rerun()
    with p2:
        st.markdown(
            f"<p style='text-align:center; padding-top:8px'>{page} / {total_pages}</p>",
            unsafe_allow_html=True,
        )
    with p3:
        if st.button("다음 →", disabled=(page >= total_pages), use_container_width=True):
            st.session_state["lib_page"] = min(total_pages, page + 1)
            st.rerun()


def _render_link_card(link: dict) -> None:
    link_id = link["id"]
    selected: set = st.session_state.get("lib_selected", set())

    with st.container(border=True):
        col1, col2 = st.columns([0.08, 0.92])

        with col1:
            checked = st.checkbox(
                "선택", key=f"lib_chk_{link_id}",
                value=(link_id in selected),
                label_visibility="collapsed",
            )
            if checked:
                selected.add(link_id)
            else:
                selected.discard(link_id)
            st.session_state["lib_selected"] = selected

        with col2:
            read_icon = "✅" if link["is_read"] else "⬜"
            url = link.get("url")
            title = link.get("title", "제목 없음")

            header_col1, header_col2 = st.columns([0.8, 0.2])
            with header_col1:
                if url:
                    st.markdown(f"**[{title}]({url})**")
                else:
                    st.markdown(f"**{title}**")
            with header_col2:
                st.caption(f"{read_icon} {link.get('created_at', '')[:10]}")

            cat = link.get("category", "")
            summary = link.get("summary", "")
            st.caption(cat)
            if summary:
                st.write(summary[:100] + ("..." if len(summary) > 100 else ""))
