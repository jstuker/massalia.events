"""
Logging configuration for the crawler.

This module provides a comprehensive logging system with configurable levels,
colored console output, rotating file handler, and optional JSON formatting.

Usage:
    from src.logger import setup_logging, get_logger

    # Configure logging at startup
    setup_logging(level="INFO", log_file="crawler.log")

    # Get a logger in any module
    logger = get_logger(__name__)
    logger.info("Processing event: %s", event_name)
"""

import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# Default log format strings
CONSOLE_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
JSON_FORMAT = None  # Handled by JSONFormatter

# Default configuration
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_BACKUP_COUNT = 5
DEFAULT_LOG_LEVEL = "INFO"

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
    """
    Custom formatter that adds ANSI colors to log level names for console output.

    This formatter preserves the original log level name width while adding
    color codes, making the console output both readable and visually organized.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colored level name."""
        # Store original level name
        original_levelname = record.levelname

        # Apply color to level name
        level_color = COLORS.get(record.levelname, "")
        reset = COLORS["RESET"]
        record.levelname = f"{level_color}{record.levelname}{reset}"

        # Format the message
        result = super().format(record)

        # Restore original level name
        record.levelname = original_levelname
        return result


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs log records as JSON objects.

    This is useful for log aggregation systems, structured logging pipelines,
    and automated log analysis tools.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON object."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "taskName",
                "message",
            }
        }
        if extra_fields:
            log_data["extra"] = extra_fields

        return json.dumps(log_data, default=str)


def setup_logging(
    level: str = DEFAULT_LOG_LEVEL,
    log_file: str | None = None,
    log_dir: Path | None = None,
    log_format: str = "text",
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Logger:
    """
    Configure logging for the crawler application.

    This function sets up a comprehensive logging system with:
    - Colored console output for human readability
    - Optional rotating file handler to prevent unbounded log growth
    - Support for both text and JSON output formats

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            DEBUG shows all details including URLs, selectors, and data.
            INFO shows normal operations like sources crawled and events created.
            WARNING shows non-critical issues like missing fields or retries.
            ERROR shows failures that skip items like parse errors.
            CRITICAL shows fatal errors that stop execution.
        log_file: Optional filename for file logging. If provided, logs are
            written to this file in addition to console output.
        log_dir: Directory for log files. Defaults to current working directory.
            The directory is created if it doesn't exist.
        log_format: Output format for log files. "text" for human-readable
            format, "json" for structured JSON format.
        max_bytes: Maximum size of log file before rotation (default 10MB).
        backup_count: Number of backup files to keep (default 5).

    Returns:
        The configured root logger instance.

    Example:
        >>> setup_logging(level="DEBUG", log_file="crawler.log")
        >>> logger = get_logger(__name__)
        >>> logger.info("Crawler started")
    """
    # Get the root logger for the crawler package
    root_logger = logging.getLogger("src")
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)  # Let logger level control filtering
    console_formatter = ColorFormatter(CONSOLE_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional, with rotation)
    if log_file:
        # Determine log file path
        if log_dir:
            log_path = log_dir / log_file
            # Create directory if it doesn't exist
            log_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            log_path = Path(log_file)

        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # Capture all levels to file

        # Set formatter based on format option
        if log_format.lower() == "json":
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(FILE_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for use in modules.

    This returns a child logger under the "src" namespace, ensuring
    all crawler logs are properly grouped and can be configured together.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A configured logger instance.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.debug("Detailed debug info")
        >>> logger.info("Normal operation")
        >>> logger.warning("Something might be wrong")
        >>> logger.error("Something failed")
        >>> logger.critical("Cannot continue")
    """
    return logging.getLogger(name)


# Log level guidelines for reference
LOG_LEVEL_GUIDELINES = """
Log Level Guidelines
====================

| Level    | Use For                                                    |
|----------|-----------------------------------------------------------|
| DEBUG    | Detailed info for debugging (URLs, selectors, data)       |
| INFO     | Normal operations (sources crawled, events created)       |
| WARNING  | Non-critical issues (missing fields, retries)             |
| ERROR    | Failures that skip items (parse errors, download fails)   |
| CRITICAL | Fatal errors that stop execution                          |

Examples:
    logger.debug("Fetching URL: %s with selector: %s", url, selector)
    logger.info("Successfully fetched %d events from %s", count, source)
    logger.warning("Rate limit approaching for %s", source)
    logger.error("Failed to parse HTML: %s", error)
    logger.critical("Configuration file not found, cannot continue")
"""
