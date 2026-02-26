# CLAUDE.md

Guidance for Claude Code when working with LinkdBot-RAG.

## 🎯 Project Identity

**LinkdBot-RAG** — Proactive AI Knowledge Copilot

- Store user-shared links (Telegram)
- Convert content into structured knowledge
- Detect interest drift & reactivate knowledge
- Send proactive weekly insights

**Tech Stack:** Python 3.11+, FastAPI (Async), PostgreSQL + pgvector, SQLAlchemy, OpenAI API, Telegram Bot, Notion API

**Current Phase:** Phase 2 (Complete) → Phase 3 (Proactive Agent, In Progress)

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

### Type Hints & Async
- 모든 함수/메서드에 **Type Hint** 필수
- DB/API 등 모든 I/O는 **async/await** 사용

### DI 규칙 (핵심)
```python
# ❌ 금지: 내부에서 직접 인스턴스화
class SomeUseCase:
    def __init__(self):
        self.repo = UserRepository(self.db)

# ✅ 올바른 방식: Interface로 의존성 선언
class SomeUseCase:
    def __init__(self, user_repo: IUserRepository):
        self.repo = user_repo

# ✅ DI 팩토리에서만 concrete class 생성
def get_some_usecase(
    user_repo: UserRepository = Depends(get_user_repository),
) -> SomeUseCase:
    return SomeUseCase(user_repo)
```

### Commit Convention
- Format: `#이슈번호 [prefix] : 메시지`
- Prefixes: `[feat]`, `[fix]`, `[add]`, `[chore]`, `[docs]`, `[refactor]`, `[test]`
- Example: `#42 [feat] : Add search_usecase`

### PR Convention
- Title: `[PREFIX/#이슈번호] 작업 제목`
- Use `--merge` flag when merging (no squash/rebase)
- No URL in PR body

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
3. Follow coding conventions above

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
