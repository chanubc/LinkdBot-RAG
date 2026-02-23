# 🛠 Coding Rules

## DI Strategy

Use FastAPI Depends.

Service는 **Interface 타입**으로 파라미터를 선언하고, DI 팩토리에서 concrete class를 주입한다.

```python
# ✅ Service — 인터페이스에만 의존
class LinkService:
    def __init__(
        self,
        link_repo: ILinkRepository,
        chunk_repo: IChunkRepository,
    ) -> None: ...

# ✅ DI factory — concrete class 인스턴스화
def get_chunk_repository(db: AsyncSession = Depends(get_db)) -> ChunkRepository:
    return ChunkRepository(db)

def get_link_service(
    link_repo: LinkRepository = Depends(get_link_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
) -> LinkService:
    return LinkService(link_repo, chunk_repo)
```

---

## Domain Rules

- Pure functions only.
- No FastAPI imports.
- No SQLAlchemy imports.
- No HTTP calls.
- **Repository interfaces (ABC)는 domain 레이어에 위치** (`app/domain/repositories/`).

---

## Repository Rules

- `app/domain/repositories/` — 인터페이스(ABC)만 정의. DB 로직 없음.
- `app/infrastructure/repository/` — 인터페이스 구현체. DB 로직만.
- 엔티티별로 Repository를 분리한다 (`LinkRepository`, `ChunkRepository` 등).
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
   - PR 제목 형식: `[PREFIX/#이슈번호] 작업 제목`
   - 예시: `[FEAT/#12] Notion OAuth 콜백 엔드포인트 추가`, `[FIX/#7] 중복 URL 처리 버그 수정`
5. **머지** — `main` PR 머지 시 자동 배포 트리거

### 브랜치 전략

```
feat/#N-xxx ──→ main
               (PR, 자동 배포)
```

- `feat/*`, `fix/*`, `chore/*` 등 작업 브랜치는 **main**으로 PR
- **main** PR 머지 시 GitHub Actions 배포 자동 실행
