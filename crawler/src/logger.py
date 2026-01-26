"""Logging configuration for the crawler."""

import logging
import sys
from pathlib import Path

# Color codes for terminal output
COLORS = {
    "DEBUG": "\033[36m",  # Cyan
    "INFO": "\033[32m",  # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "CRITICAL": "\033[35m",  # Magenta
    "RESET": "\033[0m",
}


class ColorFormatter(logging.Formatter):
    """Custom formatter with colored level names for console output."""

    def format(self, record: logging.LogRecord) -> str:
        # Color the level name
        level_color = COLORS.get(record.levelname, "")
        reset = COLORS["RESET"]

        # Format the message
        record.levelname = f"{level_color}{record.levelname}{reset}"
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    log_dir: Path | None = None,
):
    """
    Configure logging for the crawler.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional filename for file logging
        log_dir: Directory for log files (defaults to current dir)
    """
    # Get the root logger for the crawler package
    root_logger = logging.getLogger("src")
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = ColorFormatter(
        "%(levelname)s %(name)s: %(message)s"
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File handler (no colors, more detail)
    if log_file:
        if log_dir:
            log_path = log_dir / log_file
        else:
            log_path = Path(log_file)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
