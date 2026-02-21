# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LinkdBot-RAG — 사용자가 텔레그램으로 URL을 전송하면 자동으로 스크래핑, AI 분석, 벡터 임베딩 후 Notion에 저장하고 RAG 검색을 제공하는 백엔드 에이전트.

**Tech Stack:** Python 3.11+, FastAPI (Async), PostgreSQL (pgvector), SQLAlchemy, OpenAI API, Telegram Bot, Notion API

## Commands

```bash
# 개발 서버 실행
uvicorn app.main:app --reload

# 테스트 실행
pytest

# 단일 테스트 실행
pytest tests/path/to/test.py::test_function_name -v

# DB 마이그레이션
alembic upgrade head
alembic revision --autogenerate -m "description"

# 의존성 설치
pip install -r requirements.txt
```

## Architecture (Light Clean Architecture)

의존성 방향: **Presentation → Application → Domain → Infrastructure**

- **Presentation (`app/api/`):** FastAPI 라우터. 비즈니스 로직 작성 금지.
- **Application (`app/services/`):** Agent의 두뇌 역할 및 흐름 제어 (오케스트레이션).
- **Domain (`app/domain/`):** DB/API 의존성이 없는 순수 비즈니스 로직 (Scoring, Drift 계산).
- **Infrastructure (`app/infrastructure/`):** DB Repository, 외부 API Client (Notion, Telegram, OpenAI).
- **DI (Dependency Injection):** FastAPI `Depends`만 사용 (`app/api/dependencies.py`).

```
app/
├── api/            # Presentation: FastAPI 라우터만. 비즈니스 로직 금지.
│   ├── v1/endpoints/
│   │   ├── auth.py         # Notion OAuth 흐름
│   │   └── webhook.py      # Telegram 웹훅 수신
│   └── dependencies.py     # FastAPI Depends로 DI 주입
├── services/       # Application: 오케스트레이션 (흐름 제어)
│   ├── link_service.py     # 링크 처리 파이프라인 (Phase 1)
│   ├── agent_service.py    # RAG 에이전트 두뇌 (Phase 2)
│   └── report_service.py   # 주간 리포트 스케줄러 (Phase 3)
├── domain/         # Domain: DB/API 의존성 없는 순수 비즈니스 로직
│   ├── drift.py            # Interest Drift 계산 (Phase 3)
│   └── scoring.py          # Reactivation Score 계산 (Phase 3)
├── infrastructure/ # Infrastructure: 외부 시스템 연동
│   ├── llm/openai_client.py
│   ├── external/notion_client.py
│   └── repository/         # DB Repository
└── models/         # SQLAlchemy ORM 모델
```

## Key Flows

**링크 처리 파이프라인** (`app/services/link_service.py`, `BackgroundTasks`로 비동기 실행):
1. Scrape: Jina Reader API (`https://r.jina.ai/{url}`) → 마크다운 추출
2. AI Analysis: GPT-4o → 3줄 요약, 카테고리 분류, 키워드 추출
3. Embed: `text-embedding-3-small` → 500~1000자 청크 단위 벡터화
4. Save: DB (`Link`, `Chunk` 테이블) + Notion 페이지
5. Notify: 텔레그램으로 완료 알림

**Notion OAuth** (`app/api/v1/endpoints/auth.py`):
- `/auth/notion/login` → Notion 인증 페이지 리다이렉트 (state=telegram_id)
- `/auth/notion/callback` → 토큰 발급 → DB Upsert

## DB Schema

- `User`: `telegram_id` (PK), `notion_access_token` (암호화), `notion_page_id`
- `Link`: `id`, `user_id` (FK), `url`, `title`, `summary`, `category`, `keywords`, `is_read`, `created_at` — UNIQUE(user_id, url)
- `Chunk`: `id`, `link_id` (FK), `content`, `embedding` (Vector 1536)

> `notion_access_token`은 반드시 `cryptography` 라이브러리로 암호화하여 저장.

## Coding Conventions

- 모든 함수/메서드에 **Type Hint** 필수
- DB/API 등 모든 I/O는 **async/await** 사용
- DI는 외부 라이브러리 없이 FastAPI `Depends`만 사용 (`app/api/dependencies.py`)
- 새 파일 생성 전 기존 디렉토리 구조 확인 후 적절한 위치에 배치

## Phase Specs

코드 작성 전 해당 Phase 문서를 먼저 읽을 것:
- Phase 1 (수집 & 인프라): `.claude/phases/phase1.md`
- Phase 2 (RAG & Agent): `.claude/phases/phase2.md`
- Phase 3 (Proactive Agent): `.claude/phases/phase3.md`

상세 참고:
- Architecture & DB Schema: `.claude/architecture.md`
- Coding Rules: `.claude/coding_rules.md`
- Tech Stack: `.claude/stack.md`
- Drift / Reactivation / Vector: `.claude/context/`
