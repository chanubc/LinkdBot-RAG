"""Synchronous httpx client for Streamlit dashboard."""
import os

import httpx
import streamlit as st

BASE_URL = os.getenv("DASHBOARD_API_URL", "http://localhost:8000")
_TIMEOUT = 30.0


class DashboardAPIClient:
    def __init__(self, jwt_token: str, base_url: str = BASE_URL):
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {jwt_token}"}
        self._client = httpx.Client(timeout=_TIMEOUT)

    def _get(self, path: str, **params) -> dict:
        r = self._client.get(
            f"{self._base}{path}",
            headers=self._headers,
            params={k: v for k, v in params.items() if v is not None},
        )
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> dict:
        r = self._client.delete(f"{self._base}{path}", headers=self._headers)
        r.raise_for_status()
        return r.json()

    def verify_token(self) -> dict | None:
        """GET /api/v1/dashboard/auth/me — returns user info or None on error."""
        try:
            return self._get("/api/v1/dashboard/auth/me")
        except httpx.HTTPError:
            return None

    def get_drift(self) -> dict:
        return self._get("/api/v1/dashboard/drift/me")

    def get_reactivation(self, query: str | None = None) -> dict:
        params = {"query": query} if query else {}
        return self._get("/api/v1/dashboard/reactivation/me", **params)

    def get_embeddings(self) -> dict:
        return self._get("/api/v1/dashboard/embeddings/me")

    def get_graph_view(self) -> dict:
        return self._get("/api/v1/dashboard/graph/me")

    def get_links(
        self,
        is_read: bool | None = None,
        category: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        return self._get(
            "/api/v1/dashboard/links/me",
            is_read=is_read,
            category=category,
            page=page,
            page_size=page_size,
        )

    def delete_link(self, link_id: int) -> dict:
        return self._delete(f"/api/v1/dashboard/links/{link_id}")

    def get_stats(self) -> dict:
        return self._get("/api/v1/dashboard/stats/me")

    def search(self, q: str, top_k: int = 10) -> dict:
        return self._get("/api/v1/dashboard/search/me", q=q, top_k=top_k)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DashboardAPIClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()


@st.cache_data(ttl=30, show_spinner=False)
def cached_get_stats(jwt_token: str, base_url: str = BASE_URL) -> dict:
    with DashboardAPIClient(jwt_token=jwt_token, base_url=base_url) as c:
        return c.get_stats()


@st.cache_data(ttl=30, show_spinner=False)
def cached_get_drift(jwt_token: str, base_url: str = BASE_URL) -> dict:
    with DashboardAPIClient(jwt_token=jwt_token, base_url=base_url) as c:
        return c.get_drift()


@st.cache_data(ttl=30, show_spinner=False)
def cached_get_reactivation(jwt_token: str, base_url: str = BASE_URL) -> dict:
    with DashboardAPIClient(jwt_token=jwt_token, base_url=base_url) as c:
        return c.get_reactivation()


@st.cache_data(ttl=30, show_spinner=False)
def cached_get_embeddings(jwt_token: str, base_url: str = BASE_URL) -> dict:
    with DashboardAPIClient(jwt_token=jwt_token, base_url=base_url) as c:
        return c.get_embeddings()


@st.cache_data(ttl=30, show_spinner=False)
def cached_get_graph_view(jwt_token: str, base_url: str = BASE_URL) -> dict:
    with DashboardAPIClient(jwt_token=jwt_token, base_url=base_url) as c:
        return c.get_graph_view()
