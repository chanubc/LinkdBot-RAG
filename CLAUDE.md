# CLAUDE.md

Guidance for Claude Code when working with LinkdBot-RAG.

## 🎯 Project Identity

**LinkdBot-RAG** — Proactive AI Knowledge Copilot

- Store user-shared links (Telegram)
- Convert content into structured knowledge
- Detect interest drift & reactivate knowledge
- Send proactive weekly insights

**Tech Stack:** Python 3.11+, FastAPI (Async), PostgreSQL + pgvector, SQLAlchemy, OpenAI API, Telegram Bot, Notion API (see [`.claude/stack.md`](./.claude/stack.md) for details)

**Current Phase:** Phase 2 (Complete) → Phase 3 (Proactive Agent, In Progress)

**Architecture Pattern:** Pragmatic Clean Architecture + **Port/Adapter (Hexagonal)** for external systems

---

## 🏗️ Architecture (Pragmatic Clean Architecture)

**Layers:** Presentation → Application → Domain/RAG ← Infrastructure

**Key Principles:**
- Keep domain logic pure
- Use FastAPI Depends for DI only
- Strict SRP: Prevent 'God Objects'
- Decouple External I/O: Depend on interfaces (ABC), not concrete classes
- No circular imports

**For detailed architecture, see [`.claude/architecture.md`](./.claude/architecture.md)**

---

## 📋 Quick Commands

```bash
# 개발 서버 실행
uvicorn app.main:app --reload

# 테스트 실행
pytest
pytest tests/path/to/test.py::test_function_name -v

# DB 마이그레이션
alembic upgrade head
alembic revision --autogenerate -m "description"

# 의존성 설치
pip install -r requirements.txt
```

---

## 🎮 Coding Conventions

See [`.claude/coding_rules.md`](./.claude/coding_rules.md) for detailed conventions including:
- Type Hints & Async requirements
- DI strategy (Interface types, DI factories)
- Domain, Repository, Service rules
- Commit & PR conventions

---

## 📚 Reference Documents

Essential reading before coding:

- **Architecture & DB Schema:** [`.claude/architecture.md`](./.claude/architecture.md)
- **Migration Plan:** [`.claude/migration_plan.md`](./.claude/migration_plan.md) (Phase 2 마이그레이션 히스토리)
- **Phase Specs:**
  - Phase 1 (수집 & 인프라): [`.claude/phases/phase1.md`](./.claude/phases/phase1.md)
  - Phase 2 (RAG & Agent): [`.claude/phases/phase2.md`](./.claude/phases/phase2.md)
  - Phase 3 (Proactive Agent): [`.claude/phases/phase3.md`](./.claude/phases/phase3.md)
- **Context & Logic:**
  - Drift Logic: [`.claude/context/drift.md`](./.claude/context/drift.md)
  - Reactivation Logic: [`.claude/context/reactivation.md`](./.claude/context/reactivation.md)
  - Vector Strategy: [`.claude/context/vector_strategy.md`](./.claude/context/vector_strategy.md)
- **Coding Rules:** [`.claude/coding_rules.md`](./.claude/coding_rules.md)
- **Tech Stack:** [`.claude/stack.md`](./.claude/stack.md)

---

## 🔄 Development Strategy

**Phase-based development:** Never implement future phase logic unless explicitly instructed.

**Before starting work:**
1. Read relevant Phase spec (`.claude/phases/phase{N}.md`)
2. Check architecture (`.claude/architecture.md`)
3. Follow coding conventions (see [`.claude/coding_rules.md`](./.claude/coding_rules.md))

---

## 📌 Git Workflow

See [`.claude/commands/start-feature.md`](./.claude/commands/start-feature.md) for detailed workflow.

**Quick summary:**
1. GitHub 이슈 생성
2. main 최신화
3. `feat/#이슈번호-설명` 브랜치 생성
4. 작업 후 PR 생성
5. "Create a merge commit" 선택 후 병합

---

## 📦 DB Schema Summary

- `users`: `telegram_id` (PK), `notion_access_token` (encrypted), `notion_page_id`
- `links`: `id`, `user_id` (FK), `url`, `title`, `summary`, `category`, `keywords`, `is_read`, `created_at` — UNIQUE(user_id, url)
- `chunks`: `id`, `link_id` (FK), `content`, `embedding` (Vector 1536)

See [`.claude/architecture.md`](./.claude/architecture.md) for full schema details.
