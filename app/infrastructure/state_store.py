import secrets

_store: dict[str, int] = {}


def create(telegram_id: int) -> str:
    """telegram_id를 매핑하는 단기 state 토큰을 생성하고 반환."""
    token = secrets.token_urlsafe(16)
    _store[token] = telegram_id
    return token


def consume(token: str) -> int | None:
    """토큰으로 telegram_id를 조회하고 저장소에서 제거."""
    return _store.pop(token, None)


class InMemoryStateStore:
    def __init__(self) -> None:
        self._store: dict[str, int] = {}

    def create(self, telegram_id: int) -> str:
        token = secrets.token_urlsafe(16)
        self._store[token] = telegram_id
        return token

    def consume(self, token: str) -> int | None:
        return self._store.pop(token, None)
