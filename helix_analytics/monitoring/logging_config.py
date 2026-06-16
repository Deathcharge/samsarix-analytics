"""
Helix Logging Configuration
Centralized logging setup for Helix Collective components
"""

import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "Helix/logs",
    console_output: bool = True,
    file_output: bool = True,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if file_output:
        main_handler = logging.handlers.RotatingFileHandler(
            log_path / "helix.log", maxBytes=max_bytes, backupCount=backup_count
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(formatter)
        root_logger.addHandler(main_handler)

        error_handler = logging.handlers.RotatingFileHandler(
            log_path / "errors.log", maxBytes=max_bytes, backupCount=backup_count
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)

    return root_logger


class HelixLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.performance_score = 0.0

    def set_performance_score(self, level: float):
        self.performance_score = level

    def info(self, message: str, *args, **kwargs):
        self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self.logger.error(message, *args, **kwargs)

    def system(self, message: str, *args, **kwargs):
        self.logger.info(
            f"[UCF: {self.performance_score:.3f}] SYSTEM: {message}",
            *args,
            **kwargs,
        )


def get_logger(name: str) -> HelixLogger:
    return HelixLogger(name)
