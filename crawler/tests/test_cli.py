"""Tests for the command-line interface."""

import tempfile
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from crawl import (
    cli,
    load_config,
    load_status,
    save_status,
    setup_logging_from_config,
)


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory with config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create config.yaml
        config = {
            "sources_file": "config/sources.yaml",
            "output_dir": "content/events",
            "image_dir": "static/images/events",
            "logging": {
                "log_level": "INFO",
            },
            "http": {
                "timeout": 30,
            },
        }
        config_path = tmpdir / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Create config directory
        config_dir = tmpdir / "config"
        config_dir.mkdir()

        # Create sources.yaml
        sources = {
            "sources": [
                {
                    "name": "Test Source",
                    "id": "test-source",
                    "url": "https://example.com/events",
                    "parser": "generic",
                    "enabled": True,
                }
            ]
        }
        with open(config_dir / "sources.yaml", "w") as f:
            yaml.dump(sources, f)

        # Create selection-criteria.yaml
        selection = {
            "geography": {"required_areas": ["Marseille"]},
        }
        with open(config_dir / "selection-criteria.yaml", "w") as f:
            yaml.dump(selection, f)

        # Create output directory
        (tmpdir / "content" / "events").mkdir(parents=True)

        yield tmpdir


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, temp_config_dir):
        """Test loading a valid config file."""
        config_path = temp_config_dir / "config.yaml"
        config = load_config(config_path)
        assert config["sources_file"] == "config/sources.yaml"
        assert config["output_dir"] == "content/events"

    def test_load_nonexistent_config(self):
        """Test loading a nonexistent config file."""
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/config.yaml"))


class TestStatusFunctions:
    """Tests for status save/load functions."""

    def test_save_and_load_status(self, temp_config_dir):
        """Test saving and loading status."""
        status = {
            "sources_processed": 3,
            "sources_total": 5,
            "events_accepted": 42,
            "events_rejected": 10,
            "errors": 1,
            "dry_run": False,
            "interrupted": False,
        }
        save_status(temp_config_dir, status)

        loaded = load_status(temp_config_dir)
        assert loaded["sources_processed"] == 3
        assert loaded["events_accepted"] == 42
        assert "timestamp" in loaded

    def test_load_missing_status(self, temp_config_dir):
        """Test loading status when file doesn't exist."""
        result = load_status(temp_config_dir)
        assert result is None


class TestCliGroup:
    """Tests for the main CLI group."""

    def test_cli_shows_help_without_command(self, runner, temp_config_dir):
        """Test that CLI shows help when no command is given."""
        result = runner.invoke(cli, ["-c", str(temp_config_dir / "config.yaml")])
        assert result.exit_code == 0
        assert "Massalia Events Crawler" in result.output
        assert "Commands:" in result.output

    def test_cli_version(self, runner, temp_config_dir):
        """Test --version flag."""
        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "--version"]
        )
        assert result.exit_code == 0
        assert "massalia-crawler" in result.output
        assert "1.0.0" in result.output

    def test_cli_help(self, runner, temp_config_dir):
        """Test --help flag."""
        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "--help"]
        )
        assert result.exit_code == 0
        assert "Commands:" in result.output
        assert "run" in result.output
        assert "list-sources" in result.output
        assert "validate" in result.output
        assert "status" in result.output
        assert "clean" in result.output


class TestListSourcesCommand:
    """Tests for the list-sources command."""

    def test_list_sources(self, runner, temp_config_dir):
        """Test list-sources command output."""
        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "list-sources"]
        )
        assert result.exit_code == 0
        assert "Configured sources:" in result.output
        assert "test-source" in result.output
        assert "Test Source" in result.output
        assert "generic" in result.output
        assert "enabled" in result.output


class TestValidateCommand:
    """Tests for the validate command."""

    def test_validate_valid_config(self, runner, temp_config_dir):
        """Test validate command with valid config."""
        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "validate"]
        )
        # May have warnings but should pass
        assert "Validating configuration files..." in result.output
        assert "config.yaml is valid" in result.output

    def test_validate_missing_sources_file(self, runner, temp_config_dir):
        """Test validate when sources file is missing."""
        # Remove sources file
        (temp_config_dir / "config" / "sources.yaml").unlink()

        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "validate"]
        )
        assert result.exit_code == 1
        assert "VALIDATION FAILED" in result.output


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_no_previous_run(self, runner, temp_config_dir):
        """Test status command when no previous crawl."""
        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "status"]
        )
        assert result.exit_code == 0
        assert "No previous crawl status found" in result.output

    def test_status_with_previous_run(self, runner, temp_config_dir):
        """Test status command after a crawl."""
        # Save status
        status = {
            "sources_processed": 2,
            "sources_total": 3,
            "events_accepted": 15,
            "events_rejected": 5,
            "errors": 0,
            "dry_run": False,
            "interrupted": False,
        }
        save_status(temp_config_dir, status)

        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "status"]
        )
        assert result.exit_code == 0
        assert "LAST CRAWL STATUS" in result.output
        assert "Sources processed:  2/3" in result.output
        assert "Events accepted:    15" in result.output
        assert "SUCCESS" in result.output

    def test_status_with_errors(self, runner, temp_config_dir):
        """Test status command shows errors correctly."""
        status = {
            "sources_processed": 2,
            "sources_total": 3,
            "events_accepted": 10,
            "events_rejected": 0,
            "errors": 2,
            "dry_run": False,
            "interrupted": False,
        }
        save_status(temp_config_dir, status)

        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "status"]
        )
        assert result.exit_code == 0
        assert "COMPLETED WITH ERRORS" in result.output


class TestCleanCommand:
    """Tests for the clean command."""

    def test_clean_dry_run(self, runner, temp_config_dir):
        """Test clean command with --dry-run."""
        # Create an old event file
        events_dir = temp_config_dir / "content" / "events" / "2020" / "01" / "01"
        events_dir.mkdir(parents=True)
        event_file = events_dir / "old-event.md"

        front_matter = {
            "title": "Old Event",
            "date": "2020-01-01T10:00:00+01:00",
            "name": "Old Event",
            "expired": False,
        }
        content = "---\n" + yaml.dump(front_matter) + "---\n\nEvent description"
        event_file.write_text(content)

        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "clean", "--dry-run"]
        )
        assert result.exit_code == 0
        assert "DRY RUN MODE" in result.output
        assert (
            "old-event.md" in result.output
            or "Would have marked expired: 1" in result.output
        )

        # File should still exist and not be modified
        assert event_file.exists()
        content = event_file.read_text()
        assert "expired: false" in content.lower() or "expired: False" in content

    def test_clean_marks_expired(self, runner, temp_config_dir):
        """Test clean command marks events as expired."""
        # Create an old event file
        events_dir = temp_config_dir / "content" / "events" / "2020" / "01" / "01"
        events_dir.mkdir(parents=True)
        event_file = events_dir / "old-event.md"

        front_matter = {
            "title": "Old Event",
            "date": "2020-01-01T10:00:00+01:00",
            "name": "Old Event",
            "expired": False,
        }
        content = "---\n" + yaml.dump(front_matter) + "---\n\nEvent description"
        event_file.write_text(content)

        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "clean"]
        )
        assert result.exit_code == 0
        assert (
            "Marked expired:" in result.output
            or "Events marked expired: 1" in result.output
        )

        # Check file was modified
        content = event_file.read_text()
        assert "expired: true" in content.lower()

    def test_clean_delete(self, runner, temp_config_dir):
        """Test clean command with --delete flag."""
        # Create an old event file
        events_dir = temp_config_dir / "content" / "events" / "2020" / "01" / "01"
        events_dir.mkdir(parents=True)
        event_file = events_dir / "old-event.md"

        front_matter = {
            "title": "Old Event",
            "date": "2020-01-01T10:00:00+01:00",
            "name": "Old Event",
            "expired": False,
        }
        content = "---\n" + yaml.dump(front_matter) + "---\n\nEvent description"
        event_file.write_text(content)

        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "clean", "--delete"]
        )
        assert result.exit_code == 0

        # File should be deleted
        assert not event_file.exists()

    def test_clean_before_date(self, runner, temp_config_dir):
        """Test clean command with --before flag."""
        # Create events at different dates
        for year, month, day in [(2020, 1, 1), (2025, 6, 15)]:
            events_dir = (
                temp_config_dir
                / "content"
                / "events"
                / str(year)
                / f"{month:02d}"
                / f"{day:02d}"
            )
            events_dir.mkdir(parents=True)
            event_file = events_dir / f"event-{year}.md"

            front_matter = {
                "title": f"Event {year}",
                "date": f"{year}-{month:02d}-{day:02d}T10:00:00+01:00",
                "name": f"Event {year}",
                "expired": False,
            }
            content = "---\n" + yaml.dump(front_matter) + "---\n\nEvent description"
            event_file.write_text(content)

        result = runner.invoke(
            cli,
            [
                "-c",
                str(temp_config_dir / "config.yaml"),
                "clean",
                "--before",
                "2025-01-01",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        # Only 2020 event should be cleaned
        assert (
            "event-2020.md" in result.output
            or "Would have marked expired: 1" in result.output
        )


class TestRunCommand:
    """Tests for the run command."""

    def test_run_help(self, runner, temp_config_dir):
        """Test run command help."""
        result = runner.invoke(
            cli, ["-c", str(temp_config_dir / "config.yaml"), "run", "--help"]
        )
        assert result.exit_code == 0
        assert "--source" in result.output
        assert "--dry-run" in result.output
        assert "--skip-selection" in result.output

    def test_run_source_not_found(self, runner, temp_config_dir):
        """Test run with nonexistent source."""
        result = runner.invoke(
            cli,
            [
                "-c",
                str(temp_config_dir / "config.yaml"),
                "run",
                "--source",
                "nonexistent",
            ],
        )
        assert result.exit_code == 1
        assert (
            "No source found" in result.output or "not found" in result.output.lower()
        )


class TestSetupLoggingFromConfig:
    """Tests for setup_logging_from_config function."""

    def test_setup_logging_defaults(self, temp_config_dir):
        """Test logging setup with defaults."""
        config = {"logging": {"log_level": "INFO"}}
        # Should not raise
        setup_logging_from_config(config, temp_config_dir)

    def test_setup_logging_override(self, temp_config_dir):
        """Test logging setup with CLI override."""
        config = {"logging": {"log_level": "INFO"}}
        # Should not raise
        setup_logging_from_config(config, temp_config_dir, log_level_override="DEBUG")

    def test_setup_logging_backwards_compatibility(self, temp_config_dir):
        """Test logging setup with old flat config format."""
        config = {"log_level": "WARNING"}  # Old format
        # Should not raise
        setup_logging_from_config(config, temp_config_dir)
