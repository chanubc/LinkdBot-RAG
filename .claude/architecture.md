# 🏗 Architecture

## Layer Structure

Presentation → Application → Infrastructure
                     ↓
                  Domain

---

## Responsibilities

### Presentation
- FastAPI routers
- Input validation
- Calls services

### Application
- Orchestrates flows
- Calls repositories
- Calls domain logic
- Calls external clients

### Domain
- Pure business logic
- Drift calculation
- Reactivation scoring
- No DB or HTTP imports

### Infrastructure
- DB access
- LLM calls
- Telegram client
- Jina Reader calls

---

## Dependency Rules

- Router may import services only.
- Services may import repositories + domain.
- Domain imports nothing external.
- Infrastructure must not import services.

Never break this direction.

---

## Database Schema (PostgreSQL + pgvector)

Parent-Child split for RAG quality. Defined in `app/models/`.

### `users`
- `telegram_id` (PK, BigInt)
- `notion_access_token` (Encrypted String) — `cryptography` 라이브러리 필수
- `notion_page_id` (String, Optional)

### `links` (Parent)
- `id` (PK, Serial)
- `user_id` (FK → users)
- `url` (String) — UNIQUE(user_id, url) 복합 제약
- `title` (String)
- `summary` (Text)
- `category` (String)
- `keywords` (Text) — JSON 배열 문자열, AI 추출
- `is_read` (Boolean, Default: False)
- `created_at` (Timestamp)

### `chunks` (Child)
- `id` (PK, Serial)
- `link_id` (FK → links)
- `content` (Text)
- `embedding` (Vector(1536), IVFFlat Index)
