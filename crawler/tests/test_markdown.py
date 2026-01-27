"""Tests for the markdown generator."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
import yaml

from src.generators.markdown import GenerateResult, GeneratorStats, MarkdownGenerator
from src.models.event import Event


class TestGeneratorStats:
    """Tests for GeneratorStats dataclass."""

    def test_initial_values(self):
        stats = GeneratorStats()
        assert stats.created == 0
        assert stats.updated == 0
        assert stats.skipped_duplicate == 0
        assert stats.skipped_exists == 0
        assert stats.failed == 0

    def test_total_processed(self):
        stats = GeneratorStats(created=5, updated=2, skipped_duplicate=3, failed=1)
        assert stats.total_processed == 11

    def test_reset(self):
        stats = GeneratorStats(created=5, updated=2)
        stats.reset()
        assert stats.created == 0
        assert stats.updated == 0

    def test_to_dict(self):
        stats = GeneratorStats(created=1, updated=2, failed=3)
        d = stats.to_dict()
        assert d["created"] == 1
        assert d["updated"] == 2
        assert d["failed"] == 3


class TestGenerateResult:
    """Tests for GenerateResult dataclass."""

    def test_basic_result(self):
        result = GenerateResult(
            success=True,
            file_path=Path("/test/file.md"),
            action="created",
        )
        assert result.success is True
        assert result.action == "created"
        assert result.reason == ""

    def test_result_with_reason(self):
        result = GenerateResult(
            success=False,
            file_path=None,
            action="failed",
            reason="Permission denied",
        )
        assert result.success is False
        assert result.reason == "Permission denied"


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
            start_datetime=datetime(
                2026, 1, 26, 20, 0, tzinfo=ZoneInfo("Europe/Paris")
            ),
            description="Un concert de jazz exceptionnel.",
            categories=["musique"],
            locations=["la-friche"],
            tags=["jazz"],
            source_id="lafriche:concert-jazz",
        )

    def test_generate_creates_file(self, generator, sample_event, temp_dir):
        """Test that generate creates a markdown file."""
        result = generator.generate(sample_event)

        assert result.success is True
        assert result.action == "created"
        assert result.file_path.exists()
        assert result.file_path.suffix == ".md"
        assert "2026/01/26" in str(result.file_path)

    def test_generate_file_path_structure(self, generator, sample_event):
        """Test that files are created in date-based folders."""
        result = generator.generate(sample_event)

        expected_path = generator.output_dir / "2026/01/26/concert-de-jazz.fr.md"
        assert result.file_path == expected_path

    def test_generate_valid_yaml_front_matter(self, generator, sample_event, temp_dir):
        """Test that generated file has valid YAML front matter."""
        result = generator.generate(sample_event)

        content = result.file_path.read_text(encoding="utf-8")

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

    def test_generate_includes_body_content(self, generator, sample_event):
        """Test that description is included as body content."""
        result = generator.generate(sample_event)

        content = result.file_path.read_text(encoding="utf-8")

        # Body content should appear after front matter
        assert "Un concert de jazz exceptionnel." in content

    def test_dry_run_no_file(self, temp_dir, sample_event):
        """Test that dry run mode doesn't create files."""
        generator = MarkdownGenerator(output_dir=temp_dir, dry_run=True)

        result = generator.generate(sample_event)

        assert result.success is True
        assert result.action == "created"
        assert result.reason == "Dry run"
        assert not result.file_path.exists()

    def test_dry_run_updates_stats(self, temp_dir, sample_event):
        """Test that dry run updates statistics."""
        generator = MarkdownGenerator(output_dir=temp_dir, dry_run=True)

        generator.generate(sample_event)

        assert generator.stats.created == 1

    def test_skip_existing_file(self, generator, sample_event):
        """Test that existing files are skipped."""
        # Generate first time
        generator.generate(sample_event)
        generator.reset_stats()

        # Try to generate again
        result = generator.generate(sample_event)

        assert result.success is True
        assert result.action == "skipped"
        assert "already exists" in result.reason
        assert generator.stats.skipped_exists == 1

    def test_overwrite_when_skip_existing_false(self, temp_dir, sample_event):
        """Test that files are overwritten when skip_existing=False."""
        generator = MarkdownGenerator(
            output_dir=temp_dir, dry_run=False, skip_existing=False
        )

        # Generate first time
        generator.generate(sample_event)

        # Modify the event
        sample_event.description = "Updated description"

        # Generate again
        result = generator.generate(sample_event)

        assert result.success is True
        assert result.action == "created"

        content = result.file_path.read_text(encoding="utf-8")
        assert "Updated description" in content

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

        result = generator.generate(sample_event)

        assert result.file_path.exists()
        assert "deep/nested/path" in str(result.file_path)

    def test_stats_tracking(self, generator, sample_event):
        """Test statistics tracking."""
        assert generator.stats.created == 0

        generator.generate(sample_event)

        assert generator.stats.created == 1
        stats = generator.get_stats()
        assert stats["created"] == 1

    def test_reset_stats(self, generator, sample_event):
        """Test statistics reset."""
        generator.generate(sample_event)
        assert generator.stats.created == 1

        generator.reset_stats()

        assert generator.stats.created == 0


class TestMarkdownGeneratorBatch:
    """Tests for batch generation."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def generator(self, temp_dir):
        return MarkdownGenerator(output_dir=temp_dir, dry_run=False)

    @pytest.fixture
    def sample_events(self):
        """Create multiple sample events."""
        return [
            Event(
                name="Concert Jazz",
                event_url="https://example.com/jazz",
                start_datetime=datetime(
                    2026, 1, 26, 20, 0, tzinfo=ZoneInfo("Europe/Paris")
                ),
                categories=["musique"],
                locations=["opera"],
            ),
            Event(
                name="Exposition Art",
                event_url="https://example.com/art",
                start_datetime=datetime(
                    2026, 1, 27, 10, 0, tzinfo=ZoneInfo("Europe/Paris")
                ),
                categories=["art"],
                locations=["mucem"],
            ),
            Event(
                name="Spectacle Danse",
                event_url="https://example.com/danse",
                start_datetime=datetime(
                    2026, 1, 28, 19, 0, tzinfo=ZoneInfo("Europe/Paris")
                ),
                categories=["danse"],
                locations=["klap"],
            ),
        ]

    def test_generate_batch(self, generator, sample_events):
        """Test batch generation of multiple events."""
        results = generator.generate_batch(sample_events)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert generator.stats.created == 3

    def test_batch_with_duplicates(self, generator, sample_events, temp_dir):
        """Test batch handles existing files."""
        # Pre-create one file
        first_event = sample_events[0]
        generator.generate(first_event)
        generator.reset_stats()

        # Generate batch
        results = generator.generate_batch(sample_events)

        assert len(results) == 3
        assert generator.stats.created == 2
        assert generator.stats.skipped_exists == 1


class TestMarkdownGeneratorMultiDay:
    """Tests for multi-day event generation."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def generator(self, temp_dir):
        return MarkdownGenerator(output_dir=temp_dir, dry_run=False)

    @pytest.fixture
    def base_event(self):
        """Create a base event for multi-day generation."""
        return Event(
            name="Festival de Marseille",
            event_url="https://festival.com/2026",
            start_datetime=datetime(2026, 2, 6, 20, 0, tzinfo=ZoneInfo("Europe/Paris")),
            description="Festival pluridisciplinaire",
            categories=["communaute"],
            locations=["la-friche"],
            source_id="festival:2026",
        )

    def test_generate_multi_day_creates_files(self, generator, base_event):
        """Test that multi-day generation creates files for each day."""
        dates = [
            datetime(2026, 2, 6, tzinfo=ZoneInfo("Europe/Paris")),
            datetime(2026, 2, 7, tzinfo=ZoneInfo("Europe/Paris")),
            datetime(2026, 2, 8, tzinfo=ZoneInfo("Europe/Paris")),
        ]

        results = generator.generate_multi_day(base_event, dates)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert generator.stats.created == 3

    def test_multi_day_files_have_correct_dates(self, generator, base_event):
        """Test that each file has the correct date."""
        dates = [
            datetime(2026, 2, 6, tzinfo=ZoneInfo("Europe/Paris")),
            datetime(2026, 2, 7, tzinfo=ZoneInfo("Europe/Paris")),
        ]

        results = generator.generate_multi_day(base_event, dates)

        assert "2026/02/06" in str(results[0].file_path)
        assert "2026/02/07" in str(results[1].file_path)

    def test_multi_day_files_have_group_id(self, generator, base_event, temp_dir):
        """Test that multi-day files share eventGroupId."""
        dates = [
            datetime(2026, 2, 6, tzinfo=ZoneInfo("Europe/Paris")),
            datetime(2026, 2, 7, tzinfo=ZoneInfo("Europe/Paris")),
        ]

        results = generator.generate_multi_day(base_event, dates, group_id="test-group")

        for result in results:
            content = result.file_path.read_text()
            assert "eventGroupId: test-group" in content

    def test_multi_day_files_have_day_of(self, generator, base_event, temp_dir):
        """Test that multi-day files have dayOf field."""
        dates = [
            datetime(2026, 2, 6, tzinfo=ZoneInfo("Europe/Paris")),
            datetime(2026, 2, 7, tzinfo=ZoneInfo("Europe/Paris")),
            datetime(2026, 2, 8, tzinfo=ZoneInfo("Europe/Paris")),
        ]

        results = generator.generate_multi_day(base_event, dates)

        content1 = results[0].file_path.read_text()
        content2 = results[1].file_path.read_text()
        content3 = results[2].file_path.read_text()

        assert "Jour 1 sur 3" in content1
        assert "Jour 2 sur 3" in content2
        assert "Jour 3 sur 3" in content3

    def test_multi_day_auto_generates_group_id(self, generator, base_event, temp_dir):
        """Test that group ID is auto-generated if not provided."""
        dates = [
            datetime(2026, 2, 6, tzinfo=ZoneInfo("Europe/Paris")),
        ]

        results = generator.generate_multi_day(base_event, dates)

        content = results[0].file_path.read_text()
        assert "eventGroupId:" in content
        # Should contain slugified name
        assert "festival-de-marseille" in content.lower()

    def test_multi_day_empty_dates(self, generator, base_event):
        """Test handling of empty dates list."""
        results = generator.generate_multi_day(base_event, [])
        assert results == []


class TestMarkdownGeneratorWithDeduplicator:
    """Tests for generator with deduplicator integration."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_deduplicator(self):
        """Create a mock deduplicator."""
        return Mock()

    @pytest.fixture
    def sample_event(self):
        return Event(
            name="Concert Test",
            event_url="https://example.com/concert",
            start_datetime=datetime(
                2026, 1, 26, 20, 0, tzinfo=ZoneInfo("Europe/Paris")
            ),
            categories=["musique"],
        )

    def test_skips_duplicate_event(self, temp_dir, mock_deduplicator, sample_event):
        """Test that duplicate events are skipped."""
        # Mock duplicate result
        mock_dup_result = Mock()
        mock_dup_result.is_duplicate = True
        mock_dup_result.should_merge = False
        mock_dup_result.existing_file = Path("/existing/file.md")
        mock_dup_result.match_reasons = ["Same booking URL"]

        mock_deduplicator.check_duplicate.return_value = mock_dup_result

        generator = MarkdownGenerator(
            output_dir=temp_dir, deduplicator=mock_deduplicator
        )

        result = generator.generate(sample_event)

        assert result.success is True
        assert result.action == "skipped"
        assert "Duplicate" in result.reason
        assert generator.stats.skipped_duplicate == 1

    def test_merges_duplicate_event(self, temp_dir, mock_deduplicator, sample_event):
        """Test that duplicate events are merged when should_merge=True."""
        # Mock duplicate result with merge
        mock_dup_result = Mock()
        mock_dup_result.is_duplicate = True
        mock_dup_result.should_merge = True
        mock_dup_result.existing_file = Path("/existing/file.md")
        mock_dup_result.match_reasons = ["Same booking URL"]

        mock_merge_result = Mock()
        mock_merge_result.updated = True

        mock_deduplicator.check_duplicate.return_value = mock_dup_result
        mock_deduplicator.merge_event.return_value = mock_merge_result

        generator = MarkdownGenerator(
            output_dir=temp_dir, deduplicator=mock_deduplicator
        )

        result = generator.generate(sample_event)

        assert result.success is True
        assert result.action == "updated"
        assert generator.stats.updated == 1
        mock_deduplicator.merge_event.assert_called_once()

    def test_creates_new_when_not_duplicate(
        self, temp_dir, mock_deduplicator, sample_event
    ):
        """Test that new events are created when not duplicate."""
        # Mock not duplicate
        mock_dup_result = Mock()
        mock_dup_result.is_duplicate = False

        mock_deduplicator.check_duplicate.return_value = mock_dup_result

        generator = MarkdownGenerator(
            output_dir=temp_dir, deduplicator=mock_deduplicator
        )

        result = generator.generate(sample_event)

        assert result.success is True
        assert result.action == "created"
        assert generator.stats.created == 1

    def test_skip_duplicate_check(self, temp_dir, mock_deduplicator, sample_event):
        """Test that duplicate check can be skipped."""
        generator = MarkdownGenerator(
            output_dir=temp_dir, deduplicator=mock_deduplicator
        )

        result = generator.generate(sample_event, check_duplicate=False)

        assert result.success is True
        assert result.action == "created"
        mock_deduplicator.check_duplicate.assert_not_called()


class TestMarkdownGeneratorFrenchDates:
    """Tests for French date formatting in generated files."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def generator(self, temp_dir):
        return MarkdownGenerator(output_dir=temp_dir)

    def test_french_date_in_dates_taxonomy(self, generator):
        """Test that dates taxonomy uses French format."""
        event = Event(
            name="Test Event",
            event_url="https://example.com",
            start_datetime=datetime(
                2026, 1, 26, 20, 0, tzinfo=ZoneInfo("Europe/Paris")
            ),
            categories=["test"],
        )

        result = generator.generate(event)
        content = result.file_path.read_text()

        # Check for French date format: lundi-26-janvier
        assert "lundi-26-janvier" in content

    def test_various_french_days(self, generator):
        """Test French day names for different weekdays."""
        # Tuesday
        event = Event(
            name="Tuesday Event",
            event_url="https://example.com/tue",
            start_datetime=datetime(
                2026, 1, 27, 20, 0, tzinfo=ZoneInfo("Europe/Paris")
            ),
            categories=["test"],
        )
        result = generator.generate(event)
        content = result.file_path.read_text()
        assert "mardi-27-janvier" in content

        # Saturday
        event2 = Event(
            name="Saturday Event",
            event_url="https://example.com/sat",
            start_datetime=datetime(
                2026, 1, 31, 20, 0, tzinfo=ZoneInfo("Europe/Paris")
            ),
            categories=["test"],
        )
        result2 = generator.generate(event2)
        content2 = result2.file_path.read_text()
        assert "samedi-31-janvier" in content2
