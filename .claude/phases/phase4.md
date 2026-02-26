# 🤖 Phase 4 — LangGraph Agent

## Goal

기존 OpenAI Function Calling 기반 AgentService를 LangGraph 그래프 기반으로 전환.
단순 선형 흐름을 넘어 멀티스텝 추론, 조건 분기, 사용자 피드백 루프를 지원하는 복잡한 Agent를 구축한다.

---

## Prerequisites

Phase 2, 3이 완료된 상태에서 시작한다.

- Phase 2 완료: `application/services/agent_service.py` (OpenAI Function Calling)
- Phase 3 완료: Proactive Agent (drift, scoring, weekly report)
- `rag/` 모듈 완료: retriever, reranker

---

## Why LangGraph?

### Phase 2 Agent의 한계

```
Phase 2 (선형):
  메시지 → LLM intent 판단 → tool 1개 호출 → 결과 반환 → 끝
```

- Tool 호출 1회로 끝남 (결과가 부족해도 재시도 불가)
- 여러 tool을 순차/병렬 조합할 수 없음
- 사용자 피드백을 받아 흐름을 분기할 수 없음
- 중간 상태 유지 불가 (stateless)

### Phase 4 Agent가 해결하는 것

```
Phase 4 (그래프):
  메시지 → intent 판단 → 검색 → 결과 충분? ─No─→ 쿼리 재작성 → 재검색
                                    │                          │
                                   Yes                         │
                                    ↓                          │
                              답변 생성 ←─────────────────────────┘
                                    │
                                    ↓
                              사용자 피드백 → 후속 질문 루프
```

---

## Architecture

### 디렉토리 구조

```
app/agents/                      # LangGraph Agent
├── graph.py                     # 메인 그래프 정의 (StateGraph 조합)
├── state.py                     # AgentState TypedDict 정의
├── nodes/                       # 개별 노드 (각 노드 = 1개 함수)
│   ├── intent_node.py           # 사용자 의도 분류
│   ├── search_node.py           # RAG 검색 (rag/ 모듈 활용)
│   ├── rewrite_node.py          # 검색 결과 부족 시 쿼리 재작성
│   ├── answer_node.py           # 최종 답변 생성
│   ├── report_node.py           # 주간 리포트 생성 (Phase 3 로직 재사용)
│   └── feedback_node.py         # 사용자 피드백 처리
└── tools/                       # LangGraph Tool 정의
    ├── search_tool.py           # search_knowledge_base (기존 rag/ 래핑)
    ├── unread_tool.py           # get_unread_links (기존 LinkRepository 래핑)
    └── drift_tool.py            # get_interest_drift (기존 domain/drift.py 래핑)
```

### 기존 모듈 재사용

| agents/ 내부 | 재사용 대상 | 관계 |
|---|---|---|
| `nodes/search_node.py` | `rag/retriever.py`, `rag/reranker.py` | import해서 사용 |
| `nodes/report_node.py` | `domain/drift.py`, `domain/scoring.py` | import해서 사용 |
| `tools/search_tool.py` | `rag/retriever.py` | Tool로 래핑 |
| `tools/unread_tool.py` | `ILinkRepository` | Tool로 래핑 |
| `tools/drift_tool.py` | `domain/drift.py` | Tool로 래핑 |

**원칙: agents/는 새로운 로직을 만들지 않는다. 기존 모듈을 그래프로 조합만 한다.**

---

## Agent State

```python
# app/agents/state.py
from typing import TypedDict

class AgentState(TypedDict):
    messages: list              # 대화 히스토리
    user_id: int                # telegram_id
    intent: str | None          # 분류된 의도
    search_query: str | None    # 검색 쿼리
    search_results: list        # 검색 결과
    retry_count: int            # 재검색 횟수
    final_answer: str | None    # 최종 답변
```

---

## Graph 구조

```python
# app/agents/graph.py (개념)
from langgraph.graph import StateGraph, END

graph = StateGraph(AgentState)

# 노드 등록
graph.add_node("intent", intent_node)
graph.add_node("search", search_node)
graph.add_node("rewrite", rewrite_node)
graph.add_node("answer", answer_node)

# 엣지 정의
graph.set_entry_point("intent")
graph.add_edge("intent", "search")
graph.add_conditional_edges("search", should_rewrite, {
    "rewrite": "rewrite",
    "answer": "answer",
})
graph.add_edge("rewrite", "search")    # 재검색 루프
graph.add_edge("answer", END)

agent = graph.compile()
```

### 흐름도

```
[intent] → [search] → 결과 충분? ─Yes─→ [answer] → END
                          │
                          No (retry_count < 2)
                          │
                          ↓
                      [rewrite] → [search] (루프)
```

---

## Integration

### Router 연결

```python
# app/api/v1/endpoints/webhook.py
# Phase 4에서 기존 AgentService 호출을 LangGraph Agent로 교체

@router.post("/telegram")
async def handle_webhook(
    update: TelegramUpdate,
    agent: CompiledGraph = Depends(get_agent_graph),
):
    # /ask 명령어 → LangGraph Agent 실행
    result = await agent.ainvoke({
        "messages": [update.text],
        "user_id": update.chat_id,
        "retry_count": 0,
    })
```

### DI Factory

```python
# app/api/dependencies/agent_di.py
def get_agent_graph(
    retriever: HybridRetriever = Depends(get_retriever),
    link_repo: ILinkRepository = Depends(get_link_repository),
    openai: IOpenAIRepository = Depends(get_openai_repository),
    telegram: ITelegramRepository = Depends(get_telegram_repository),
) -> CompiledGraph:
    return build_agent_graph(retriever, link_repo, openai, telegram)
```

---

## Migration from Phase 2

### Phase 2 → Phase 4 전환 전략

| 항목 | Phase 2 (현재) | Phase 4 (전환 후) |
|---|---|---|
| Agent 위치 | `application/services/agent_service.py` | `agents/graph.py` |
| 의도 판단 | OpenAI Function Calling | `agents/nodes/intent_node.py` |
| 검색 | 단일 호출 | 재검색 루프 (결과 부족 시 쿼리 재작성) |
| Tool 정의 | Function schema dict | `agents/tools/*.py` (LangGraph Tool) |
| 상태 관리 | Stateless | `AgentState` (대화 히스토리 유지) |
| 확장성 | 새 tool 추가 시 if/else 증가 | 새 노드/엣지 추가로 그래프 확장 |

### 전환 순서

1. `agents/state.py` 작성
2. 기존 AgentService의 tool들을 `agents/tools/`로 이동
3. 각 노드 구현 (`agents/nodes/`)
4. `agents/graph.py`에서 그래프 조합
5. DI Factory 추가 → Router에서 graph 주입
6. 기존 `application/services/agent_service.py` 제거
7. 테스트 작성

---

## Features (Phase 4 단계별)

### 4.1: Core Graph
- [ ] `agents/` 디렉토리 생성
- [ ] `state.py`, `graph.py` 기본 구조
- [ ] `intent_node`, `search_node`, `answer_node` 구현
- [ ] 기존 AgentService 대체
- [ ] 테스트 작성

### 4.2: Query Rewrite Loop
- [ ] `rewrite_node` 구현 (검색 결과 부족 시 쿼리 재작성)
- [ ] conditional edge 추가 (should_rewrite 판단)
- [ ] retry_count 제한 (max 2회)
- [ ] 테스트 작성

### 4.3: Proactive Integration
- [ ] `report_node` 구현 (Phase 3 drift/scoring 재사용)
- [ ] `drift_tool` 추가
- [ ] 주간 리포트도 Agent 그래프로 실행 가능하게 확장
- [ ] 테스트 작성

### 4.4: Conversation Loop (향후)
- [ ] `feedback_node` 구현
- [ ] 사용자 후속 질문 처리
- [ ] 대화 히스토리 기반 컨텍스트 유지
- [ ] 멀티턴 대화 지원

---

## Constraints

- **기존 모듈을 재작성하지 않는다** — agents/는 rag/, domain/, infrastructure/를 조합만 한다.
- **Phase 2 Agent가 먼저 안정화된 후 전환한다** — Function Calling으로 충분한 동안은 전환하지 않는다.
- **노드는 순수하게 유지한다** — 각 노드는 State를 받아 State를 반환하는 함수. 부수효과는 Infrastructure를 통해서만.
- **점진적 전환** — 한 번에 모든 기능을 LangGraph로 옮기지 않는다. Core Graph 먼저, 확장은 단계별로.
- Maintain architecture separation. Do not collapse layers.

---

## Dependencies

```
# requirements.txt에 추가
langgraph>=0.2.0
langchain-core>=0.3.0
langchain-openai>=0.2.0
```
