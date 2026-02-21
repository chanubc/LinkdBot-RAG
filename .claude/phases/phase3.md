# 🤖 Phase 3 — Proactive Agent

## Goal

Turn system into a proactive AI agent.

---

## Features

- APScheduler weekly job
- Drift + Reactivation execution
- LLM-generated weekly insight
- Telegram push message
- Streamlit dashboard
- Explainable scoring breakdown

---

## Scheduling (`app/services/report_service.py`)

APScheduler를 FastAPI 구동 시 연결. 매주 월요일 오전 9시 KST 실행.

### Workflow

1. **Analyze:** `app/domain/drift.py` → 관심사 변화 수치 계산
2. **Select:** `app/domain/scoring.py` → `is_read=False` 링크 중 Reactivation Score 1위 선정
3. **Draft:** LLM → 브리핑 메시지 생성
4. **Push:** 텔레그램 발송 + `[읽음 처리]` Inline Keyboard Button으로 사용자 상호작용 유도

---

## Constraints

Maintain architecture separation.
Do not collapse layers.
