# LinkdBot-RAG

> Proactive AI Knowledge Copilot — Store user-shared links, convert to structured knowledge, detect interest drift, send proactive insights

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Async-green)](https://fastapi.tiangolo.com/)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Demo

| Link Save & Notion Sync | Hybrid RAG 벡터(Dense) + 키워드(Sparse) | Knowledge Q&A (`/ask`) |
|:-:|:-:|:-:|
| <img src="docs/assets/screenshots/telegram-save-link-sync.jpg" width="220" alt="링크 저장" /> | <img src="docs/assets/screenshots/telegram-search-results.jpg" width="220" alt="하이브리드 검색" /> | <img src="docs/assets/screenshots/telegram-ask-answer.jpg" width="220" alt="지식 Q&A" /> |
| 텔레그램에 링크만 보내면 본문 스크랩 → 요약/분석 → 저장 → Notion 동기화까지 한 번에 처리 | 벡터 + 키워드 검색 후 reranking으로 정확도를 높임 | 저장된 링크/메모를 바탕으로 답변을 생성하는 개인 지식 Q&A 흐름 |

| Proactive Weekly Report | Dashboard Entry | Quick Menu |
|:-:|:-:|:-:|
| <img src="docs/assets/screenshots/telegram-weekly-report.jpg" width="220" alt="주간 리포트" /> | <img src="docs/assets/screenshots/telegram-dashboard-entry.jpg" width="220" alt="대시보드 진입" /> | <img src="docs/assets/screenshots/telegram-quick-menu.jpg" width="220" alt="빠른 메뉴" /> |
| drift / reactivation 기반으로 관심사 변화와 다시 볼 링크를 선제적으로 추천 | `/dashboard`로 JWT 매직 링크를 발급해 웹 대시보드로 바로 이동 | 검색, 질문, 리포트, 대시보드, 도움말을 버튼 중심으로 빠르게 실행 |

---

## Core Features

| Priority | Feature | Description |
|---|---|---|
| 1 | **Proactive Agent** | 사용자의 저장 패턴과 관심사 변화를 분석해 `drift`를 감지하고, `reactivation` 점수를 기반으로 다시 볼 만한 링크를 주간 리포트로 먼저 제안합니다. 이 프로젝트의 차별점이 가장 강하게 드러나는 영역입니다. |
| 2 | **Hybrid RAG (Dense + Sparse + Reranking)** | pgvector 기반 dense vector search와 keyword/FTS 기반 sparse search를 함께 사용하고, 이후 reranking과 cutoff optimization까지 적용해 관련 링크를 더 안정적으로 찾습니다. `/search` 품질뿐 아니라 `/ask` 답변 품질의 기반이 됩니다. |
| 3 | **지식 Q&A 에이전트** | `/ask` 요청 시 저장된 링크와 메모를 조회한 뒤 근거 기반 답변을 생성합니다. 단순 챗봇이 아니라 개인 지식 베이스를 활용하는 응답 흐름입니다. |
| 4 | **본문 스크랩 & Notion 요약 자동화** | 텔레그램에 링크만 보내면 해당 페이지의 본문 내용을 스크랩/크롤링하고, 요약·키워드·임베딩을 생성한 뒤 저장합니다. 이후 핵심 요약과 메타데이터를 Notion에도 자동 동기화해 다시 보기 쉬운 형태로 남깁니다. |
| 5 | **멀티 서피스 UX** | 텔레그램을 메인 인터페이스로 유지하면서, Streamlit 대시보드와 Notion을 보조 표면으로 연결해 탐색/회고/재사용을 돕습니다. |

### Why These Matter Most

제가 보기엔 핵심은 아래 3개예요.

1. **Proactive Agent (drift + reactivation)**  
   이 프로젝트를 “저장 앱”이 아니라 “먼저 챙겨주는 지식 코파일럿”으로 바꾸는 가장 중요한 기능입니다.

2. **Hybrid RAG (벡터 dense + 키워드 sparse + reranking)**  
   사람들이 바로 이해할 수 있는 표현으로 보면 “벡터 검색 + 키워드 검색” 조합이고, 그 위에 reranking과 cutoff optimization이 한 번 더 얹혀 있습니다. 검색 품질이 좋아야 질문 응답, 추천, 리포트가 전부 살아납니다.

3. **본문 스크랩과 Notion 요약 자동화**  
   아무리 추천과 검색이 좋아도 원문 지식이 제대로 쌓이지 않으면 가치가 없습니다. 링크 본문을 자동으로 읽고 요약해 Notion까지 정리해주는 흐름이 실사용성을 받쳐줍니다.

---

## Workflow

### Main Workflow

시스템은 아래와 같은 다단계 파이프라인으로 메시지를 처리합니다.

1. **Telegram Webhook** → URL 또는 일반 텍스트 메시지 수신
2. **WebhookHandler** → URL 추출 및 메시지 유형 분기
3. **MessageRouter** → 의도 분류 (`SEARCH`, `MEMO`, `ASK` 등)
4. **병렬 처리** → 세 가지 주요 흐름 실행
   - **SaveLink** → 스크랩, 분석, 임베딩, 저장, Notion 동기화
   - **Search** → Hybrid retrieval, rerank, 상위 결과 반환
   - **Knowledge Agent** → 도구 호출 기반 질의응답 (지식 검색, 미읽음 링크 조회 등)
5. **Response** → 결과를 Telegram 사용자에게 전송

```mermaid
%%{init: {"theme": "base", "look": "handDrawn", "themeVariables": {"fontFamily": "Comic Sans MS"}}}%%
flowchart TD
    classDef user fill:#dbeafe,stroke:#0284c7,color:#1e3a8a
    classDef interface fill:#ccfbf1,stroke:#0d9488,color:#115e59
    classDef router fill:#f3e8ff,stroke:#9333ea,color:#4c1d95
    classDef usecase fill:#dcfce7,stroke:#22c55e,color:#14532d
    classDef storage fill:#fed7aa,stroke:#f97316,color:#7c2d12
    classDef external fill:#ffe4e6,stroke:#e11d48,color:#881337

    A("👤 Telegram User"):::user
    B["📱 Telegram Bot API"]:::interface
    C["TelegramWebhookHandler"]:::router
    D{"MessageRouter"}:::router
    E1["SaveLink UseCase"]:::usecase
    E2["SaveMemo UseCase"]:::usecase
    E3["Search UseCase"]:::usecase
    E4["KnowledgeAgent<br/>(Ask Flow)"]:::usecase
    E5["AuthService<br/>(Magic Link 생성)"]:::router
    F["HybridRetriever"]:::usecase
    G[("🗄️ PostgreSQL<br/>(DB & Vector)")]:::storage
    H1["🧪 Jina Reader"]:::external
    H2["🤖 OpenAI API<br/>(Embed/Analyze/Chat)"]:::external
    H3["📜 Notion API<br/>(Sync)"]:::external
    I("💬 Telegram Response<br/>(Answer or Web Link)"):::user

    A --> B --> C --> D
    D -->|"URL"| E1
    D -->|"Memo"| E2
    D -->|"SEARCH"| E3
    D -->|"ASK"| E4
    D -->|"DASHBOARD"| E5
    E1 -.->|"1. Scrape"| H1
    E1 -.->|"2. Analyze & Embed"| H2
    E1 -->|"3. Save"| G
    E1 -.->|"4. Sync"| H3
    E2 -.->|"1. Embed"| H2
    E2 -->|"2. Save"| G
    E2 -.->|"3. Sync"| H3
    E3 --> F
    E4 --> F
    F -.->|"Embed Query"| H2
    F -->|"Search"| G
    E4 -.->|"Chat / Tool Call"| H2
    E5 -->|"Generate JWT URL"| I
    G --> I
```

### Dashboard Workflow

`/dashboard` 명령어 → Magic Link 생성(JWT) → Streamlit 대시보드 접근. APScheduler가 주기적으로 interest drift를 감지하고 주간 리포트를 생성하여 Telegram으로 전송.

```mermaid
%%{init: {"theme": "base", "look": "handDrawn", "themeVariables": {"fontFamily": "Comic Sans MS"}}}%%
flowchart TD
    classDef user fill:#dbeafe,stroke:#0284c7,color:#1e3a8a
    classDef interface fill:#ccfbf1,stroke:#0d9488,color:#115e59
    classDef router fill:#f3e8ff,stroke:#9333ea,color:#4c1d95
    classDef usecase fill:#dcfce7,stroke:#22c55e,color:#14532d
    classDef storage fill:#fed7aa,stroke:#f97316,color:#7c2d12
    classDef external fill:#ffe4e6,stroke:#e11d48,color:#881337

    A1("👤 Telegram User<br/>(via Magic Link)"):::user
    A2["⏰ Scheduler<br/>(Cron)"]:::interface
    B1["🖥️ Streamlit Dashboard"]:::interface
    B2["AuthService<br/>(Verify JWT)"]:::router
    C1["Library / Insights UseCase"]:::usecase
    C2["GenerateWeeklyReport UseCase"]:::usecase
    D[("🗄️ PostgreSQL<br/>(DB)")]:::storage
    E1["🤖 OpenAI API<br/>(Generate Briefing)"]:::external
    E2["📱 Telegram API<br/>(Push Notification)"]:::external

    A1 -.->|"Click URL"| B1
    B1 -->|"1. Extract Token"| B2
    B2 -->|"2. Validate"| C1
    C1 -->|"3. Fetch Data"| D
    A2 --> C2
    C2 -->|"1. Fetch Drift & Links"| D
    C2 -.->|"2. Summarize"| E1
    C2 -.->|"3. Push Report"| E2
```

---

## Architecture

LinkdBot-RAG는 의존성 역전을 적용한 **Clean Architecture**를 사용합니다.

```
    Presentation (API)
         ↓ Depends
    Application (UseCases + Services + Ports)
         ↓ Depends
    Domain (Pure Logic + Entities)
         ↓ Implements
    Infrastructure (Adapters + RAG + External I/O)
```

- **Domain**: Pure business logic (no imports of external libraries like FastAPI, DB, HTTP)
- **Application**: UseCase orchestration and Port interfaces for external systems
- **Infrastructure**: Repository implementations, LLM clients, external API adapters
- **Presentation**: FastAPI routers that depend only on Application layer via dependency injection

```mermaid
%%{init: {"theme": "base", "look": "handDrawn", "themeVariables": {"fontFamily": "Comic Sans MS"}}}%%
flowchart TD
    classDef domain fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#92400e
    classDef app fill:#dcfce7,stroke:#059669,stroke-width:2px,color:#064e3b
    classDef infra fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a8a
    classDef pres fill:#f3e8ff,stroke:#9333ea,stroke-width:2px,color:#4c1d95

    subgraph Presentation ["1. Presentation Layer (app/api, dashboard)"]
        direction LR
        P1["🌐 FastAPI<br/>(Webhook)"]:::pres
        P2["🖥️ Streamlit<br/>(Dashboard)"]:::pres
        P3["⏰ APScheduler<br/>(Cron)"]:::pres
    end

    subgraph Application ["2. Application Layer (app/application)"]
        direction TB
        A1["⚙️ Services & Agents<br/>(MessageRouter, KnowledgeAgent)"]:::app
        A2["🎯 Use Cases<br/>(SaveLink, Search, Report)"]:::app
        A3["🔌 Outbound Ports<br/>(ScraperPort, AIAnalysisPort)"]:::app

        P1 -->|"Trigger"| A1
        P1 -->|"Trigger"| A2
        P2 -->|"Trigger"| A2
        P3 -->|"Trigger"| A2

        A1 -->|"Execute"| A2
        A2 -->|"Define needs"| A3
    end

    subgraph Domain ["3. Domain Layer (app/domain)"]
        direction TB
        D1["📦 Entities<br/>(Link, Chunk, User)"]:::domain
        D2["🧠 Domain Rules<br/>(scoring.py, drift.py)"]:::domain
        D3["🔌 Repository Interfaces<br/>(ILinkRepository, etc.)"]:::domain

        A2 -->|"Uses"| D3
        A2 -->|"Manipulates"| D1
        A2 -->|"Applies"| D2

        A3 -.->|"References"| D1
        D3 -.->|"References"| D1
    end

    subgraph Infrastructure ["4. Infrastructure Layer (app/infrastructure)"]
        direction LR
        I1["🗄️ Repository Adapters<br/>(PostgreSQL)"]:::infra
        I2["📡 External Adapters<br/>(JinaAdapter, OpenAIClient)"]:::infra
    end

    I1 -.->|"✨ Implements (Dependency Inversion)"| D3
    I2 -.->|"✨ Implements (Dependency Inversion)"| A3
```

### System Infrastructure

GCP VM(chanu.shop) 위에서 Docker로 실행합니다. NGINX가 리버스 프록시 역할을 하며 FastAPI(:8000)와 Streamlit(:8501)을 서빙합니다.

![System Architecture](docs/assets/system-architecture.png)

### DB Schema

`USERS → LINKS → CHUNKS` 3-테이블 구조입니다. `LINKS`에는 summary embedding(Vector 1536)이 저장되고, `CHUNKS`에는 전문 검색용 TSVector와 청크 embedding이 저장됩니다.

![ERD Diagram](docs/assets/erd-diagram.png)

---

## Directory Structure

```
LinkdBot-RAG/
├── app/
│   ├── api/            # FastAPI routers & dependency injection
│   ├── application/    # Use cases, services, ports (Port/Adapter)
│   ├── domain/         # Entities, repository interfaces (pure logic)
│   ├── infrastructure/ # DB, LLM, RAG, external API adapters
│   └── core/           # Config, JWT
├── dashboard/          # Streamlit (Home / Trends / Insights / Discover)
├── alembic/            # DB migrations
├── tests/
└── docs/
```

---

## Troubleshooting

### Hybrid Search Performance Issues

**문제**: 검색 결과가 느리거나 부정확합니다.

**해결**: cutoff 최적화가 적용된 하이브리드 검색 전략을 사용합니다.

자세한 하이브리드 검색 튜닝과 성능 최적화는 [docs/troubleshooting/hybrid-search.md](docs/troubleshooting/hybrid-search.md)를 참고하세요.

### Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: dashboard` | Add `sys.path.insert(0, os.path.dirname(__file__))` to `dashboard/app.py` |
| `pgvector extension not found` | Install pgvector: `CREATE EXTENSION vector;` in PostgreSQL |
| `Telegram webhook not responding` | Verify webhook URL is publicly accessible and HTTPS |
| `OpenAI API errors` | Check API key and rate limits; see [OpenAI docs](https://platform.openai.com/docs) |
| `Notion sync fails` | Verify Notion OAuth token and page permissions |
| `Pydantic validation errors` | Check `.env` has all required variables; use `extra="ignore"` in Settings |

더 많은 해결 방법은 [Troubleshooting Guide](docs/troubleshooting/)를 참고하세요.

---

## Tech Stack

| Category | Technology |
|----------|-----------|
| **Backend** | Python 3.11+ · FastAPI (Async) · SQLAlchemy |
| **Database** | PostgreSQL 16 + pgvector |
| **AI / LLM** | OpenAI GPT-4.1 · text-embedding-3-small (1536 dims) · Jina Reader |
| **Hybrid RAG** | Dense (pgvector cosine) + Sparse (Full-Text Search) + Rerank |
| **Integrations** | Telegram Bot API (Webhook) · Notion API (OAuth 2.0 + Page Sync) |
| **Frontend** | Streamlit |
| **Scheduler** | APScheduler |
| **Security** | Fernet · JWT |
| **Infrastructure** | GCP VM · Docker · NGINX · GitHub Actions |
| **Testing** | pytest |

---

## License

이 프로젝트는 MIT License를 따릅니다. 자세한 내용은 [LICENSE](LICENSE)를 참고하세요.

### Summary

- **Permissions**: Commercial use, modification, distribution, private use
- **Conditions**: License and copyright notice
- **Limitations**: No liability or warranty

전체 라이선스 본문은 [LICENSE](LICENSE)를 참고하세요.
