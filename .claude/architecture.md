# 🏗 Architecture

## Layer Structure

```
Presentation → Application → domain/repositories (Interface)
                                      ↑
                             infrastructure/repository (Impl)
```

의존 방향: **Presentation → Services → domain/repositories(Interface) ← infrastructure/repository(Impl)**

---

## Responsibilities

### Presentation
- FastAPI routers
- Input validation
- Calls services

### Application
- Orchestrates flows
- Depends on repository **interfaces** (not concrete classes)
- Calls domain logic
- Calls external clients

### Domain
- Pure business logic
- Drift calculation
- Reactivation scoring
- **Repository interfaces (ABC)** — `app/domain/repositories/`
- No DB or HTTP imports

### Infrastructure
- DB access (concrete repository implementations)
- LLM calls
- Telegram client
- Jina Reader calls

---

## Repository Interface Pattern

`app/domain/repositories/` — ABC 인터페이스 정의

```
app/domain/repositories/
  i_user_repository.py    IUserRepository (ABC)
  i_link_repository.py    ILinkRepository (ABC)
  i_chunk_repository.py   IChunkRepository (ABC)
```

`app/infrastructure/repository/` — 구현체

```
app/infrastructure/repository/
  user_repository.py      UserRepository(IUserRepository)
  link_repository.py      LinkRepository(ILinkRepository)
  chunk_repository.py     ChunkRepository(IChunkRepository)
```

Service는 반드시 Interface 타입으로 의존성을 선언한다.
DI 팩토리(`dependencies/`)에서만 concrete class를 인스턴스화한다.

---

## Dependency Rules

- Router may import services only.
- Services depend on **domain interfaces**, not concrete infrastructure classes.
- Domain imports nothing external (DB, HTTP, FastAPI 금지).
- Infrastructure implements domain interfaces; must not import services.
- DI factories (`app/api/dependencies/`) wire interfaces to implementations.

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
