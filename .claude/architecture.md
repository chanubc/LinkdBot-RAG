# 🏗️ Architecture (Phase 2 마이그레이션 완료)

## Layer Structure (Port/Adapter Pattern)

```
Presentation (API)
    ↓ Depends
Application (UseCases + Services + Ports)
    ↓ Depends
Domain (Pure Logic + Entities)
    ↓ Depends
Infrastructure (Implementations + Adapters + RAG)
```

**의존성 방향:**
- Data Flow: Presentation → Application → Domain → Infrastructure
- Dependency Flow: Presentation → Application (Ports) ← Infrastructure (Adapters)

**Port/Adapter 원칙:**
- **Repository Interfaces**: Domain (Entity 저장/조회는 도메인 규칙)
- **Port Interfaces**: Application (외부 시스템 호출은 유스케이스 흐름)
- **Adapter Implementations**: Infrastructure (기술적 구현)
- **RAG**: Infrastructure (검색 알고리즘은 도메인이 아님, 구현 전략)

---

## Responsibilities

### Presentation (`app/api/`)
- FastAPI routers only
- Input validation
- Call UseCase/Service via `Depends`
- ❌ No business logic

### Application
#### `app/application/usecases/` (완결된 비즈니스 흐름)
- **SaveLinkUseCase**: 링크 저장 파이프라인 (스크래핑 → 분석 → 임베딩 → 저장 → 노션 → 알림)
- **SaveMemoUseCase**: 메모 저장 파이프라인
- **SearchUseCase**: RAG 검색 흐름 (임베딩 → retrieval → reranking → 알림)

**핵심:**
- 1 파일 = 1 기능
- I/O 조율만 담당 (Domain 순수 로직 호출 + Repository 호출)
- Interface 타입으로 의존성 선언

#### `app/application/services/` (비UseCase 오케스트레이션)
- **AuthService**: Notion OAuth 흐름
- **TelegramWebhookHandler**: Telegram 웹훅 수신 + callback 처리 + URL 핸들러
- **MessageRouterService**: 메시지 라우팅 (슬래쉬 명령어 + Intent 분류 + UseCase 분기)
- **AgentService**: OpenAI Function Calling (intent 판단 + tools 호출)

**핵심:**
- UseCase 범위 밖의 프로토콜, 분기, 인증, Agent 로직
- TelegramWebhookHandler: 웹훅 프로토콜만 담당
- MessageRouterService: 메시지 처리 & 라우팅 (Intent classifier Port 사용)
- 통합 테스트 대상

#### `app/application/ports/` (Port/Adapter 패턴 - 외부 시스템 계약)
**의도 분류 & Agent:**
- **IntentClassifierPort**: 메시지 의도 분류
  - 구현체: `OpenAIIntentClassifier` (Infrastructure/Adapters)
- **AgentPort**: AI 에이전트 실행
  - 구현체: `KnowledgeAgentAdapter` (Infrastructure/Adapters)

**외부 API 통신:**
- **TelegramPort**: Telegram API
  - 구현체: `TelegramRepository` (Infrastructure/External)
- **NotionPort**: Notion API
  - 구현체: `NotionRepository` (Infrastructure/External)
- **ScraperPort**: 웹 스크래핑
  - 구현체: `ScraperRepository` (Infrastructure/External)
- **OpenAILLMPort**: OpenAI 콘텐츠 분석 & 임베딩
  - 구현체: `OpenAIRepository` (Infrastructure/LLM)

**LLM & 상태 관리:**
- **LLMGatewayPort**: 범용 LLM 호출 (Function Calling 등)
  - 구현체: `OpenAILLMGateway` (Infrastructure/LLM)
- **StateStorePort**: OAuth state 저장/검증
  - 구현체: `StateStore` (Infrastructure)

**Port/Adapter 의존성:**
```
MessageRouterService → IntentClassifierPort (Port, Interface)
                     ← OpenAIIntentClassifier (Adapter, Impl)

AgentService → AgentPort (Port, Interface)
            ← KnowledgeAgentAdapter (Adapter, Impl)
```

**⚠️ 핵심 규칙:**
```python
# ❌ 금지
class SomeUseCase:
    def __init__(self):
        self.repo = UserRepository(self.db)  # 직접 인스턴스화

# ✅ 올바른 방식 — DB Repository Interface
class SomeUseCase:
    def __init__(self, user_repo: IUserRepository):  # Interface 타입
        self.repo = user_repo  # __init__으로 주입

# ✅ 올바른 방식 — External System Port
class SomeService:
    def __init__(self, classifier: IntentClassifierPort):  # Port 타입
        self.classifier = classifier

# ✅ DI 팩토리에서만 concrete class 생성
def get_some_usecase(
    user_repo: UserRepository = Depends(get_user_repository),
) -> SomeUseCase:
    return SomeUseCase(user_repo)

def get_intent_classifier() -> IntentClassifierPort:
    return OpenAIIntentClassifier()  # Adapter 반환
```

### Domain (`app/domain/`)
- Pure business logic (no DB/HTTP/External imports)
- **Entities** (`app/domain/entities/`) — Domain 비즈니스 개념만
  - `Intent` Enum: 메시지 의도 (SEARCH, MEMO, ASK, START, HELP, UNKNOWN)
- **Drift calculation** (`drift.py`) — Phase 3
- **Reactivation scoring** (`scoring.py`) — Phase 3
- **Repository interfaces (ABC)** — `app/domain/repositories/`
  - **오직 데이터 저장소만**: `IUserRepository`, `ILinkRepository`, `IChunkRepository`
  - ❌ 외부 API는 Repository가 아님 (Application Ports로 이동됨)

### RAG (`app/rag/`) — Phase 2
- **HybridRetriever**: 벡터 + 키워드 검색 조합 (SearchUseCase에서 호출)
- **SimpleReranker**: 검색 결과 재정렬
- Domain과 Infrastructure 사이의 검색 전략 계층

### Infrastructure (`app/infrastructure/`)
- **Repository** (`repository/`) — Domain Repository Interface 구현
  - `UserRepository(IUserRepository)`
  - `LinkRepository(ILinkRepository)`
  - `ChunkRepository(IChunkRepository)`

- **Adapters** (`adapters/`) — Application Port 구현
  - `OpenAIIntentClassifier(IntentClassifierPort)`: OpenAI Structured Output
  - `KnowledgeAgentAdapter(AgentPort)`: KnowledgeAgent 래핑

- **LLM** (`llm/`) — OpenAI 구현체
  - `openai_client.py` → `OpenAIRepository(OpenAILLMPort)`
  - `openai_llm_gateway.py` → `OpenAILLMGateway(LLMGatewayPort)`

- **External** (`external/`) — 외부 API 포트 구현
  - `telegram_client.py` → `TelegramRepository(TelegramPort)`
  - `notion_client.py` → `NotionRepository(NotionPort)`
  - `scraper_client.py` → `ScraperRepository(ScraperPort)`

- **RAG** (`rag/`) — 검색 알고리즘 구현 (Infrastructure 범위)
  - `retriever.py` → `HybridRetriever` (벡터+키워드 검색)
  - `reranker.py` → `SimpleReranker` (결과 재정렬)

- **Database**: `database.py` (AsyncSession)

### Core & Utils (계층 무관)
- `app/core/config.py`: 환경변수 Settings
- `app/core/security.py`: Fernet 암호화 (Notion token 보호)
- `app/utils/text.py`: split_chunks, extract_urls (순 순수 함수)

---

## Directory Structure

```
app/
├── api/                    # Presentation: FastAPI 라우터만
│   ├── v1/endpoints/
│   │   ├── auth.py         # Notion OAuth
│   │   └── webhook.py      # Telegram 웹훅 (TelegramWebhookHandler 호출)
│   └── dependencies/       # DI 팩토리
│       ├── auth_di.py
│       ├── link_di.py
│       ├── webhook_di.py
│       ├── rag_di.py
│       ├── agent_di.py
│       └── adapter_di.py   # Port → Adapter 매핑 (NEW)
│
├── application/            # Application: 비즈니스 흐름 조율
│   ├── usecases/           # 완결된 비즈니스 흐름 (1 파일 = 1 기능)
│   │   ├── save_link_usecase.py
│   │   ├── save_memo_usecase.py
│   │   └── search_usecase.py
│   ├── ports/              # Port 인터페이스 (외부 시스템 계약)
│   │   ├── intent_classifier_port.py
│   │   ├── agent_port.py
│   │   ├── telegram_port.py
│   │   ├── notion_port.py
│   │   ├── scraper_port.py
│   │   ├── openai_llm_port.py
│   │   ├── llm_gateway_port.py
│   │   └── state_store_port.py
│   ├── services/           # UseCase 밖의 오케스트레이션
│   │   ├── auth_service.py
│   │   ├── telegram_webhook_handler.py  # 웹훅 수신만 담당
│   │   ├── message_router_service.py     # 메시지 라우팅 + Intent 분류
│   │   └── agent_service.py (또는 knowledge_agent.py)
│   └── agents/
│       └── knowledge_agent.py       # OpenAI Function Calling Agent
│
├── domain/                 # Domain: 순수 로직 + Repository Interface
│   ├── entities/           # Domain Entity
│   │   └── intent.py       # Intent Enum
│   ├── repositories/       # Repository Interface (DB만)
│   │   ├── i_user_repository.py
│   │   ├── i_link_repository.py
│   │   └── i_chunk_repository.py
│   ├── drift.py            # Interest Drift (Phase 3)
│   └── scoring.py          # Reactivation Score (Phase 3)
│
├── infrastructure/         # Infrastructure: 모든 구현체
│   ├── repository/         # DB Repository 구현
│   │   ├── user_repository.py
│   │   ├── link_repository.py
│   │   └── chunk_repository.py
│   ├── adapters/           # Application Port 구현
│   │   ├── openai_intent_classifier.py
│   │   └── knowledge_agent_adapter.py
│   ├── rag/                # 검색 전략 (RAG도 Infrastructure)
│   │   ├── retriever.py        # Hybrid Retrieval
│   │   └── reranker.py         # 결과 재정렬
│   ├── llm/                # LLM 구현
│   │   ├── openai_client.py
│   │   └── openai_llm_gateway.py
│   ├── external/           # 외부 API 포트 구현
│   │   ├── telegram_client.py
│   │   ├── notion_client.py
│   │   └── scraper_client.py
│   └── database.py
│
├── core/                   # 공통 설정 (계층 무관)
│   ├── config.py
│   └── security.py
│
├── utils/                  # 순수 유틸리티 (계층 무관)
│   └── text.py
│
├── models/                 # SQLAlchemy ORM
│   ├── user.py
│   ├── link.py
│   └── chunk.py
│
└── main.py                 # FastAPI 앱 진입점
```

---

## Dependency Rules

1. **Presentation** → Application (UseCase/Service) only
2. **Application** → Domain interfaces (not Infrastructure concrete classes)
3. **Domain** → nothing external (no DB, HTTP, FastAPI imports)
4. **Infrastructure** → Domain interfaces only (implements, not imports services)
5. **DI factories** wire interfaces to implementations
6. **No circular imports** ever

---

## Database Schema

Parent-Child split for RAG quality. Defined in `app/models/`.

### `users`
- `telegram_id` (PK, BigInt)
- `notion_access_token` (Encrypted String) — cryptography 필수
- `notion_page_id` (String, Optional)

### `links` (Parent)
- `id` (PK, Serial)
- `user_id` (FK → users)
- `url` (String) — UNIQUE(user_id, url)
- `title` (String)
- `summary` (Text)
- `category` (String)
- `keywords` (Text) — JSON 배열 문자열
- `is_read` (Boolean, Default: False)
- `created_at` (Timestamp)

### `chunks` (Child)
- `id` (PK, Serial)
- `link_id` (FK → links)
- `content` (Text)
- `embedding` (Vector(1536), IVFFlat Index)

---

## Key Data Flows

### 링크 저장 (SaveLinkUseCase)
```
Router (/webhook)
  ↓
TelegramWebhookHandler (프로토콜: 웹훅 수신 + callback)
  ↓
MessageRouterService (정책: 메시지 라우팅)
  ├─ IntentClassifierPort (Port)
  │  └─ OpenAIIntentClassifier (Adapter): Structured Output
  └─ SaveLinkUseCase (Use Case: 링크 저장 파이프라인)
     ├─ ScraperPort (Port)
     │  └─ ScraperRepository (Adapter): Jina Reader
     ├─ OpenAILLMPort (Port)
     │  └─ OpenAIRepository (Adapter): GPT-4o 분석
     ├─ Repository (Domain): DB 저장
     ├─ NotionPort (Port)
     │  └─ NotionRepository (Adapter): Notion 동기화
     └─ TelegramPort (Port)
        └─ TelegramRepository (Adapter): 알림 전송
```

### RAG 검색 (SearchUseCase)
```
Router (/webhook)
  ↓
TelegramWebhookHandler
  ↓
MessageRouterService
  ├─ IntentClassifierPort → OpenAIIntentClassifier
  └─ SearchUseCase (RAG 파이프라인)
     ├─ OpenAILLMPort → OpenAIRepository (임베딩)
     ├─ HybridRetriever (Infrastructure): 벡터+키워드 검색
     ├─ SimpleReranker (Infrastructure): 결과 재정렬
     └─ TelegramPort → TelegramRepository (결과 전송)
```

### AI Agent (/ask 명령어)
```
Router (/webhook)
  ↓
TelegramWebhookHandler
  ↓
MessageRouterService
  ├─ IntentClassifierPort → OpenAIIntentClassifier
  └─ AgentPort (Port)
     └─ KnowledgeAgentAdapter (Adapter)
        ↓
        KnowledgeAgent (Application Service)
        ├─ LLMGatewayPort (Port)
        │  └─ OpenAILLMGateway (Adapter): Function Calling
        ├─ Tools:
        │  ├─ search_knowledge_base → SearchUseCase
        │  │  ├─ HybridRetriever (Infrastructure/RAG)
        │  │  └─ SimpleReranker (Infrastructure/RAG)
        │  └─ get_unread_links → LinkRepository (Domain)
        └─ TelegramPort → TelegramRepository (자동 알림)
```
