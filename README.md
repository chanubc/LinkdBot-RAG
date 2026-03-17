# LinkdBot-RAG

> Proactive AI Knowledge Copilot — Store user-shared links, convert to structured knowledge, detect interest drift, send proactive insights

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Async-green)](https://fastapi.tiangolo.com/)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Demo

| Save Link Flow | Knowledge Agent (/ask) | Dashboard Home |
|:-:|:-:|:-:|
| ![Save Link](docs/assets/screenshots/demo-save-link.png) | ![Knowledge Agent](docs/assets/screenshots/demo-ask.png) | ![Dashboard](docs/assets/screenshots/demo-dashboard.png) |
| Send any URL to Telegram bot → Auto-extract content, analyze with AI, store with vector embeddings, sync to Notion | Ask questions about your knowledge base → Hybrid search + AI agent answers with function calling → RAG-powered responses | Browse collected links, discover trends, manage personal knowledge library with smart filtering |

---

## Features

### Smart Link Collection
- Send any URL directly to the Telegram bot
- Auto-extract URLs from text messages
- Normalize URLs and prevent duplicates

### Intelligent Indexing
- Content scraping from URLs using Jina Reader
- Semantic analysis with OpenAI embeddings and keyword extraction

### Hybrid RAG Search
- Dense search (semantic similarity) + Sparse search (keyword matching)
- Rerank results with keyword overlap optimization for better accuracy

### Proactive Knowledge
- Interest drift detection based on activity patterns
- Reactivation scoring to resurface relevant old knowledge
- Weekly digest reports sent directly to Telegram

### Multi-Platform
- **Telegram Bot**: Primary interface (slash commands, auto-collection)
- **Notion Sync**: One-way export with user's Notion workspace (OAuth)
- **Streamlit Dashboard**: Personal knowledge library with analytics
- **REST API**: Full CRUD operations for programmatic access

---

## Workflow

### Main Workflow

The system processes messages in a multi-stage pipeline:

1. **Telegram Webhook** → Receives URL or text message
2. **WebhookHandler** → Extracts URLs and routes message type
3. **MessageRouter** → Classifies intent (SEARCH, MEMO, ASK, etc.)
4. **Parallel Processing** → Three independent flows:
   - **SaveLink** → Scrape, analyze, embed, store, sync Notion
   - **Search** → Hybrid retrieval, rerank, return top results
   - **Knowledge Agent** → Function calling with tools (search KB, get unread links)
5. **Response** → Send results back to Telegram user

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

LinkdBot-RAG uses **Clean Architecture** with dependency inversion:

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

GCP VM(chanu.shop) 위에서 Docker로 실행. NGINX가 리버스 프록시 역할을 하며 FastAPI(:8000)와 Streamlit(:8501)을 서빙.

![System Architecture](docs/assets/system-architecture.png)

### DB Schema

`USERS → LINKS → CHUNKS` 3-테이블 구조. `LINKS`에 summary embedding(Vector 1536)이 저장되고, `CHUNKS`에 전문 검색용 TSVector와 청크 embedding이 저장됨.

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

**Problem**: Search results are slow or inaccurate.

**Solution**: Use optimized hybrid search with cutoff optimization.

For detailed hybrid search tuning and performance optimization, see [docs/troubleshooting/hybrid-search.md](docs/troubleshooting/hybrid-search.md).

### Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: dashboard` | Add `sys.path.insert(0, os.path.dirname(__file__))` to `dashboard/app.py` |
| `pgvector extension not found` | Install pgvector: `CREATE EXTENSION vector;` in PostgreSQL |
| `Telegram webhook not responding` | Verify webhook URL is publicly accessible and HTTPS |
| `OpenAI API errors` | Check API key and rate limits; see [OpenAI docs](https://platform.openai.com/docs) |
| `Notion sync fails` | Verify Notion OAuth token and page permissions |
| `Pydantic validation errors` | Check `.env` has all required variables; use `extra="ignore"` in Settings |

For more solutions, see the [Troubleshooting Guide](docs/troubleshooting/).

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

### Summary

- **Permissions**: Commercial use, modification, distribution, private use
- **Conditions**: License and copyright notice
- **Limitations**: No liability or warranty

For the full license text, see [LICENSE](LICENSE).
