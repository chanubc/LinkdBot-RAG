import os

_REQUIRED_TEST_ENV = {
    'DATABASE_URL': 'postgresql+asyncpg://test:test@localhost/test',
    'OPENAI_API_KEY': 'test',
    'TELEGRAM_BOT_TOKEN': 'test',
    'TELEGRAM_WEBHOOK_URL': 'https://example.com/webhook',
    'NOTION_CLIENT_ID': 'test',
    'NOTION_CLIENT_SECRET': 'test',
    'NOTION_REDIRECT_URI': 'https://example.com/notion',
    'ENCRYPTION_KEY': 'VqEq2rCnzMq-AcS0MditpkHKtCiJQy32Wcsw1nJ78qE=',
}

for key, value in _REQUIRED_TEST_ENV.items():
    os.environ.setdefault(key, value)
