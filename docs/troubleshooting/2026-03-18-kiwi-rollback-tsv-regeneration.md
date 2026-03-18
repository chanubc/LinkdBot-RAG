# Kiwi rollback: production `chunks.tsv` 재생성 절차

PR #95 이전 동작으로 되돌릴 때는 **코드 rollback만으로 끝나지 않는다.**
운영 DB에서 Kiwi 기반으로 저장/백필된 `chunks.tsv` 값도 함께 다시 생성해야
Phase 3 hybrid search(`tsv` / FTS / keyword rescoring)가 코드와 동일한 의미로 동작한다.

## 대상

- Kiwi backfill 실행 당시 이미 존재하던 모든 `chunks`
- Kiwi rollout 이후 `save_chunks()` 경로로 새로 저장된 모든 `chunks`

즉, 안전한 기준은 **운영 DB의 `chunks` 전체를 다시 생성**하는 것이다.

## 사전 조건

1. Kiwi rollback 코드가 배포되어 있어야 한다.
2. 서버에서 `DATABASE_URL` 이 올바르게 설정되어 있어야 한다.
3. 작업 전후 row count와 샘플 검색 결과를 확인할 수 있어야 한다.

## 실행 명령

### 1) Dry run

```bash
docker compose exec -T app python scripts/rebuild_tsvectors_without_kiwi.py --dry-run
```

예상 결과:
- 총 `chunks` row 수 확인
- 실제 UPDATE 없음

### 2) 실제 재생성

```bash
docker compose exec -T app python scripts/rebuild_tsvectors_without_kiwi.py --batch-size 500
```

스크립트가 하는 일:
- `chunks` 를 ID 순서로 batch 조회
- `tsv = to_tsvector('simple', content)` 로 전체 row 재생성
- 마지막에 `ANALYZE chunks` 실행

## GCP 운영 절차 예시

```bash
gcloud compute ssh <INSTANCE_NAME>
cd ~/linkdbot-rag
docker compose exec -T app python scripts/rebuild_tsvectors_without_kiwi.py --dry-run
docker compose exec -T app python scripts/rebuild_tsvectors_without_kiwi.py --batch-size 500
```

## 확인 포인트

### 1) row 수 확인

재생성 전후 전체 row 수가 동일해야 한다.

### 2) NULL 여부 확인

```sql
SELECT COUNT(*) FROM chunks WHERE tsv IS NULL;
```

기대값: `0`

### 3) 샘플 검색 확인

다음처럼 compound/particle 케이스를 앱 또는 SQL smoke check로 확인한다.

- `채용공고를`
- `롯데에서`
- `AI개발자를`

목표:
- Kiwi는 제거됐지만
- 기존 Phase 3 hybrid search는 계속 동작하고
- keyword rescoring 경로와 충돌하지 않아야 함

## 주의

- 이 절차는 **Alembic downgrade 대체물**이다.
- `alembic/versions/0006_rebuild_tsvectors_with_morpheme_tokenization.py` 는 역사적 marker일 뿐,
  운영 데이터 원복을 해주지 않는다.
- `content` 자체를 바꾸는 작업이 아니라 **`tsv`만 재생성**하는 작업이다.
