# 🧰 Tech Stack

## Backend
- Python 3.10+
- FastAPI
- SQLAlchemy
- PostgreSQL
- pgvector

## AI
- Jina Reader (content extraction via `https://r.jina.ai/{url}`)
- OpenAI GPT-4o (summarization, categorization, keyword extraction)
- OpenAI `text-embedding-3-small` (vector embeddings, 1536 dims)

## External Integrations
- Telegram Bot API (webhook)
- Notion API (OAuth 2.0 + page creation)

## Scheduler
- APScheduler

## Security
- `cryptography` library (Fernet) for `notion_access_token` encryption

## Dashboard
- Streamlit (Phase 3)

## Testing
- pytest
