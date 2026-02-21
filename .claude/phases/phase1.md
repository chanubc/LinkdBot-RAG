# 🚀 Phase 1 — Core System

## Goal

Build a working link ingestion + semantic search system.

---

## Features

- Telegram webhook endpoint
- URL ingestion
- Jina Reader content extraction
- LLM summary + category + keyword generation
- Embedding creation
- Store in PostgreSQL (pgvector)
- Notion page creation
- Semantic search endpoint

---

## DB Schema (`app/models/`)

### `User`
- `telegram_id` (PK, BigInt)
- `notion_access_token` (Encrypted String) — `cryptography` 라이브러리 필수
- `notion_page_id` (String, Optional)

### `Link` (Parent)
- `id` (PK, Serial)
- `user_id` (FK → User)
- `url` (String) — UNIQUE(user_id, url) 복합 제약
- `title` (String)
- `summary` (Text) — AI 3줄 요약
- `category` (String) — AI 분류 e.g. 'AI', 'Dev', 'Career'
- `keywords` (Text) — JSON 배열 문자열 e.g. '["LLM", "RAG", "pgvector"]'
- `is_read` (Boolean, Default: False)
- `created_at` (Timestamp)

### `Chunk` (Child)
- `id` (PK, Serial)
- `link_id` (FK → Link)
- `content` (Text) — 500~1000자 단위 분할
- `embedding` (Vector(1536)) — pgvector IVFFlat Index

---

## Core Flows

### Notion OAuth (`app/api/v1/endpoints/auth.py`)
1. `GET /api/v1/auth/notion/login` → Notion 인증 페이지 리다이렉트 (state=telegram_id)
2. `GET /api/v1/auth/notion/callback` → Code 수신 → Access Token 발급 → DB Upsert

### Link Processing Pipeline (`app/services/link_service.py`, BackgroundTasks)
1. **Scrape:** Jina Reader API (`https://r.jina.ai/{url}`) → 마크다운 추출
2. **Analyze:** GPT-4o → 3줄 요약, 카테고리 분류, 핵심 키워드 추출
3. **Embed:** `text-embedding-3-small` → 500~1000자 청크 단위 벡터화
4. **Save:** DB (`links` + `chunks`) + Notion 페이지 (`app/infrastructure/external/notion_client.py`)
5. **Notify:** 텔레그램 완료 알림

---

## API Endpoints

- `POST /api/v1/webhook/telegram` — 텔레그램 메시지 수신
- `GET /api/v1/auth/notion/login` — 인증 시작
- `GET /api/v1/auth/notion/callback` — 인증 완료

---

## Exclusions

Do NOT implement:
- Drift logic
- Reactivation logic
- Weekly scheduler
- Streamlit dashboard

Focus only on ingestion and semantic retrieval.
