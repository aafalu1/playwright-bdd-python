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

        # 2. File Handler (saved to reports directory)
        os.makedirs(settings.reports_dir, exist_ok=True)
        log_file_path = os.path.join(settings.reports_dir, "test_run.log")
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _LOGGERS[name] = logger
    return logger


# Default framework logger
logger: logging.Logger = get_logger("playwright")
