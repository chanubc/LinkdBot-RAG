# 🛠 Coding Rules

## DI Strategy

Use FastAPI Depends only.

**2가지 DI 패턴:**

### 1️⃣ Repository Pattern (DB I/O)
Service는 **Repository Interface 타입**으로 파라미터를 선언하고, DI 팩토리에서 concrete Repository를 주입한다.

```python
# ✅ UseCase — Repository Interface에만 의존
class SaveLinkUseCase:
    def __init__(
        self,
        link_repo: ILinkRepository,  # Interface 타입
        chunk_repo: IChunkRepository,
    ) -> None: ...

# ✅ DI factory — concrete Repository 인스턴스화
def get_link_repository(db: AsyncSession = Depends(get_db)) -> LinkRepository:
    return LinkRepository(db)

def get_save_link_usecase(
    link_repo: LinkRepository = Depends(get_link_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
) -> SaveLinkUseCase:
    return SaveLinkUseCase(link_repo, chunk_repo)
```

### 2️⃣ Port/Adapter Pattern (External Systems)
Service는 **Port Interface 타입**으로 파라미터를 선언하고, DI 팩토리에서 Adapter를 주입한다.
Framework 전환 가능 (OpenAI ↔ Anthropic, KnowledgeAgent ↔ LangGraph).

```python
# ✅ Service — Port Interface에만 의존
class MessageRouterService:
    def __init__(
        self,
        intent_classifier: IntentClassifierPort,  # Port 타입
        agent: AgentPort,
    ) -> None: ...

# ✅ DI factory — Port → Adapter 매핑
def get_intent_classifier() -> IntentClassifierPort:
    return OpenAIIntentClassifier()  # Adapter 반환

def get_message_router(
    intent_classifier: IntentClassifierPort = Depends(get_intent_classifier),
    agent: AgentPort = Depends(get_agent),
) -> MessageRouterService:
    return MessageRouterService(intent_classifier, agent)
```

---

## Domain Rules

- Pure functions only.
- No FastAPI, SQLAlchemy, HTTP, or External System imports.
- **Repository interfaces (ABC) only** (`app/domain/repositories/`)
  - **오직 데이터 저장소만**: Entity 저장/조회 (User, Link, Chunk)
  - ❌ 외부 API (Telegram, Notion, OpenAI)는 Application Ports로
- **Entities** (`app/domain/entities/`)
  - `Intent` Enum (SEARCH, MEMO, ASK, START, HELP, UNKNOWN)
  - Domain 비즈니스 모델들

---

## Repository Rules

- `app/domain/repositories/` — 인터페이스(ABC)만 정의. DB 로직 없음.
- `app/infrastructure/repository/` — 인터페이스 구현체. DB 로직만.
- 엔티티별로 Repository를 분리한다 (`LinkRepository`, `ChunkRepository` 등).
- No business logic.
- No scoring logic.

---

## Service Rules

- Orchestration & Protocol handling only (비즈니스 흐름 조율, 프로토콜 처리).
- No raw SQL.
- Call domain for calculations.
- **SRP 준수**: 1 파일 = 1 책임
  - 예: WebhookService 분리
    - `TelegramWebhookHandler`: 웹훅 프로토콜만
    - `MessageRouterService`: 메시지 라우팅 & Intent 분류

---

## General

- Use type hints on all functions.
- Keep functions small.
- Avoid premature abstraction.

---

## Commit Message Convention

형식: `[prefix] : 메시지`

| Prefix | 용도 |
|--------|------|
| `[feat]` | 새 기능 추가 |
| `[fix]` | 버그 수정 |
| `[add]` | 파일 / 설정 추가 |
| `[chore]` | 빌드 / 패키지 / 환경 설정 |
| `[docs]` | 문서 작업 |
| `[refactor]` | 기능 변경 없는 코드 개선 |
| `[test]` | 테스트 추가 / 수정 |

예시:
```
[feat] : add Notion OAuth callback endpoint
#12 [fix] : handle duplicate URL in link repository
#7 [add] : docker-compose for pgvector PostgreSQL
[chore] : update .gitignore for tmpclaude files
```

**규칙:**
- 이슈가 있을 경우 반드시 `#이슈번호`를 앞에 붙인다.
- 이슈가 없을 경우 prefix만 사용한다.
- **❌ Co-Authored-By 라인 추가 금지** — 단독 커밋으로만 진행

---

## Git Workflow

모든 작업은 아래 순서를 따른다:

1. **이슈 생성** — 작업 단위로 GitHub 이슈 생성
2. **브랜치 생성** — `main`을 최신화 후 분기
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feat/#이슈번호-설명
   ```
   브랜치 형식 예시:
   ```
   feat/#6-welcome-message
   fix/#7-duplicate-url
   chore/#8-update-deps
   ```
3. **커밋** — `#이슈번호 [prefix] : 메시지`
   - **기능별로 커밋**: 한 번에 여러 파일을 수정해도, 논리적 기능 단위로 나눠서 커밋한다.
   - 예시 (같은 이슈 #40에서):
     ```
     커밋 1: #40 [refactor] : Implement Port/Adapter pattern for LLM
     커밋 2: #40 [refactor] : Complete Port/Adapter pattern with SRP-compliant webhook service split
     ```
   - 각 커밋은 **독립적으로 동작 가능**해야 함 (히스토리 추적 용이)
4. **PR 생성** — `feat/#N-xxx` → `main`, 본문에 `Closes #이슈번호` 포함, URL 노출 금지
   - PR 제목 형식: `[PREFIX/#이슈번호] 작업 제목`
   - 예시: `[FEAT/#12] Notion OAuth 콜백 엔드포인트 추가`, `[FIX/#7] 중복 URL 처리 버그 수정`
5. **머지** — `main` PR 머지 시 자동 배포 트리거

### 브랜치 전략

```
feat/#N-xxx ──→ main
               (PR, 자동 배포)
```

- `feat/*`, `fix/*`, `chore/*` 등 작업 브랜치는 **main**으로 PR
- **main** PR 머지 시 GitHub Actions 배포 자동 실행
