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
- Avoid over-engineering.
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
