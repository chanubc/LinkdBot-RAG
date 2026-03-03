import logging
import re
import sys
from pprint import pformat
from typing import Any

from loguru import logger

__all__ = ["logger", "setup_logging"]


# ✅ HTTP Method 색상 매핑
METHOD_COLORS = {
    "GET": "green",
    "POST": "blue",
    "PUT": "yellow",
    "DELETE": "red",
    "PATCH": "magenta",
}


class _InterceptHandler(logging.Handler):
    """표준 logging → loguru 인터셉트 핸들러."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        try:
            frame, depth = sys._getframe(6), 6
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
        except ValueError:
            depth = 6

        msg = record.getMessage()
        bound_logger = logger.opt(depth=depth, exception=record.exc_info)

        # 💡 핵심 수정 1: uvicorn.access 로그에서 HTTP Method 추출하여 bind
        if record.name == "uvicorn.access":
            # 예: "... "GET /api HTTP/1.1" 200" 형태에서 메서드 추출
            match = re.search(r'"(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD) ', msg)
            if match:
                method = match.group(1)
                # 추출한 메서드를 extra["method"]에 주입
                bound_logger = bound_logger.bind(method=method)

        bound_logger.log(level, msg)


# ✅ 커스텀 포맷터 (HTTP Method 색상 적용)
def _formatter(record: dict) -> str:
    method = record["extra"].get("method")
    method_part = ""

    if method:
        color = METHOD_COLORS.get(method, "white")
        # Loguru의 태그 문법에 맞게 색상 적용
        method_part = f"<{color}><bold>{method:<6}</bold></{color}> | "

    return (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        f"{method_part}"
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
        "<level>{message}</level>\n{exception}"
    )


def pretty_format(data: Any) -> str:
    """사용자가 직접 호출해서 쓸 수 있는 Pretty Helper"""
    if isinstance(data, (dict, list)):
        return "\n" + pformat(data, sort_dicts=False, indent=2)
    return str(data)


def setup_logging(level: str = "INFO") -> None:
    """loguru 초기화 및 표준 logging 인터셉트."""
    logger.remove()

    logger.add(
        sys.stdout,
        level=level,
        colorize=True,
        format=_formatter,  # type: ignore
        backtrace=True,
        diagnose=False,  # 민감정보 보호
    )

    # 표준 logging 핸들러 전체 인터셉트
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "sqlalchemy.engine",
    ):
        logging.getLogger(name).handlers = [_InterceptHandler()]
        logging.getLogger(name).propagate = False
