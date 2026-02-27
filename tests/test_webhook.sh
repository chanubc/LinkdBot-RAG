#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# 로컬 웹훅 시뮬레이션 스크립트
# 사용법: bash scripts/test_webhook.sh <scenario>
#
# Prerequisites:
#   uvicorn app.main:app --reload  (별도 터미널에서 실행)
#
# 환경변수:
#   TELEGRAM_ID  — 본인 텔레그램 user ID (기본값: 123456789)
#   HOST         — 서버 주소 (기본값: http://localhost:8000)
# ─────────────────────────────────────────────────────────────────────────────

HOST="${HOST:-http://localhost:8000}"
TELEGRAM_ID="${TELEGRAM_ID:-123456789}"
ENDPOINT="$HOST/api/v1/webhook/telegram"

# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────

post() {
  echo "▶ POST $ENDPOINT"
  echo "  payload: $1"
  echo ""
  curl -s -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$1" | python3 -m json.tool 2>/dev/null || echo "(응답 없음)"
  echo ""
}

make_message() {
  # make_message <text>
  cat <<EOF
{
  "update_id": $RANDOM,
  "message": {
    "message_id": $RANDOM,
    "from": {
      "id": $TELEGRAM_ID,
      "is_bot": false,
      "first_name": "TestUser",
      "username": "testuser"
    },
    "chat": { "id": $TELEGRAM_ID, "type": "private" },
    "date": $(date +%s),
    "text": "$1"
  }
}
EOF
}

# ── 시나리오 ──────────────────────────────────────────────────────────────────

scenario_start() {
  echo "=== [/start] Notion 연동 여부 확인 ==="
  post "$(make_message "/start")"
}

scenario_url() {
  URL="${2:-https://example.com}"
  echo "=== [url] URL 메시지 처리: $URL ==="
  post "$(make_message "$URL")"
}

scenario_url_with_memo() {
  echo "=== [url_memo] URL + 메모 함께 전송 ==="
  post "$(make_message "https://example.com 나중에 꼭 읽어보기")"
}

scenario_memo() {
  MEMO="${2:-오늘 배운 파이썬 팁 정리}"
  echo "=== [/memo] 메모 저장: $MEMO ==="
  post "$(make_message "/memo $MEMO")"
}

scenario_memo_empty() {
  echo "=== [memo_empty] /memo 내용 없이 전송 ==="
  post "$(make_message "/memo")"
}

scenario_search() {
  QUERY="${2:-머신러닝}"
  echo "=== [/search] 검색: $QUERY ==="
  post "$(make_message "/search $QUERY")"
}

scenario_search_empty() {
  echo "=== [search_empty] /search 검색어 없이 전송 ==="
  post "$(make_message "/search")"
}

scenario_text() {
  TEXT="${2:-인공지능 관련 자료}"
  echo "=== [text] 일반 텍스트 (검색으로 처리): $TEXT ==="
  post "$(make_message "$TEXT")"
}

scenario_callback_help() {
  echo "=== [callback] 도움말 버튼 클릭 ==="
  post "{
    \"update_id\": $RANDOM,
    \"callback_query\": {
      \"id\": \"$(date +%s%N)\",
      \"from\": {
        \"id\": $TELEGRAM_ID,
        \"is_bot\": false,
        \"first_name\": \"TestUser\"
      },
      \"message\": {
        \"message_id\": $RANDOM,
        \"chat\": { \"id\": $TELEGRAM_ID, \"type\": \"private\" },
        \"date\": $(date +%s)
      },
      \"data\": \"help\"
    }
  }"
}

# ── 진입점 ────────────────────────────────────────────────────────────────────

SCENARIO="${1:-help}"

case "$SCENARIO" in
  start)           scenario_start ;;
  url)             scenario_url "$@" ;;
  url_memo)        scenario_url_with_memo ;;
  memo)            scenario_memo "$@" ;;
  memo_empty)      scenario_memo_empty ;;
  search)          scenario_search "$@" ;;
  search_empty)    scenario_search_empty ;;
  text)            scenario_text "$@" ;;
  callback)        scenario_callback_help ;;
  all)
    scenario_start
    scenario_url
    scenario_url_with_memo
    scenario_memo
    scenario_memo_empty
    scenario_search
    scenario_search_empty
    scenario_text
    scenario_callback_help
    ;;
  *)
    cat <<HELP
사용법: bash scripts/test_webhook.sh <scenario> [args]

시나리오:
  start           /start 커맨드 (Notion 연동 여부 확인)
  url [URL]       URL 메시지 (기본: https://example.com)
  url_memo        URL + 메모 함께 전송
  memo [TEXT]     /memo 커맨드 (기본: "오늘 배운 파이썬 팁 정리")
  memo_empty      /memo 내용 없이 (에러 메시지 확인)
  search [QUERY]  /search 커맨드 (기본: "머신러닝")
  search_empty    /search 검색어 없이 (에러 메시지 확인)
  text [TEXT]     일반 텍스트 → 검색으로 처리
  callback        도움말 인라인 버튼 클릭
  all             모든 시나리오 순서대로 실행

환경변수:
  TELEGRAM_ID=<your_id>  bash scripts/test_webhook.sh start
  HOST=http://localhost:8001  bash scripts/test_webhook.sh url
HELP
    ;;
esac
