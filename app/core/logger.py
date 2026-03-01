"""Loguru 기반 로깅 설정.

표준 logging 핸들러를 인터셉트하여 uvicorn/sqlalchemy 등 서드파티 로그도
loguru로 통합 출력.
"""
import logging
import sys

from loguru import logger

__all__ = ["logger", "setup_logging"]


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
            # 호출 스택이 얕은 경우 (테스트/특정 런타임) 기본값 사용
            depth = 6

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(level: str = "INFO") -> None:
    """loguru 초기화 및 표준 logging 인터셉트.

    Args:
        level: 로그 레벨 (기본 INFO)
    """
    logger.remove()
    logger.add(
        sys.stdout,
        level=level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        backtrace=True,
        diagnose=False,  # 기본값: 민감정보(토큰/키) 유출 방지
    )

    # 표준 logging 핸들러 전체 인터셉트
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(name).handlers = [_InterceptHandler()]
        logging.getLogger(name).propagate = False
