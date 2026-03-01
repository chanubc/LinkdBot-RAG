# Phase 4: Insight Dashboard (Streamlit)

## 1. Objectives
- 텔레그램 봇(행동/대화)의 한계를 보완하는 **백오피스(통찰/관리)** 구축.
- `app/domain` 계층에서 계산되는 핵심 알고리즘(Drift, Reactivation Score)의 투명한 시각화.
- 벡터 데이터베이스(pgvector)에 저장된 지식의 군집 상태 시각화.

## 2. Architecture & Boundary
- **분리 원칙:** Streamlit 앱은 DB(`infrastructure`)나 비즈니스 로직(`services`)에 직접 접근하지 않는다.
- **통신 방식:** 철저하게 클라이언트(Frontend)로서 작동하며, FastAPI의 `app/api/v1/dashboard/` 엔드포인트를 HTTP(httpx)로 호출.
- **디렉토리 위치:** 프로젝트 루트의 `dashboard/` 폴더 내에 독립적으로 구성 (`dashboard/app.py`).

## 3. 인증 흐름 (JWT + Cookie)

```
유저 → 텔레그램 /dashboard 입력
봇   → create_dashboard_token(telegram_id) → JWT (7일 만료)
봇   → 링크 전송: {DASHBOARD_URL}?token={JWT}

브라우저 → Streamlit 로드 (?token=JWT)
Streamlit → 쿠키에 JWT 저장 (7일, streamlit-cookies-controller)
Streamlit → GET /api/v1/dashboard/auth/me (Authorization: Bearer JWT)
FastAPI  → JWT 검증 → {telegram_id, first_name} 반환
Streamlit → session_state에 저장 → 4탭 접근 허용

다음 방문 → 쿠키에서 JWT 읽어 바로 인증 (봇 링크 불필요)
JWT 만료 → 쿠키 삭제 → 봇에서 /dashboard 재입력 안내
```

**핵심 결정:**
| 항목 | 결정 | 이유 |
|------|------|------|
| 인증 | JWT (HS256) + 브라우저 쿠키 | Stateless, InMemoryStateStore 불사용 |
| API 식별 | `/me` 패턴 (JWT → telegram_id 추출) | IDOR 방지 — URL에 telegram_id 노출 금지 |
| 차원축소 | PCA(2D)만 | t-SNE는 FastAPI worker 블로킹 위험 |
| Reactivation 후보 | `older_than_days=3` | 방금 저장한 글 추천 방지 |

## 4. API 엔드포인트 목록 (`/api/v1/dashboard/`)

| Method | Path | 역할 |
|--------|------|------|
| GET | `/auth/me` | JWT 검증 + {telegram_id, first_name} 반환 |
| GET | `/drift/me` | TVD + delta + 8주 시계열 |
| GET | `/reactivation/me?query=` | 미읽음 링크 점수 랭킹 (older_than_days=3) |
| GET | `/embeddings/me` | PCA 2D 좌표 (t-SNE 없음) |
| GET | `/links/me` | 링크 목록 (필터+페이지네이션) |
| PATCH | `/links/{link_id}/read` | 읽음 처리 |
| DELETE | `/links/{link_id}` | 삭제 |
| POST | `/report/trigger/me` | 주간 리포트 강제 실행 (BackgroundTasks) |

## 5. Core Features (4 Tabs)

### Tab 1: 📈 Interest Drift (관심사 변화 추적)
- `st.metric` 3개: TVD, 최다 증가/감소 카테고리
- `go.Scatterpolar` Radar: 최근7일 vs 7~30일 분포
- `px.line` Line: 8주 주차별 카테고리 비중

### Tab 2: 🔁 Reactivation Debugger (알고리즘 투명성)
- `st.text_input` → "점수 재계산" 버튼 → `client.get_reactivation(query=...)`
- `centroid_source` info badge (keyword vs recent_activity)
- 컬럼: 제목, 카테고리, 유사도(Similarity×0.6), 망각점수(Recency×0.4), 최종점수
- `px.bar` 상위 20개 구성 차트
- **점수 공식:** Score = Similarity × 0.6 + Recency × 0.4

### Tab 3: 🌌 Knowledge Universe (벡터 공간 시각화)
- "시각화 로드" 버튼 → `client.get_embeddings()` (PCA only, t-SNE 없음)
- `px.scatter` 2D: color=category, hover=title
- PCA 설명 분산 % 표시
- 카테고리별 링크 수 `st.bar_chart`

### Tab 4: 📁 Archive Manager (지식 관리자)
- "주간 브리핑 강제 실행" 버튼
- 필터: is_read / category / page_size
- `st.data_editor` 행 선택 (checkbox)
- 읽음 처리 / 삭제 (2단계 확인) → `st.rerun()`

## 6. Tech Stack & Dependencies

```
PyJWT>=2.8.0                         # JWT 생성/검증 (FastAPI 서버 + 봇)
scikit-learn>=1.4.0                  # PCA (FastAPI /embeddings/me)
streamlit>=1.35.0                    # 대시보드 UI
plotly>=5.22.0                       # 차트
pandas>=2.2.0                        # 데이터프레임
streamlit-cookies-controller>=0.4.0  # 브라우저 쿠키 관리
```

`httpx`, `numpy`는 기존 requirements.txt에 포함.

## 7. 환경변수

```
# FastAPI 서버 (.env)
DASHBOARD_JWT_SECRET=your-secret-key-here  # 필수 (기본값: change-me-in-production)
DASHBOARD_URL=http://localhost:8501          # Streamlit URL

# Streamlit 앱 (dashboard/.env.example 참고)
DASHBOARD_API_URL=http://localhost:8000
```

## 8. 실행

```bash
# FastAPI 서버
uvicorn app.main:app --reload

# Streamlit 대시보드
DASHBOARD_API_URL=http://localhost:8000 streamlit run dashboard/app.py

# JWT 생성 테스트
python -c "from app.core.jwt import create_dashboard_token; print(create_dashboard_token(YOUR_TELEGRAM_ID))"
```

## 9. 파일 목록

| 파일 | 유형 |
|------|------|
| `app/core/jwt.py` | **신규** (JWT 생성/검증) |
| `app/core/config.py` | 수정 (DASHBOARD_JWT_SECRET, DASHBOARD_URL 추가) |
| `app/api/dependencies/dashboard_auth.py` | **신규** (get_dashboard_telegram_id Depends) |
| `app/domain/repositories/i_link_repository.py` | 수정 (3개 abstract 메서드 추가) |
| `app/infrastructure/repository/link_repository.py` | 수정 (3개 메서드 구현) |
| `app/api/v1/endpoints/dashboard.py` | **신규** (8개 엔드포인트, /me 패턴) |
| `app/main.py` | 수정 (router 등록) |
| `app/application/services/message_router_service.py` | 수정 (/dashboard 명령어 추가) |
| `requirements.txt` | 수정 (6개 패키지 추가) |
| `dashboard/app.py` | **신규** |
| `dashboard/api_client.py` | **신규** |
| `dashboard/tabs/__init__.py` | **신규** |
| `dashboard/tabs/drift_tab.py` | **신규** |
| `dashboard/tabs/reactivation_tab.py` | **신규** |
| `dashboard/tabs/knowledge_tab.py` | **신규** |
| `dashboard/tabs/archive_tab.py` | **신규** |
| `dashboard/.env.example` | **신규** |
