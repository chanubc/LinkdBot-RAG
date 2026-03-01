"""Streamlit 대시보드용 loguru 설정.

FastAPI 서버와 별개 프로세스이므로 uvicorn 인터셉터 없이 단순하게 구성.
표준 logging(streamlit 내부 포함)도 loguru로 인터셉트.
"""
import logging
import sys

from loguru import logger

__all__ = ["logger", "setup_logging"]


class _InterceptHandler(logging.Handler):
    """표준 logging → loguru 인터셉트."""

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

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(level: str = "INFO") -> None:
    """loguru 초기화 및 streamlit 표준 logging 인터셉트."""
    logger.remove()

    logger.add(
        sys.stdout,
        level=level,
        colorize=True,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        backtrace=True,
        diagnose=False,
    )

    # streamlit 내부 logging 인터셉트
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("streamlit", "streamlit.runtime", "tornado"):
        logging.getLogger(name).handlers = [_InterceptHandler()]
        logging.getLogger(name).propagate = False
