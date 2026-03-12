# Dashboard Redesign Design Spec

**Date:** 2026-03-12
**Feature branch:** feat/#82-dashboard-redesign

---

## Goal

Streamlit 대시보드를 다크 테마로 전환하고, 탭 구조를 재편하며, AI 인사이트 시각화를 전용 탭으로 분리한다. 사용자가 기본 Streamlit UI에서 벗어난 세련된 다크 UI를 경험하도록 한다.

---

## Architecture

### 탭 구조

```
Before: 🏠 홈 | 🔍 탐색 | 📈 트렌드 | 🗂 보관함
After:  🏠 홈 | 📈 트렌드 | 🧠 인사이트 | 🔍 탐색
```

- 보관함 탭 제거 (library_tab.py 미사용 상태로 잔존)
- 탐색 탭 맨 우측으로 이동
- 인사이트 탭 신규 추가 (기존 Advanced 기능을 일반 사용자용으로 승격)
- 사이드바 전체 제거 (Advanced View 토글 포함)
- `advanced` 파라미터 모든 탭에서 제거

### 테마

`.streamlit/config.toml` 신규 생성:

```toml
[theme]
base                     = "dark"
primaryColor             = "#6366f1"
backgroundColor          = "#0a0f1a"
secondaryBackgroundColor = "#0f172a"
textColor                = "#e2e8f0"
```

### 공유 색상 팔레트

`dashboard/colors.py` 신규 생성 — 홈 탭 지식 그래프와 인사이트 탭 PCA scatter에서 공유:

```python
CATEGORY_COLORS = {
    "AI":       "#6366f1",
    "Dev":      "#f59e0b",
    "Career":   "#10b981",
    "Business": "#ef4444",
    "Science":  "#06b6d4",
    "Other":    "#8b5cf6",
    "Memo":     "#ec4899",
}
DEFAULT_COLOR = "#64748b"
```

---

## Tab Designs

### 🏠 홈 탭 (`home_tab.py`)

**변경:**
- `render(client, advanced)` → `render(client)` (advanced 파라미터 제거)
- `cached_get_reactivation` import 제거
- 오늘 추천글 섹션 제거 (→ 탐색 탭으로 이동)
- Advanced Drift expander 제거
- `_render_recommendation_card` 함수 삭제

**지식 그래프 색상 변경:**
- 현재: 카테고리 `#6366F1` / 링크 `#10B981` (타입 기반 2색)
- 변경: `CATEGORY_COLORS[category]` + fallback `DEFAULT_COLOR` (카테고리 기반 다색)
- 링크 노드: 부모 카테고리 색상의 밝은 변형 (`plotly.colors` tint 또는 고정 alpha)
- 네온 글로우 효과: `marker.line` + `opacity` 조합으로 Plotly에서 구현

**유지:**
- 관심사 분석 텍스트 배너
- 지식 그래프
- 이번 주 요약 메트릭 4개

---

### 📈 트렌드 탭 (`trends_tab.py`)

**변경:**
- `render(advanced)` → `render()` (advanced 파라미터 제거)
- `if advanced:` 블록 전체 삭제 (Drift Radar, PCA → 인사이트 탭으로 이동)
- `cached_get_drift`, `cached_get_embeddings` import 제거

**유지 (변경 없음):**
- 월별 저장 추이 Line chart
- 카테고리 분포 Bar chart
- 관심 키워드 Top 20 Horizontal bar
- 읽기 습관 메트릭 4개

---

### 🧠 인사이트 탭 (`insights_tab.py`) — 신규

**데이터 로드:** 탭 진입 시 3개 API 순차 호출
- `cached_get_drift` → Drift Radar + Delta DataFrame
- `cached_get_reactivation` → Reactivation Debugger
- `cached_get_embeddings` → Knowledge Universe

**섹션 1: 📈 Interest Drift — 관심사 변화**
- Radar Chart (Plotly `go.Scatterpolar`)
- 최근 7일(royalblue) vs 7~30일 전(tomato, opacity 0.5) 오버레이
- TVD metric + 상태 라벨 ("안정적" / "서서히 이동 중" / "급격한 변화")
- Delta DataFrame: 변화량 > 0.01인 카테고리만, "방향" 컬럼 포함

**섹션 2: 🔁 Reactivation Debugger — 추천 알고리즘 투명성**
- 설명 캡션: `Score = (유사도 × 0.6) + (시간 감쇠 × 0.4)`
- Pandas DataFrame 상위 15개
- 컬럼: 순위, 제목(40자 truncate), 카테고리, 유사도, 시간감쇠, 최종점수
- `st.column_config.ProgressColumn` 적용 (유사도, 시간감쇠, 최종점수)
- 후보 없을 시 안내 메시지

**섹션 3: 🌌 Knowledge Universe — 나의 지식 공간**
- PCA 2D Scatter (`plotly.express.scatter`)
- `color="category"` + `color_discrete_map=CATEGORY_COLORS`
- 축 숨김 (`xaxis.visible=False`, `yaxis.visible=False`)
- hover: 제목, 카테고리 (x/y 숨김)
- 설명 분산 caption 표시
- 3개 미만 시 안내 메시지

---

### 🔍 탐색 탭 (`discover_tab.py`)

**변경:**
- 탭 최상단에 "🔥 오늘 읽으면 좋은 글" 섹션 추가
  - `cached_get_reactivation` 호출, top3 표시
  - `_render_recommendation_card` 함수 추가
- 기존 카드 함수 하이퍼링크로 변경:
  - `st.link_button("🔗", url)` → `st.markdown(f"**[{title}]({url})**")`
  - `_render_result_card`, `_render_forgotten_card` 수정

**유지:**
- 스마트 검색 섹션
- 잊고 있던 글 섹션

---

## File Map

| 파일 | 작업 |
|------|------|
| `.streamlit/config.toml` | 신규 생성 |
| `dashboard/colors.py` | 신규 생성 |
| `dashboard/app.py` | 사이드바 제거, 탭 4개 재배치, insights_tab import 추가 |
| `dashboard/tabs/__init__.py` | insights_tab export 추가 |
| `dashboard/tabs/home_tab.py` | 색상 팔레트 적용, advanced/추천글 제거 |
| `dashboard/tabs/trends_tab.py` | advanced 파라미터·블록 제거 |
| `dashboard/tabs/insights_tab.py` | 신규 생성 |
| `dashboard/tabs/discover_tab.py` | 추천글 섹션 추가, 하이퍼링크 적용 |

---

## Out of Scope

- 백엔드 API 변경 없음 (기존 엔드포인트 그대로 사용)
- `library_tab.py` 파일 삭제 안 함 (import만 제거)
- CSS 인젝션 없음 (config.toml만으로 테마 처리)
- 모바일 반응형 별도 작업 없음
