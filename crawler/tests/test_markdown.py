"""Tests for the markdown generator."""

import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

from src.generators.markdown import MarkdownGenerator
from src.models.event import Event


class TestMarkdownGenerator:
    """Tests for MarkdownGenerator class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def generator(self, temp_dir):
        """Create a MarkdownGenerator instance."""
        return MarkdownGenerator(output_dir=temp_dir, dry_run=False)

    @pytest.fixture
    def sample_event(self):
        """Create a sample event for testing."""
        return Event(
            name="Concert de Jazz",
            event_url="https://lafriche.org/concert-jazz",
            start_datetime=datetime(2026, 1, 26, 20, 0, tzinfo=ZoneInfo("Europe/Paris")),
            description="Un concert de jazz exceptionnel.",
            categories=["musique"],
            locations=["la-friche"],
            tags=["jazz"],
            source_id="lafriche:concert-jazz",
        )

    def test_generate_creates_file(self, generator, sample_event, temp_dir):
        """Test that generate creates a markdown file."""
        file_path = generator.generate(sample_event)

        assert file_path.exists()
        assert file_path.suffix == ".md"
        assert "2026/01/26" in str(file_path)

    def test_generate_file_path_structure(self, generator, sample_event):
        """Test that files are created in date-based folders."""
        file_path = generator.generate(sample_event)

        expected_path = generator.output_dir / "2026/01/26/concert-de-jazz.fr.md"
        assert file_path == expected_path

    def test_generate_valid_yaml_front_matter(self, generator, sample_event, temp_dir):
        """Test that generated file has valid YAML front matter."""
        file_path = generator.generate(sample_event)

        content = file_path.read_text(encoding="utf-8")

        # Should start and end with ---
        assert content.startswith("---\n")
        assert content.count("---") >= 2

        # Parse the YAML
        yaml_content = content.split("---")[1]
        front_matter = yaml.safe_load(yaml_content)

        assert front_matter["title"] == "Concert de Jazz"
        assert front_matter["name"] == "Concert de Jazz"
        assert front_matter["startTime"] == "20:00"
        assert front_matter["categories"] == ["musique"]

    def test_dry_run_no_file(self, temp_dir, sample_event):
        """Test that dry run mode doesn't create files."""
        generator = MarkdownGenerator(output_dir=temp_dir, dry_run=True)

        file_path = generator.generate(sample_event)

        assert not file_path.exists()

    def test_check_exists(self, generator, sample_event):
        """Test checking if event file exists."""
        assert not generator.check_exists(sample_event)

        generator.generate(sample_event)

        assert generator.check_exists(sample_event)

    def test_find_by_source_id(self, generator, sample_event, temp_dir):
        """Test finding files by source ID."""
        # Initially no matches
        matches = generator.find_by_source_id("lafriche:concert-jazz")
        assert len(matches) == 0

        # Generate file
        generator.generate(sample_event)

        # Now should find it
        matches = generator.find_by_source_id("lafriche:concert-jazz")
        assert len(matches) == 1

    def test_creates_parent_directories(self, temp_dir, sample_event):
        """Test that parent directories are created automatically."""
        deep_dir = temp_dir / "deep" / "nested" / "path"
        generator = MarkdownGenerator(output_dir=deep_dir)

        file_path = generator.generate(sample_event)

        assert file_path.exists()
        assert "deep/nested/path" in str(file_path)
