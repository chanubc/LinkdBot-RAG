# 🛠 Coding Rules

## DI Strategy

Use FastAPI Depends.

Example:

```python
def get_agent_service(
    repo: LinkRepository = Depends(get_repository),
    llm: LLMClient = Depends(get_llm_client)
) -> AgentService:
    return AgentService(repo, llm)
```

---

## Domain Rules

- Pure functions only.
- No FastAPI imports.
- No SQLAlchemy imports.
- No HTTP calls.

---

## Repository Rules

- Only database logic.
- No business logic.
- No scoring logic.

---

## Service Rules

- Orchestration only.
- No raw SQL.
- Call domain for calculations.

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

이슈가 있을 경우 반드시 `#이슈번호`를 앞에 붙인다.
이슈가 없을 경우 prefix만 사용한다.

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
4. **PR 생성** — `feat/#N-xxx` → `main`, 본문에 `Closes #이슈번호` 포함, URL 노출 금지
5. **머지** — `main` PR 머지 시 자동 배포 트리거

### 브랜치 전략

```
feat/#N-xxx ──→ main
               (PR, 자동 배포)
```

- `feat/*`, `fix/*`, `chore/*` 등 작업 브랜치는 **main**으로 PR
- **main** PR 머지 시 GitHub Actions 배포 자동 실행
