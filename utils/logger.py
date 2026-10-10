import io
import logging
import os
import sys
from typing import Optional
from config.settings import settings


_LOGGERS: dict[str, logging.Logger] = {}


class ScenarioLogCapture(logging.Handler):
    """In-memory log handler to capture logs per Behave scenario for HTML report embedding."""

    def __init__(self, level: int = logging.NOTSET):
        super().__init__(level)
        self.buffer = io.StringIO()
        self.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.buffer.write(msg + "\n")
        except Exception:
            self.handleError(record)

    def get_logs(self) -> str:
        return self.buffer.getvalue()

    def clear(self) -> None:
        self.buffer.truncate(0)
        self.buffer.seek(0)

    def close(self) -> None:
        self.buffer.close()
        super().close()


_SHARED_FILE_HANDLER: Optional[logging.FileHandler] = None


def _get_shared_file_handler(log_level: int, formatter: logging.Formatter) -> logging.FileHandler:
    """Retrieve or create singleton FileHandler with mode='w' to overwrite test_run.log per test session."""
    global _SHARED_FILE_HANDLER
    if _SHARED_FILE_HANDLER is None:
        os.makedirs(settings.reports_dir, exist_ok=True)
        log_file_path = os.path.join(settings.reports_dir, "test_run.log")
        # mode='w' ensures previous test run logs are overwritten, never appended
        _SHARED_FILE_HANDLER = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
        _SHARED_FILE_HANDLER.setLevel(log_level)
        _SHARED_FILE_HANDLER.setFormatter(formatter)
    return _SHARED_FILE_HANDLER


def get_logger(name: str = "framework") -> logging.Logger:
    """Retrieve or configure a structured logger instance.
    
    Logs to both standard output and a file inside the configured reports directory.
    """
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Avoid duplicate handlers if logger was previously retrieved
    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 1. Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 2. File Handler (overwrites test_run.log per test run, never appends previous runs)
        file_handler = _get_shared_file_handler(log_level, formatter)
        logger.addHandler(file_handler)

    _LOGGERS[name] = logger
    return logger


# Default framework logger
logger: logging.Logger = get_logger("playwright")
