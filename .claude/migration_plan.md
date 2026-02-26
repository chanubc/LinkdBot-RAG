# 🎯 기능별 계층 분리 계획 (Phase 2 전) — 경량 UseCase Pattern

## 현재 상태 분석

### 문제점

```
LinkService의 의존성 (8개 - 산만함)
├── db (AsyncSession)
├── openai (IOpenAIRepository)
├── scraper (IScraperRepository)
├── notion_svc (NotionService)
├── telegram (ITelegramRepository)
├── user_repo (IUserRepository)
├── link_repo (ILinkRepository)
└── chunk_repo (IChunkRepository)
```

**문제:**
- Service가 모든 의존성을 직접 관리
- 비즈니스 흐름과 Repository 호출이 섞여있음
- link/memo/search 로직이 하나의 Service에 혼재
- 기능이 복잡할수록 Service가 비대해짐
- 테스트할 때 Mock 설정이 복잡

---

## 해결책: 경량 UseCase Pattern

### 핵심 원칙

1. **UseCase Interface 없음** — 구현을 교체할 일 없음 (YAGNI)
2. **모든 Application 로직은 `application/` 안에** — usecases/ + services/ 두 디렉토리로 구분
3. **UseCase = 완결된 비즈니스 흐름** (SaveLink, SaveMemo, Search)
4. **Service = UseCase에 해당하지 않는 오케스트레이션** (OAuth, 웹훅 분기 등)
5. **Router → UseCase/Service 직접 주입** — DI로 깔끔하게 연결, 프록시 금지

### 아키텍처 구조

```
┌─────────────────────────────────────────────────┐
│ Presentation (API)                              │
│ Router → UseCase/Service 직접 주입 (Depends)     │
└──────────────────┬──────────────────────────────┘
                   │ 의존
┌──────────────────▼──────────────────────────────┐
│ Application                                     │
│ ├─ usecases/: SaveLinkUseCase, SearchUseCase    │
│ └─ services/: AuthService, WebhookService,      │
│               AgentService (Function Calling)    │
│ 기능별 I/O 조율, 트랜잭션 관리                    │
└──────┬─────────────────────────────┬────────────┘
       │ 의존                        │ 사용
┌──────▼──────────────────┐  ┌───────▼────────────┐
│ Domain                  │  │ rag/               │
│ repositories/ (ABC)     │  │ retriever.py       │
│ scoring, drift          │  │ reranker.py        │
└──────┬──────────────────┘  └───────┬────────────┘
       │ 구현                        │ 의존
┌──────▼─────────────────────────────▼────────────┐
│ Infrastructure (Concrete Implementations)       │
│ UserRepository, OpenAIClient, TelegramClient... │
└─────────────────────────────────────────────────┘

 ─── 계층 무관 (어디서든 사용 가능) ───
┌─────────────────┐  ┌─────────────────┐
│ core/           │  │ utils/          │
│ config, security│  │ text, cleaner   │
└─────────────────┘  └─────────────────┘
```

---

## 변경 전 vs 변경 후

### 변경 전 (현재)

```
Router → Service(8개 의존성, link/memo/search 혼재)
```

### 변경 후

```
Router → UseCase(기능별 분리, 각자 필요한 의존성만)
```

**바뀌는 것:**
- `link_service.py` (모든 로직 혼재) → 기능별 UseCase 파일로 분리
- 기능 단위로 파일이 나뉘어서 수정 범위 명확
- Router에서 UseCase 직접 주입 (중간 프록시 없음)

**안 바뀌는 것:**
- 의존성 총량 (필요한 의존성은 필요한 것)
- DI Factory 복잡도
- Repository Interface 구조 (이미 완성됨)

---

## UseCase 구현 예시

### SaveLinkUseCase

```python
# app/application/usecases/save_link_usecase.py
class SaveLinkUseCase:
    """링크 저장 전체 흐름을 조율하는 UseCase"""

    def __init__(
        self,
        db: AsyncSession,
        user_repo: IUserRepository,
        link_repo: ILinkRepository,
        chunk_repo: IChunkRepository,
        openai: IOpenAIRepository,
        scraper: IScraperRepository,
        telegram: ITelegramRepository,
        notion: INotionRepository,
    ):
        self._db = db
        self._user_repo = user_repo
        self._link_repo = link_repo
        self._chunk_repo = chunk_repo
        self._openai = openai
        self._scraper = scraper
        self._telegram = telegram
        self._notion = notion

    async def execute(
        self,
        telegram_id: int,
        url: str,
        memo: str | None = None,
    ) -> tuple[Link, str]:
        """링크 저장 전체 흐름"""

        # 1. Scrape
        content = await self._scraper.scrape(url)
        if memo:
            content = f"{content}\n\n{memo}"

        # 2. Analyze
        analysis = await self._openai.analyze_content(content)
        title = analysis.get("title") or url
        summary = analysis.get("summary", "")
        category = analysis.get("category", "Other")
        keywords = analysis.get("keywords", [])

        # 3. Save to DB (User)
        await self._user_repo.ensure_exists(telegram_id)

        # 4. Save to DB (Link)
        link = await self._link_repo.save_link(
            user_id=telegram_id,
            url=url,
            title=title,
            summary=summary,
            category=category,
            keywords=json.dumps(keywords, ensure_ascii=False),
            memo=memo,
        )

        if link is None:
            await self._telegram.send_message(telegram_id, "⚠️ 이미 저장된 링크입니다.")
            return None, ""

        # 5. Embed & Save Chunks
        raw_chunks = split_chunks(content)
        if raw_chunks:
            embeddings = await self._openai.embed(raw_chunks)
            await self._chunk_repo.save_chunks(
                link.id,
                list(zip(raw_chunks, embeddings))
            )

        # 6. Commit DB Transaction
        await self._db.commit()

        # 7. Notion Sync (after commit)
        notion_url = await self._notion.create_database_entry(...)

        # 8. Telegram Notify
        await self._telegram.send_link_saved_message(...)

        return link, notion_url
```

### Router에서 직접 주입

```python
# app/api/v1/endpoints/webhook.py
@router.post("/telegram")
async def handle_webhook(
    update: TelegramUpdate,
    save_link: SaveLinkUseCase = Depends(get_save_link_usecase),
    save_memo: SaveMemoUseCase = Depends(get_save_memo_usecase),
):
    if is_link(update.text):
        await save_link.execute(update.chat_id, update.text)
    elif is_memo(update.text):
        await save_memo.execute(update.chat_id, update.text)
```

---

## DI Factory

```python
# app/api/dependencies/link_di.py
def get_save_link_usecase(
    db: AsyncSession = Depends(get_db),
    openai: IOpenAIRepository = Depends(get_openai_repository),
    scraper: IScraperRepository = Depends(get_scraper_repository),
    notion: INotionRepository = Depends(get_notion_repository),
    telegram: ITelegramRepository = Depends(get_telegram_repository),
    user_repo: IUserRepository = Depends(get_user_repository),
    link_repo: ILinkRepository = Depends(get_link_repository),
    chunk_repo: IChunkRepository = Depends(get_chunk_repository),
) -> SaveLinkUseCase:
    return SaveLinkUseCase(
        db, user_repo, link_repo, chunk_repo,
        openai, scraper, telegram, notion,
    )
```

Service용 팩토리 불필요 — UseCase 팩토리만 있으면 됨.

---

## 디렉토리 구조

```
app/
├── api/                         # Presentation
│   ├── v1/endpoints/
│   │   ├── webhook.py           # Router → UseCase/Service 직접 주입
│   │   └── auth.py
│   └── dependencies/            # DI Factory
│       ├── link_di.py           # get_save_link_usecase, get_search_usecase
│       ├── memo_di.py           # get_save_memo_usecase
│       ├── auth_di.py
│       └── webhook_di.py
│
├── application/                 # Application (기존 services/ 통합)
│   ├── usecases/                # 완결된 비즈니스 흐름 (1 파일 = 1 기능)
│   │   ├── save_link_usecase.py    # 링크 저장 흐름
│   │   ├── save_memo_usecase.py    # 메모 저장 흐름
│   │   └── search_usecase.py       # RAG 검색 흐름
│   └── services/                # UseCase에 해당하지 않는 오케스트레이션
│       ├── auth_service.py         # OAuth 흐름
│       └── webhook_service.py      # 텔레그램 명령어 분기/라우팅
│
├── agents/                      # LangGraph Agent (Phase 3+, 복잡한 흐름 필요 시)
│   ├── graph.py                    # Agent 그래프 정의
│   ├── state.py                    # Agent 상태 관리
│   └── nodes/                      # 개별 노드
│       ├── scrape_node.py
│       ├── summarize_node.py
│       ├── classify_node.py
│       └── store_node.py
│
├── rag/                         # RAG 검색 전략 (Phase 2)
│   ├── retriever.py                # Hybrid Retriever (벡터 + 키워드)
│   └── reranker.py                 # 검색 결과 재정렬
│
├── domain/                      # Domain
│   ├── repositories/            # Repository ABC (Entity + External)
│   │   ├── i_user_repository.py
│   │   ├── i_link_repository.py
│   │   ├── i_chunk_repository.py
│   │   ├── i_openai_repository.py
│   │   ├── i_telegram_repository.py
│   │   ├── i_notion_repository.py
│   │   └── i_scraper_repository.py
│   ├── drift.py                 # Interest Drift 계산 (Phase 3)
│   └── scoring.py               # Reactivation Score 계산 (Phase 3)
│
├── infrastructure/              # Infrastructure
│   ├── repository/
│   │   ├── user_repository.py
│   │   ├── link_repository.py
│   │   └── chunk_repository.py
│   ├── external/
│   │   ├── telegram_client.py
│   │   ├── notion_client.py
│   │   └── scraper_client.py
│   ├── llm/
│   │   └── openai_client.py
│   └── database.py
│
├── core/                        # 공통 설정 (계층 무관)
│   ├── config.py                   # 환경변수, Settings
│   └── security.py                 # Fernet 암호화
│
├── utils/                       # 순수 유틸리티 (계층 무관)
│   ├── text.py                     # split_chunks, extract_urls (기존 domain/text.py)
│   └── text_cleaner.py             # HTML 정리, 마크다운 전처리
│
└── models/                      # SQLAlchemy ORM
```

### 디렉토리 분류 기준

| 디렉토리 | 계층 | 기준 | 예시 |
|----------|------|------|------|
| `application/usecases/` | Application | **완결된 비즈니스 흐름** 1개를 조율 | SaveLink, SaveMemo, Search |
| `application/services/` | Application | **분기/인증/Agent 등** UseCase에 해당하지 않는 오케스트레이션 | Auth, Webhook, AgentService |
| `agents/` | Application (확장) | **그래프 기반 복잡 Agent** (Phase 3+, LangGraph 도입 시) | 멀티스텝 추론, 조건 분기 + 반복 |
| `rag/` | Domain ↔ Infra 사이 | **검색 전략** (retrieval, reranking) | HybridRetriever, Reranker |
| `domain/` | Domain | **순수 비즈니스 로직 + Repository ABC** | scoring, drift, interfaces |
| `infrastructure/` | Infrastructure | **외부 시스템 구현체** | DB Repository, API Client |
| `core/` | 계층 무관 | **공통 설정/보안** | config, security |
| `utils/` | 계층 무관 | **순수 유틸리티 함수** | text split, URL 추출 |

### 기존 대비 변경 요약

| 항목 | 기존 계획 | 수정 계획 |
|------|-----------|-----------|
| UseCase Interface | `domain/usecases/i_*.py` 생성 | **생성하지 않음 (YAGNI)** |
| UseCase 구현체 위치 | `infrastructure/usecases/` | **`application/usecases/`** |
| Service 위치 | 프로젝트 루트 `services/` | **`application/services/`** |
| Agent (Phase 2) | 없음 | **`application/services/agent_service.py`** (OpenAI Function Calling) |
| Agent (Phase 3+) | 없음 | **`agents/`** (LangGraph, 복잡한 그래프 흐름 필요 시) |
| RAG 검색 | ChunkRepository에 혼재 | **`rag/`** (retriever, reranker 분리) |
| 순수 유틸 | `domain/text.py` | **`utils/text.py`** (domain에서 분리) |
| 공통 설정 | 흩어져 있음 | **`core/`** (config, security 통합) |

---

## 데이터 흐름

```
Router (webhook.py)
  │
  ├─ GET /auth → AuthService (application/services/)
  │
  └─ POST /telegram → WebhookService (application/services/)
      │                 명령어 파싱 & 분기
      │
      ├─ link → SaveLinkUseCase.execute()
      │          ├─ Scraper (추출)
      │          ├─ OpenAI (분석)
      │          ├─ utils/text.py (split_chunks)
      │          ├─ UserRepository (확인)
      │          ├─ LinkRepository (저장)
      │          ├─ ChunkRepository (임베딩)
      │          ├─ DB commit
      │          ├─ Notion (동기화)
      │          └─ Telegram (알림)
      │
      ├─ /memo → SaveMemoUseCase.execute()
      │          ├─ OpenAI (분석)
      │          ├─ utils/text.py (split_chunks)
      │          ├─ LinkRepository (저장)
      │          ├─ ChunkRepository (임베딩)
      │          ├─ DB commit
      │          ├─ Notion (동기화)
      │          └─ Telegram (알림)
      │
      ├─ /search → SearchUseCase.execute()
      │            ├─ OpenAI (임베딩)
      │            ├─ rag/retriever.py (Hybrid Retrieval)
      │            ├─ rag/reranker.py (결과 재정렬)
      │            └─ Telegram (결과 전송)
      │
      └─ /ask → AgentService (application/services/, Phase 2)
               ├─ OpenAI Function Calling (intent 판단 + tool 호출)
               ├─ tools: search_knowledge_base → rag/ (검색 전략)
               ├─ tools: get_unread_links → LinkRepository
               └─ Telegram (최종 답변 전송)

--- Phase 3+ (LangGraph 도입 시) ---
      └─ /ask → RAG Agent (agents/)
               ├─ agents/graph.py (LangGraph 그래프)
               ├─ agents/nodes/ (멀티스텝 노드)
               ├─ rag/ (검색 전략)
               └─ Telegram (응답 전송)
```

---

## Phase 2 마이그레이션 로드맵

### Phase 2.0: 구조 준비
- [ ] `app/application/usecases/` 디렉토리 생성
- [ ] `app/application/services/` 디렉토리 생성
- [ ] `app/rag/` 디렉토리 생성
- [ ] `app/core/` 디렉토리 생성 (config, security 이동)
- [ ] `app/utils/` 디렉토리 생성 (`domain/text.py` → `utils/text.py` 이동)

### Phase 2.1: SaveLinkUseCase 구현
- [ ] `save_link_usecase.py` 작성 (기존 LinkService.process_link 로직 이동)
- [ ] DI Factory 추가 (`get_save_link_usecase`)
- [ ] Router에서 UseCase 직접 주입으로 변경
- [ ] 기존 LinkService에서 해당 로직 제거
- [ ] 테스트 작성

### Phase 2.2: SaveMemoUseCase 구현
- [ ] `save_memo_usecase.py` 작성 (기존 LinkService.process_memo 로직 이동)
- [ ] DI Factory 추가
- [ ] Router 연결
- [ ] 테스트 작성

### Phase 2.3: SearchUseCase + RAG 구현
- [ ] `rag/retriever.py` 작성 (Hybrid Retrieval 전략)
- [ ] `rag/reranker.py` 작성 (결과 재정렬)
- [ ] `search_usecase.py` 작성 (rag/ 활용)
- [ ] DI Factory 추가
- [ ] Router 연결
- [ ] 테스트 작성

### Phase 2.4: AgentService 구현 (OpenAI Function Calling)
- [ ] `application/services/agent_service.py` 작성
- [ ] OpenAI Function Calling으로 intent 판단
- [ ] tools 정의: `search_knowledge_base`, `get_unread_links`
- [ ] SearchUseCase, LinkRepository와 연동
- [ ] DI Factory 추가
- [ ] Router 연결 (/ask 명령어)
- [ ] 테스트 작성

### Phase 2.5: 정리
- [ ] 기존 `services/link_service.py` 삭제 (모든 로직이 UseCase로 이동 완료)
- [ ] 기존 `services/` 디렉토리 삭제 (모두 `application/` 안으로 이동 완료)
- [ ] 불필요한 DI Factory 제거
- [ ] 전체 테스트 통과 확인

### Phase 3: Proactive Agent
- [ ] 새로운 UseCase 추가 (ReportGenerationUseCase 등)
- [ ] `domain/drift.py`, `domain/scoring.py` 구현
- [ ] APScheduler 연동 (주간 리포트)
- [ ] 기존 UseCase 재사용

### Phase 3+: LangGraph 도입 (복잡한 Agent 흐름 필요 시)
- [ ] `app/agents/` 디렉토리 생성
- [ ] `agents/state.py` 작성 (Agent 상태 정의)
- [ ] `agents/nodes/` 개별 노드 구현
- [ ] `agents/graph.py` LangGraph 그래프 조합
- [ ] 기존 AgentService를 LangGraph 기반으로 전환
- [ ] 멀티스텝 추론, 조건 분기, 사용자 피드백 루프 구현

---

## 예상 개선 효과

| 지표 | 현재 | 개선 후 |
|-----|------|--------|
| 기능별 파일 분리 | link/memo/search 혼재 | **UseCase별 1파일** |
| 수정 범위 | Service 전체 영향 | **해당 UseCase만** |
| 테스트 단위 | Service 전체 Mock | **UseCase별 독립 테스트** |
| 새 기능 추가 | Service에 메서드 추가 | **새 UseCase 파일 추가** |
| 불필요한 추상화 | - | **없음 (Interface 미생성)** |

---

## 용어 정리

### UseCase vs Service (새 구조에서의 구분)

| | UseCase (`application/usecases/`) | Service (`application/services/`) |
|---|---------|---------|
| **계층** | Application | Application |
| **책임** | 완결된 비즈니스 흐름 1개 조율 | 분기/인증 등 비-UseCase 오케스트레이션 |
| **단위** | 파일 1개 = 기능 1개 | 파일 1개 = 역할 1개 |
| **예시** | SaveLinkUseCase, SearchUseCase | AuthService, WebhookService, AgentService |
| **테스트** | 기능별 단위 테스트 | 통합 테스트 |

### Repository vs UseCase

| | Repository | UseCase |
|---|-----------|---------|
| **책임** | **데이터를** 어디서 가져오고 저장하는가 | **기능을** 어떻게 조율하는가 |
| **추상화** | Interface 필요 (구현 교체 가능) | **Interface 불필요** (흐름은 1개) |
| **재사용** | 여러 UseCase에서 공유 | 보통 1개 기능 전담 |

---

## 주의사항

### ✅ 해야 할 것
- UseCase는 **기능 단위**로만 생성 (1 UseCase = 1 기능)
- UseCase는 **I/O 조율**만 (순수 로직은 Domain으로)
- Repository는 **공유 자산** (여러 UseCase에서 재사용)
- Router에서 UseCase/Service **직접 주입** (중간 프록시 금지)
- UseCase와 Service의 분류 기준 준수 (완결된 흐름 = UseCase, 그 외 = Service)
- 순수 유틸리티 함수는 `utils/`에 배치 (domain에 넣지 않음)
- 검색 전략 로직은 `rag/`에 분리 (Repository에 섞지 않음)
- Phase 2 Agent는 `application/services/agent_service.py`에 (OpenAI Function Calling)
- Phase 3+ LangGraph Agent는 `agents/`에 분리 (복잡한 그래프 흐름 필요 시)

### ❌ 하지 말아야 할 것
- UseCase Interface 생성 (YAGNI)
- UseCase를 infrastructure/에 배치 (UseCase는 인프라가 아님)
- UseCase 내에서 다른 UseCase 호출 (순환 의존성)
- Repository에 비즈니스 로직 포함
- 프록시 Service 생성 (UseCase 호출만 하는 클래스)
- application/ 밖에 Service나 UseCase 배치 (모든 Application 로직은 application/ 안에)
- domain/에 유틸리티 함수 배치 (순수 텍스트 처리 등은 utils/로)
- rag/ 로직을 ChunkRepository에 혼재시키기 (검색 전략과 데이터 접근은 분리)
