"""Phase 4 (Redesign): LinkdBot Personal Knowledge Dashboard.

구조:
- layout="centered" (모바일 대응)
- 사이드바: Advanced View 토글만
- 탭: 🏠 홈 | 🔍 탐색 | 📈 트렌드 | 🗂 보관함 (단축 이름)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.logger import logger, setup_logging

setup_logging()

import streamlit as st

st.set_page_config(
    page_title="LinkdBot Dashboard",
    page_icon="📊",
    layout="centered",
)

from streamlit_cookies_controller import CookieController

from dashboard.api_client import DashboardAPIClient
from dashboard.tabs import discover_tab, home_tab, library_tab, trends_tab

COOKIE_KEY = "linkdbot_dashboard_jwt"
controller = CookieController()

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
if "telegram_id" not in st.session_state:
    jwt_token: str | None = controller.get(COOKIE_KEY)

    if not jwt_token:
        jwt_token = st.query_params.get("token")
        if jwt_token:
            controller.set(COOKIE_KEY, jwt_token, max_age=7 * 24 * 3600)

    if jwt_token:
        _client = DashboardAPIClient(jwt_token=jwt_token)
        result = _client.verify_token()
        if result:
            st.session_state.update(
                {
                    "telegram_id": result["telegram_id"],
                    "first_name": result.get("first_name"),
                    "jwt_token": jwt_token,
                }
            )
            if "token" in st.query_params:
                st.query_params.clear()
                st.rerun()
        else:
            controller.remove(COOKIE_KEY)
            st.error(
                "세션이 만료되었습니다. 텔레그램 봇에서 /dashboard를 다시 입력해주세요."
            )
            st.stop()
    else:
        st.info(
            "텔레그램 봇에서 `/dashboard` 명령어를 입력하면 개인 대시보드 링크를 받을 수 있습니다."
        )
        st.stop()

# ---------------------------------------------------------------------------
# Main Dashboard
# ---------------------------------------------------------------------------
client = DashboardAPIClient(jwt_token=st.session_state["jwt_token"])
first_name: str = st.session_state.get("first_name") or ""

# 사이드바: Advanced View 토글만
with st.sidebar:
    st.markdown(f"### 👋 {first_name}" if first_name else "### 📊 LinkdBot")
    st.divider()
    advanced = st.toggle(
        "🔬 Advanced View", value=False, help="TVD, 점수 공식 등 기술 지표를 표시합니다"
    )
    st.divider()
    st.caption("LinkdBot Knowledge Dashboard")

st.title("📊 나의 지식 대시보드")

tab1, tab2, tab3, tab4 = st.tabs(["🏠 홈", "🔍 탐색", "📈 트렌드", "🗂 보관함"])

with tab1:
    home_tab.render(client, advanced)

with tab2:
    discover_tab.render(client)

with tab3:
    trends_tab.render(advanced)

with tab4:
    library_tab.render(client)
