"""Tests for the logging module."""

import json
import logging
import tempfile
from pathlib import Path

import pytest

from src.logger import (
    COLORS,
    DEFAULT_BACKUP_COUNT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_BYTES,
    ColorFormatter,
    JSONFormatter,
    get_logger,
    setup_logging,
)


class TestColorFormatter:
    """Tests for the ColorFormatter class."""

    def test_format_adds_color_codes(self):
        """Test that format adds ANSI color codes to log level."""
        formatter = ColorFormatter("%(levelname)s: %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert COLORS["INFO"] in result
        assert COLORS["RESET"] in result
        assert "Test message" in result

    def test_format_preserves_original_level_name(self):
        """Test that the original level name is restored after formatting."""
        formatter = ColorFormatter("%(levelname)s: %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Warning",
            args=(),
            exc_info=None,
        )
        formatter.format(record)
        # Original level name should be preserved
        assert record.levelname == "WARNING"

    @pytest.mark.parametrize(
        "level,color",
        [
            (logging.DEBUG, COLORS["DEBUG"]),
            (logging.INFO, COLORS["INFO"]),
            (logging.WARNING, COLORS["WARNING"]),
            (logging.ERROR, COLORS["ERROR"]),
            (logging.CRITICAL, COLORS["CRITICAL"]),
        ],
    )
    def test_format_uses_correct_color_for_level(self, level, color):
        """Test that each log level uses its correct color."""
        formatter = ColorFormatter("%(levelname)s: %(message)s")
        record = logging.LogRecord(
            name="test",
            level=level,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert color in result


class TestJSONFormatter:
    """Tests for the JSONFormatter class."""

    def test_format_returns_valid_json(self):
        """Test that format returns valid JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)  # Should not raise
        assert isinstance(data, dict)

    def test_format_includes_required_fields(self):
        """Test that format includes all required fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)

        assert "timestamp" in data
        assert "level" in data
        assert "logger" in data
        assert "message" in data

        assert data["level"] == "INFO"
        assert data["logger"] == "test.module"
        assert data["message"] == "Test message"

    def test_format_timestamp_is_iso_format(self):
        """Test that timestamp is in ISO format with Z suffix."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)
        assert data["timestamp"].endswith("Z")
        # Should be valid ISO format (no exception)
        from datetime import datetime

        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_format_includes_exception_info(self):
        """Test that exception info is included when present."""
        formatter = JSONFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        result = formatter.format(record)
        data = json.loads(result)
        assert "exception" in data
        assert "ValueError" in data["exception"]
        assert "Test error" in data["exception"]

    def test_format_handles_message_args(self):
        """Test that message arguments are properly formatted."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Processing %s with %d events",
            args=("source1", 5),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)
        assert data["message"] == "Processing source1 with 5 events"


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def test_setup_logging_returns_logger(self):
        """Test that setup_logging returns a logger instance."""
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)

    def test_setup_logging_sets_level(self):
        """Test that setup_logging sets the correct log level."""
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG

        logger = setup_logging(level="WARNING")
        assert logger.level == logging.WARNING

    def test_setup_logging_level_case_insensitive(self):
        """Test that log level is case insensitive."""
        logger = setup_logging(level="debug")
        assert logger.level == logging.DEBUG

        logger = setup_logging(level="Warning")
        assert logger.level == logging.WARNING

    def test_setup_logging_creates_console_handler(self):
        """Test that a console handler is always created."""
        logger = setup_logging()
        handlers = logger.handlers
        assert len(handlers) >= 1
        assert any(isinstance(h, logging.StreamHandler) for h in handlers)

    def test_setup_logging_clears_existing_handlers(self):
        """Test that existing handlers are cleared on each call."""
        setup_logging()
        setup_logging()
        logger = logging.getLogger("src")
        # Should have exactly 1 console handler, not multiple
        stream_handlers = [
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
        ]
        assert len(stream_handlers) == 1

    def test_setup_logging_with_file(self):
        """Test that a file handler is created when log_file is specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir)
            logger = setup_logging(log_file="test.log", log_dir=log_path)

            # Should have both console and file handlers
            from logging.handlers import RotatingFileHandler

            file_handlers = [
                h for h in logger.handlers if isinstance(h, RotatingFileHandler)
            ]
            assert len(file_handlers) == 1

            # Log file should be created
            assert (log_path / "test.log").exists()

    def test_setup_logging_creates_log_directory(self):
        """Test that log directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs" / "nested"
            setup_logging(log_file="test.log", log_dir=log_dir)
            assert log_dir.exists()

    def test_setup_logging_with_json_format(self):
        """Test that JSON formatter is used when log_format is 'json'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir)
            logger = setup_logging(
                log_file="test.log", log_dir=log_path, log_format="json"
            )

            from logging.handlers import RotatingFileHandler

            file_handlers = [
                h for h in logger.handlers if isinstance(h, RotatingFileHandler)
            ]
            assert len(file_handlers) == 1
            assert isinstance(file_handlers[0].formatter, JSONFormatter)

    def test_setup_logging_with_text_format(self):
        """Test that standard formatter is used when log_format is 'text'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir)
            logger = setup_logging(
                log_file="test.log", log_dir=log_path, log_format="text"
            )

            from logging.handlers import RotatingFileHandler

            file_handlers = [
                h for h in logger.handlers if isinstance(h, RotatingFileHandler)
            ]
            assert len(file_handlers) == 1
            assert isinstance(file_handlers[0].formatter, logging.Formatter)
            assert not isinstance(file_handlers[0].formatter, JSONFormatter)

    def test_setup_logging_rotating_handler_config(self):
        """Test that rotating handler is configured with correct parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir)
            max_bytes = 5 * 1024 * 1024  # 5MB
            backup_count = 3

            logger = setup_logging(
                log_file="test.log",
                log_dir=log_path,
                max_bytes=max_bytes,
                backup_count=backup_count,
            )

            from logging.handlers import RotatingFileHandler

            file_handlers = [
                h for h in logger.handlers if isinstance(h, RotatingFileHandler)
            ]
            handler = file_handlers[0]
            assert handler.maxBytes == max_bytes
            assert handler.backupCount == backup_count

    def test_default_values(self):
        """Test that default values are correct."""
        assert DEFAULT_LOG_LEVEL == "INFO"
        assert DEFAULT_MAX_BYTES == 10 * 1024 * 1024
        assert DEFAULT_BACKUP_COUNT == 5


class TestGetLogger:
    """Tests for the get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_uses_provided_name(self):
        """Test that get_logger uses the provided name."""
        logger = get_logger("my.custom.module")
        assert logger.name == "my.custom.module"

    def test_get_logger_inherits_from_root(self):
        """Test that loggers inherit settings from root logger."""
        setup_logging(level="WARNING")
        logger = get_logger("src.test")
        # Child logger should inherit parent's effective level
        assert logger.getEffectiveLevel() == logging.WARNING


class TestLoggingIntegration:
    """Integration tests for the logging system."""

    def test_log_message_written_to_file(self):
        """Test that log messages are written to the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir)
            setup_logging(level="INFO", log_file="test.log", log_dir=log_path)
            logger = get_logger("src.integration_test")

            logger.info("Test message for file")

            # Flush handlers
            for handler in logging.getLogger("src").handlers:
                handler.flush()

            log_file = log_path / "test.log"
            content = log_file.read_text()
            assert "Test message for file" in content
            assert "INFO" in content

    def test_json_log_file_contains_valid_json_lines(self):
        """Test that JSON format produces valid JSON lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir)
            setup_logging(
                level="INFO", log_file="test.log", log_dir=log_path, log_format="json"
            )
            logger = get_logger("src.json_test")

            logger.info("First message")
            logger.warning("Second message")

            # Flush handlers
            for handler in logging.getLogger("src").handlers:
                handler.flush()

            log_file = log_path / "test.log"
            lines = log_file.read_text().strip().split("\n")

            # Each line should be valid JSON
            for line in lines:
                if line:
                    data = json.loads(line)
                    assert "timestamp" in data
                    assert "level" in data
                    assert "message" in data

    def test_log_levels_filter_correctly(self):
        """Test that log level filtering works correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir)
            setup_logging(level="WARNING", log_file="test.log", log_dir=log_path)
            logger = get_logger("src.filter_test")

            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

            # Flush handlers
            for handler in logging.getLogger("src").handlers:
                handler.flush()

            log_file = log_path / "test.log"
            content = log_file.read_text()

            # Debug and Info should not appear (below WARNING level)
            assert "Debug message" not in content
            assert "Info message" not in content
            # Warning and Error should appear
            assert "Warning message" in content
            assert "Error message" in content
