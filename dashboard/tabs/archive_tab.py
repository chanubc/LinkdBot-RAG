"""Tab 4: Archive Manager — 지식 관리자."""
import pandas as pd
import streamlit as st

from dashboard.api_client import DashboardAPIClient


def render(client: DashboardAPIClient) -> None:
    st.header("📁 Archive Manager")
    st.caption("링크 조회, 읽음 처리, 삭제 및 주간 브리핑 수동 실행")

    # --- Report trigger ---
    with st.expander("⚡ 주간 브리핑 강제 실행", expanded=False):
        if st.button("지금 실행", type="primary"):
            try:
                client.trigger_report()
                st.success("주간 브리핑 실행을 요청했습니다. 잠시 후 텔레그램으로 전송됩니다.")
            except Exception as e:
                st.error(f"실행 실패: {e}")

    st.divider()

    # --- Filters ---
    col1, col2, col3 = st.columns(3)
    with col1:
        read_filter = st.selectbox(
            "읽음 여부", ["전체", "미열람", "열람"], index=0
        )
    with col2:
        category_filter = st.text_input("카테고리 필터", placeholder="예: AI, Dev")
    with col3:
        page_size = st.selectbox("페이지 크기", [25, 50, 100], index=1)

    is_read_param: bool | None = None
    if read_filter == "미열람":
        is_read_param = False
    elif read_filter == "열람":
        is_read_param = True

    if "archive_page" not in st.session_state:
        st.session_state["archive_page"] = 1

    if st.button("🔄 새로고침"):
        st.session_state["archive_page"] = 1

    # --- Load data ---
    with st.spinner("링크 로딩 중..."):
        try:
            data = client.get_links(
                is_read=is_read_param,
                category=category_filter or None,
                page=st.session_state["archive_page"],
                page_size=page_size,
            )
        except Exception as e:
            st.error(f"데이터 로딩 실패: {e}")
            return

    items: list[dict] = data.get("items", [])
    total: int = data.get("total", 0)
    page: int = data.get("page", 1)

    st.caption(f"총 {total}개 | 페이지 {page}")

    # --- Pagination ---
    import math
    total_pages = max(1, math.ceil(total / page_size))
    pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
    with pcol1:
        if st.button("← 이전", disabled=(page <= 1)):
            st.session_state["archive_page"] = max(1, page - 1)
            st.rerun()
    with pcol2:
        st.markdown(f"<p style='text-align:center'>{page} / {total_pages}</p>", unsafe_allow_html=True)
    with pcol3:
        if st.button("다음 →", disabled=(page >= total_pages)):
            st.session_state["archive_page"] = min(total_pages, page + 1)
            st.rerun()

    if not items:
        st.info("해당하는 링크가 없습니다.")
        return

    # --- Table with selection ---
    df = pd.DataFrame([
        {
            "선택": False,
            "ID": i["id"],
            "제목": i["title"],
            "카테고리": i["category"],
            "열람": "✅" if i["is_read"] else "⬜",
            "저장일": i["created_at"][:10] if i["created_at"] else "-",
            "URL": i.get("url") or "-",
        }
        for i in items
    ])

    edited = st.data_editor(
        df,
        column_config={
            "선택": st.column_config.CheckboxColumn("선택", default=False),
            "URL": st.column_config.LinkColumn("URL"),
        },
        use_container_width=True,
        hide_index=True,
        disabled=["ID", "제목", "카테고리", "열람", "저장일", "URL"],
    )

    selected_ids = edited.loc[edited["선택"] == True, "ID"].tolist()

    # --- Bulk actions ---
    if selected_ids:
        st.write(f"**{len(selected_ids)}개 선택됨**")
        action_col1, action_col2 = st.columns(2)

        with action_col1:
            if st.button("✅ 읽음 처리"):
                errors = []
                for link_id in selected_ids:
                    try:
                        client.mark_link_read(link_id)
                    except Exception as e:
                        errors.append(str(e))
                if errors:
                    st.error(f"일부 실패: {errors}")
                else:
                    st.success(f"{len(selected_ids)}개 읽음 처리 완료")
                    st.rerun()

        with action_col2:
            if "delete_confirm" not in st.session_state:
                st.session_state["delete_confirm"] = False

            if not st.session_state["delete_confirm"]:
                if st.button("🗑️ 삭제", type="secondary"):
                    st.session_state["delete_confirm"] = True
                    st.rerun()
            else:
                st.warning(f"정말로 {len(selected_ids)}개를 삭제하시겠습니까?")
                conf_col1, conf_col2 = st.columns(2)
                with conf_col1:
                    if st.button("확인 삭제", type="primary"):
                        errors = []
                        for link_id in selected_ids:
                            try:
                                client.delete_link(link_id)
                            except Exception as e:
                                errors.append(str(e))
                        st.session_state["delete_confirm"] = False
                        if errors:
                            st.error(f"일부 실패: {errors}")
                        else:
                            st.success(f"{len(selected_ids)}개 삭제 완료")
                        st.rerun()
                with conf_col2:
                    if st.button("취소"):
                        st.session_state["delete_confirm"] = False
                        st.rerun()
