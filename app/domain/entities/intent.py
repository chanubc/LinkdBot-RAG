from enum import Enum


class Intent(str, Enum):
    """사용자 메시지의 의도 분류."""

    SEARCH = "search"
    MEMO = "memo"
    MEMO_RECALL = "memo_recall"
    ASK = "ask"
    START = "start"
    HELP = "help"
    UNKNOWN = "unknown"
