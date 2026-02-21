# 🧠 Phase 2 — Intelligence Layer

## Goal

Add RAG search and agent orchestration layer.

---

## Features

- Semantic search via pgvector cosine similarity
- Natural language intent detection
- LLM tool calling (Function Calling)
- Unread link retrieval

---

## Agent Architecture (`app/services/agent_service.py`)

LLM Function Calling을 활용하여 에이전트의 두뇌를 구축한다.

### Tools

1. **`search_knowledge_base(query: str)`**
   - 쿼리 임베딩 → `chunks` 거리순 정렬 → 관련 `Link` 본문 취합

2. **`get_unread_links(limit: int)`**
   - `is_read=False` 최신 링크 조회

### Orchestration

Telegram 메시지 → AgentService → LLM Intent 판단 → Tool 실행 → 최종 답변 → Telegram 회신

---

## Constraints

- Do not modify Phase 1 ingestion pipeline.
- Keep domain logic pure.
- Implement scoring in `app/domain/scoring.py`.
