# README Demo Gallery Refresh Design Spec

**Date:** 2026-03-19
**Target file:** `README.md`
**Goal:** README의 데모 영역을 더 읽기 쉽게 정리하고, Notion / Dashboard 시각 자료를 별도 갤러리로 추가하며, Hybrid RAG 설명 문구를 실제 가치 중심으로 바로잡는다.

---

## 배경

현재 `README.md`의 `Demo` 섹션은 Telegram 모바일 흐름을 빠르게 보여주는 데는 성공하지만, 사용자가 요청한 두 가지 확장 포인트가 반영되어 있지 않다.

1. **Notion DB 화면 부재**
   - README 본문에서는 Notion 동기화를 중요한 기능으로 소개하지만, 시각적으로는 결과 화면이 충분히 드러나지 않는다.
2. **Dashboard 실제 화면 부재**
   - 현재 Demo에는 `/dashboard` 진입용 Telegram 화면만 있고, 실제 웹 Dashboard UI는 보여주지 않는다.
3. **Hybrid RAG 이미지 하단 설명의 설득력 부족**
   - Dense/Sparse/Reranking 요소를 나열하는 수준에 머물러, 왜 이 구성이 검색/질의응답/추천 품질에 중요한지 전달력이 약하다.

사용자 요청의 핵심은 “구조를 과하게 바꾸지 않으면서, README에서 보이는 데모 흐름을 더 보기 좋게 정리”하는 것이다.

---

## 범위

### 포함
- `README.md` 내 Demo 영역 재구성
- 기존 모바일(폰 UI) Demo 블록 유지
- Notion screenshot gallery 추가
- Dashboard screenshot gallery 추가
- Hybrid RAG 설명 문구 수정
- Demo 캡션의 간결한 기술 README 톤 정리

### 제외
- 애플리케이션 동작 변경
- Dashboard 코드 변경
- Notion 동기화 로직 변경
- README의 다른 아키텍처/워크플로/트러블슈팅 섹션 대규모 개편

---

## 사용자 승인된 방향

### 레이아웃 원칙
- 기존 **Telegram 모바일 Demo 블록은 유지**한다.
- 그 아래에 **Notion screenshot block**을 추가한다.
- 그 아래에 **Dashboard screenshot block**을 추가한다.
- 즉, README 상의 시각 흐름은 아래 순서를 따른다.

```text
기존 Demo (폰 UI)
→ Notion DB screenshots
→ Dashboard screenshots
```

### 시각 배치 원칙
- Dashboard 이미지는 가로형 비율이 강하므로, 구현 기본값은 **2열 배치**다.
- 3열 배치는 구현자가 로컬 미리보기 또는 GitHub README 렌더링 기준으로 확인했을 때, 각 이미지의 핵심 UI 텍스트와 카드 구분이 무리 없이 보이는 경우에만 허용한다.
- 위 조건을 만족하지 못하면 자동으로 2열을 사용한다.
- Notion screenshot block도 동일한 HTML table 계열 레이아웃을 사용하되, 이미지 수가 1장이면 단일 이미지, 2장 이상이면 2열 우선 배치를 사용한다.

### 문체 원칙
- 과장된 포트폴리오 톤이 아니라 **기술 README 톤 유지**
- 캡션은 짧고 명확하게 정리
- 기능 나열보다 “무엇을 보여주는 화면인지”가 즉시 이해되도록 작성

---

## 설계

### 1. Demo 섹션 구조

`## Demo` 아래를 세 개의 시각 블록으로 구성한다.

#### 블록 A — Telegram Demo (기존 유지)
현재 존재하는 두 개의 HTML table 기반 모바일 데모는 유지한다.

구성 의도:
- 사용자가 Telegram 기반 주 흐름을 먼저 이해하게 함
- README 상단에서 제품의 핵심 진입점을 유지함
- 기존 구조를 존중해 diff를 작고 안전하게 유지함

허용 변경:
- 각 이미지 아래 캡션 문구 정리
- 제목/alt text/섹션 소제목의 표현 다듬기

비허용 변경:
- 모바일 데모를 별도 섹션으로 분해하는 대규모 구조 변경
- Mermaid/architecture 영역과 섞는 변경
- `telegram-weekly-report-detail.jpg`를 기존 모바일 Demo 블록에 추가하는 변경

#### 블록 B — Notion Screenshot Gallery (신규)
Telegram에서 저장된 링크가 Notion DB에서 어떻게 구조화되는지 보여주는 별도 갤러리 블록을 추가한다.

이 블록의 역할:
- “저장 → 요약 → 동기화”가 실제 결과 화면으로 이어짐을 보여줌
- Notion integration이 단순 체크박스 기능이 아니라, **재탐색 가능한 지식 아카이브**를 만든다는 점을 시각적으로 전달함

표현 방향:
- 제목 예시: `### Notion Knowledge Archive`
- 설명 예시 방향:
  - 링크 메타데이터, 요약, 태그, 상태값이 구조화된 Notion DB
  - Telegram에서 저장한 콘텐츠가 회고와 재사용이 가능한 지식 자산으로 정리됨

레이아웃:
- 이번 작업에서는 **단일 이미지 블록**으로 고정한다.
- HTML table 또는 일반 이미지 삽입 중 더 단순하고 안정적인 방식을 사용한다.
- 캡션은 한 줄 내외로 유지한다.

#### 블록 C — Dashboard Screenshot Gallery (신규)
사용자가 제공한 웹 Dashboard 스크린샷들을 별도 갤러리로 추가한다.

이 블록의 역할:
- `/dashboard`가 단순 진입 링크가 아니라, 실제로는 **저장된 지식을 탐색/회고/재발견하는 웹 보조 인터페이스**임을 보여줌
- Telegram 사용 흐름과 웹 탐색 흐름을 분리해 이해를 돕음

표현 방향:
- 제목 예시: `### Dashboard Views`
- 설명 예시 방향:
  - 라이브러리 탐색
  - 인사이트/트렌드 확인
  - 재발견과 회고를 지원하는 web surface

레이아웃:
- 기본안은 **2열 균등 배치**
- 구현 시 3열이 충분히 readable 하면 3열 시도 가능
- 가로형 이미지 특성상 “너무 작아지는 3열”은 피함

사용자가 현재 제공한 Dashboard 이미지 소스:
- GitHub user-attachments 기반 6장
- 구현 단계에서 로컬 asset으로 저장 후 README에 연결 필요

---

## 확정된 자산 매핑

### A. Notion gallery
현재 사용자 제공 기준으로 **Notion screenshot 1장**을 사용한다.

| Source | Target repo path | 역할 | Caption 방향 | Alt text 방향 |
|---|---|---|---|---|
| `https://github.com/user-attachments/assets/5477af21-1368-43b8-b68a-12758125a396` | `docs/assets/screenshots/notion-db-overview.png` | Notion DB overview 화면 | 저장된 링크, 요약, 메타데이터가 구조화된 knowledge archive | `Notion knowledge archive overview` |

### B. Dashboard gallery
현재 사용자 제공 기준으로 **Dashboard screenshot 6장**을 사용한다.

| Source | Target repo path | 역할 | Caption 방향 | Alt text 방향 |
|---|---|---|---|---|
| `https://github.com/user-attachments/assets/ebe04969-ca68-4e8c-94db-1587bf71bd86` | `docs/assets/screenshots/dashboard-overview-1.png` | Dashboard overview / summary view | 저장된 링크와 핵심 지표를 한눈에 보는 dashboard overview | `Dashboard overview screen 1` |
| `https://github.com/user-attachments/assets/c83e52c3-5e79-4fc6-aab3-fc179adbef37` | `docs/assets/screenshots/dashboard-overview-2.png` | Dashboard secondary overview / list or insight view | 탐색 또는 인사이트 흐름을 보여주는 dashboard view | `Dashboard overview screen 2` |
| `https://github.com/user-attachments/assets/373a1fe0-0222-4435-8028-d3c77f55f3a3` | `docs/assets/screenshots/dashboard-overview-3.png` | Dashboard exploration / metrics view | 검색·탐색·지표 확인을 지원하는 dashboard view | `Dashboard overview screen 3` |
| `https://github.com/user-attachments/assets/b4dc261a-eb4e-486a-8138-605161ec8030` | `docs/assets/screenshots/dashboard-overview-4.png` | Dashboard trend / insight detail view | 관심사 변화나 분석 상세를 보여주는 dashboard view | `Dashboard overview screen 4` |
| `https://github.com/user-attachments/assets/25a5d5c5-f759-441e-a1ae-86301f364332` | `docs/assets/screenshots/dashboard-overview-5.png` | Dashboard discover / analysis view | 재발견과 분석을 보조하는 dashboard view | `Dashboard overview screen 5` |
| `https://github.com/user-attachments/assets/1490c0d9-00c4-4cdb-8329-6bfc317c3764` | `docs/assets/screenshots/dashboard-overview-6.png` | Dashboard library / retrieval support view | 라이브러리 탐색과 retrieval 보조 화면 | `Dashboard overview screen 6` |

구현 메모:
- 위 Caption/Alt text 방향을 기준으로 README 문구를 확정한다.
- README 구조상 6장을 모두 포함하는 것은 확정 범위다.

---

## 캡션/문구 수정 원칙

### A. 기존 모바일 Demo 캡션
캡션은 기능 이름 반복보다 **화면이 보여주는 결과**를 설명하는 문장으로 정리한다.

예시 방향:
- Link Save & Notion Sync
  - 링크 본문을 스크랩·요약하고 Notion DB까지 자동 동기화
- Hybrid RAG Search
  - dense+sparse retrieval과 reranking으로 관련 링크를 안정적으로 탐색
- Knowledge Q&A (`/ask`)
  - 저장된 링크와 메모를 근거로 답변 생성
- Weekly Report
  - drift·reactivation 신호를 바탕으로 다시 볼 링크를 선제적으로 추천
- Dashboard Entry
  - JWT magic link로 웹 dashboard에 안전하게 진입
- Quick Menu
  - 검색·질문·리포트·대시보드 이동을 버튼으로 빠르게 실행

### B. Notion 섹션 설명
문구는 “동기화 성공”보다 **지식 구조화 결과**에 초점을 둔다.

핵심 메시지:
- 저장된 링크가 Notion DB에서 정리된다.
- 요약, 키워드, 메타데이터가 다시 찾기 쉬운 형태로 누적된다.
- 이는 개인 지식 베이스의 아카이빙 표면이다.

### C. Dashboard 섹션 설명
문구는 “대시보드가 있다”보다 **왜 필요한지**를 드러낸다.

핵심 메시지:
- Telegram은 입력/호출 중심 인터페이스
- Dashboard는 탐색/회고/인사이트 확인 중심 인터페이스
- 두 표면이 상호보완적으로 동작한다.

---

## Hybrid RAG 설명 수정안

현재 문제:
- 이미지 하단 설명이 dense/sparse/reranking 요소를 단순 나열하는 수준이라, 실제 효용이 약하게 전달된다.

### 수정 대상 범위
이번 작업에서 Hybrid RAG 관련 문구 수정 범위는 아래 두 곳으로 한정한다.

1. `## Demo` 내 `Hybrid RAG (Dense + Sparse)` 카드의 캡션
2. `### Hybrid RAG Architecture` 바로 아래의 본문 설명 문단

이번 작업에서 **수정하지 않는 위치**:
- `## Core Features` 표의 Hybrid RAG 항목
- `### Why These Matter Most` 내 Hybrid RAG 항목
- `Workflow` / `Architecture` 섹션의 기존 기술 설명

수정 목표:
- Dense retrieval과 sparse retrieval의 상보성을 짧고 정확하게 설명
- 왜 이 조합이 `/search`, `/ask`, 추천/리포트 품질에 중요한지 연결

설명 방향:
- Dense retrieval은 의미적으로 유사한 문서를 찾는 데 강하다.
- Sparse retrieval은 키워드, 고유명사, 정확한 표현 매칭에 강하다.
- 둘을 함께 쓰면 한쪽만 사용할 때 놓치기 쉬운 결과를 더 안정적으로 회수할 수 있다.
- 이후 reranking이 최종 문맥 적합도를 정리해 검색과 답변의 신뢰도를 높인다.

예상 결과 문구 톤:
- 기술적이되 과장하지 않음
- 구성 요소 설명에서 끝나지 않고 “왜 중요한가”를 포함

---

## 구현 시 파일/자산 변경 예상

### 직접 수정
- `README.md`

### 신규 또는 추가 자산 가능성
- `docs/assets/screenshots/...` 아래 Notion screenshot 파일
- `docs/assets/screenshots/...` 아래 Dashboard screenshot 파일

### 자산 처리 원칙
- README에서는 외부 hotlink보다 **repo 내부 asset 경로** 사용을 우선
- 파일명은 용도 기반으로 명확히 부여
- README table에서 폭이 균등하게 유지되도록 동일한 패턴 적용

---

## 수용 기준

구현 완료 시 아래를 만족해야 한다.

1. 기존 모바일 Demo 블록이 유지된다.
2. Notion screenshot block이 별도로 추가된다.
3. Dashboard screenshot block이 별도로 추가된다.
4. Notion block은 현재 확정된 1장 자산을 사용한다.
5. Dashboard block은 현재 확정된 6장 자산을 모두 사용한다.
6. Dashboard 갤러리는 기본적으로 2열을 사용하고, 3열은 각 이미지의 핵심 UI 텍스트와 카드 구분이 충분히 읽힐 때만 허용된다.
7. Hybrid RAG 설명 수정은 Demo 카드 캡션과 `### Hybrid RAG Architecture` 아래 설명 문단에만 반영된다.
8. Hybrid RAG 설명이 “구성 나열”이 아니라 “검색 품질에 왜 중요한지”를 설명한다.
9. GitHub README 렌더 기준으로 모든 이미지 경로가 정상 동작한다.
10. GitHub README 렌더 기준으로 HTML table 또는 이미지 블록이 깨지지 않는다.
11. 2열 또는 3열 배치 여부와 무관하게 Dashboard 각 이미지의 핵심 UI 텍스트와 카드 구분이 식별 가능하다.
12. README 전체 톤은 여전히 기술 문서 스타일을 유지한다.

---

## 리스크 및 대응

### 리스크 1 — 가로형 Dashboard 이미지의 과도한 축소
대응:
- 3열이 너무 작으면 2열로 전환
- HTML table 폭을 고정적으로 맞추되, readability를 우선

### 리스크 2 — 외부 첨부 이미지를 로컬 asset으로 옮기는 과정의 실수
대응:
- 이미 확정된 target repo path를 그대로 사용한다.
- README 수정 전 각 파일이 지정 경로에 저장됐는지 확인한다.

### 리스크 3 — Demo 섹션 과밀화
대응:
- 각 블록 사이에 짧은 제목과 1~2문장 설명만 둠
- 장문 설명은 Core Features / Workflow로 넘기고 Demo는 시각 전달에 집중

---

## 구현 메모

실제 구현 시 다음 순서가 안전하다.

1. Dashboard / Notion 이미지 자산을 `docs/assets/screenshots/`에 정리
2. `README.md` Demo 섹션 구조를 확장
3. 모바일 Demo 캡션 문구 정리
4. Notion / Dashboard 갤러리 삽입
5. Hybrid RAG 설명 문구 교체
6. README Markdown/HTML 렌더링이 깨지지 않는지 검토

