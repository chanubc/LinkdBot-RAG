# LinkdBot-RAG Project AGENTS.md

- Global OMX / runtime / skill behavior lives in `/home/chanu/AGENTS.md`
- This file is only for LinkdBot-RAG-specific rules
- Do not modify `CLAUDE.md` unless explicitly asked

## Project state

- This repo is effectively at **Phase 3 complete / Phase 4 preparation**
- Phase 4 means preparing for **LangGraph orchestration**
- Prefer incremental cleanup before broad framework rewrites

## Source of truth

- `CLAUDE.md` and `.claude/*` are reference docs for this repo
- `.claude/` is already indexed here
- Read them only when relevant to the task
- If docs and code differ, trust the current code structure first

## Architecture rules

- `app/api/` → presentation only
- `app/application/` → use cases, services, ports, agent orchestration
- `app/domain/` → pure domain logic and repository interfaces
- `app/infrastructure/` → repositories, adapters, external clients, RAG implementation

- keep domain logic pure
- use FastAPI `Depends` for DI only
- depend on interfaces / ports in application code
- create concrete implementations in DI factories
- avoid circular imports
- avoid collapsing layers for convenience

## Repo coding rules

- prefer small, reviewable, reversible diffs
- reuse existing utils and patterns before adding abstractions
- avoid thin pass-through wrappers
- keep responsibilities clear:
  - `TelegramWebhookHandler` → webhook/input branching
  - `MessageRouterService` → command/intent routing
  - use cases → business write flows
  - agent layer → answer generation/orchestration
- add or update tests when behavior changes
- verify before claiming completion

## Phase 4 guidance

- use LangGraph as an orchestration layer
- reuse existing RAG, repository, and domain logic where possible
- prefer nodes that compose existing code instead of reimplementing it
- prefer agent logic that can return structured results/state
- avoid broad LangChain abstractions unless they clearly simplify the codebase

## Workflow note

For feature/issue/branch startup workflow, use:

- `.claude/commands/start-feature.md`
- `.agents/skills/start-feature/SKILL.md`
