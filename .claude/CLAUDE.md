# 🧠 LinkdBot-RAG — CLAUDE GUIDE

## Project Identity

This is NOT a simple RAG chatbot.

This is a **Proactive AI Knowledge Copilot** designed to:

- Store user-shared links (via Telegram)
- Convert content into structured knowledge
- Detect interest drift
- Reactivate forgotten knowledge
- Send proactive weekly insights

The system focuses on behavioral impact, not passive retrieval.

---

## Architecture Style

Pragmatic Clean Architecture.

Layers:
1. Presentation (FastAPI routers)
2. Application (Services / Agent orchestration)
3. Domain (Pure logic)
4. Infrastructure (DB + External APIs)

---

## Core Principles

- Keep domain logic pure.
- Use FastAPI Depends for DI.
- **Strict SRP (Single Responsibility Principle):** Prevent 'God Objects'. A service should orchestrate one clear flow, not manage 10 different dependencies.
- **Decouple External I/O:** Always depend on interfaces (ABC) for external systems (LLM, Telegram, Scraper), NOT concrete classes.
- Avoid over-engineering, **but do not compromise loose coupling.** (미래를 대비한 불필요한 추상화는 피하되, 현재 필요한 계층 간 분리는 타협하지 않는다.)
- No circular imports.
- Keep layers separated.

---

## Current Development Strategy

Follow phase-based development.

Never implement future phase logic unless explicitly instructed.

---

## Reference Documents

- Architecture & DB Schema: `.claude/architecture.md`
- Coding Rules: `.claude/coding_rules.md`
- Tech Stack: `.claude/stack.md`
- Phase 1 (수집 & 인프라): `.claude/phases/phase1.md`
- Phase 2 (RAG & Agent): `.claude/phases/phase2.md`
- Phase 3 (Proactive Agent): `.claude/phases/phase3.md`
- Drift Logic: `.claude/context/drift.md`
- Reactivation Logic: `.claude/context/reactivation.md`
- Vector Strategy: `.claude/context/vector_strategy.md`
