"""Tests for event deduplicator module."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.deduplicator import DuplicateResult, EventDeduplicator
from src.models.event import Event


class TestDuplicateResult:
    """Tests for DuplicateResult dataclass."""

    def test_basic_result(self):
        result = DuplicateResult(
            is_duplicate=True,
            confidence=0.95,
            existing_file=Path("/content/events/test.md"),
            match_reasons=["Matching booking URL"],
            should_merge=True,
        )
        assert result.is_duplicate is True
        assert result.confidence == 0.95
        assert result.should_merge is True

    def test_near_duplicate_threshold(self):
        """Test near-duplicate detection at boundary."""
        result_near = DuplicateResult(
            is_duplicate=False,
            confidence=0.6,
            existing_file=None,
            match_reasons=["Similar name"],
            should_merge=False,
        )
        result_not_near = DuplicateResult(
            is_duplicate=False,
            confidence=0.4,
            existing_file=None,
            match_reasons=[],
            should_merge=False,
        )
        assert result_near.is_near_duplicate is True
        assert result_not_near.is_near_duplicate is False

    def test_near_duplicate_not_when_duplicate(self):
        """Near-duplicate should be False when it's a full duplicate."""
        result = DuplicateResult(
            is_duplicate=True,
            confidence=0.85,
            existing_file=Path("/test.md"),
            match_reasons=["Match"],
            should_merge=True,
        )
        assert result.is_near_duplicate is False


class TestEventDeduplicatorIndex:
    """Tests for event index building."""

    @pytest.fixture
    def temp_content_dir(self):
        """Create temporary content directory with test events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir) / "events"
            content_dir.mkdir(parents=True)

            # Create test event file
            event_file = content_dir / "2026" / "01" / "27" / "test-event.fr.md"
            event_file.parent.mkdir(parents=True)
            event_file.write_text(
                """---
title: "Concert Jazz à l'Opéra"
date: 2026-01-27T20:00:00+01:00
name: "Concert Jazz à l'Opéra"
eventURL: "https://opera-marseille.com/concert-jazz"
startTime: "20:00"
description: "Un concert de jazz exceptionnel"
categories:
  - "musique"
locations:
  - "opera-de-marseille"
sourceId: "opera:jazz2026"
---
Content here
"""
            )

            # Create another event
            event_file2 = content_dir / "2026" / "01" / "28" / "exposition.fr.md"
            event_file2.parent.mkdir(parents=True)
            event_file2.write_text(
                """---
title: "Exposition Art Moderne"
date: 2026-01-28T10:00:00+01:00
name: "Exposition Art Moderne"
eventURL: "https://mucem.org/expo"
startTime: "10:00"
categories:
  - "art"
locations:
  - "mucem"
sourceId: "mucem:expo2026"
---
Content here
"""
            )

            yield content_dir

    def test_build_index_from_directory(self, temp_content_dir):
        """Test that index is built from event files."""
        dedup = EventDeduplicator(temp_content_dir)
        stats = dedup.get_stats()

        assert stats["total_urls"] == 2
        assert stats["total_date_locations"] == 2
        assert stats["total_names"] >= 2

    def test_index_by_url(self, temp_content_dir):
        """Test URL index lookup."""
        dedup = EventDeduplicator(temp_content_dir)

        # Check normalized URL is indexed
        assert "opera-marseille.com/concert-jazz" in dedup.event_index["by_url"]

    def test_index_by_date_location(self, temp_content_dir):
        """Test date/location index lookup."""
        dedup = EventDeduplicator(temp_content_dir)

        # Check date+time+location key (location is normalized - hyphens removed)
        key = "2026-01-27|20:00|operademarseille"
        assert key in dedup.event_index["by_date_location"]

    def test_empty_directory(self):
        """Test handling of empty content directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir) / "events"
            content_dir.mkdir()

            dedup = EventDeduplicator(content_dir)
            stats = dedup.get_stats()

            assert stats["total_urls"] == 0

    def test_nonexistent_directory(self):
        """Test handling of nonexistent directory."""
        dedup = EventDeduplicator("/nonexistent/path")
        stats = dedup.get_stats()

        assert stats["total_urls"] == 0


class TestDuplicateDetectionByURL:
    """Tests for URL-based duplicate detection."""

    @pytest.fixture
    def dedup_with_events(self):
        """Create deduplicator with indexed events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir) / "events"
            content_dir.mkdir(parents=True)

            event_file = content_dir / "2026" / "01" / "27" / "jazz.fr.md"
            event_file.parent.mkdir(parents=True)
            event_file.write_text(
                """---
title: "Concert Jazz"
date: 2026-01-27T20:00:00+01:00
name: "Concert Jazz"
eventURL: "https://www.example.com/event/123"
startTime: "20:00"
locations:
  - "opera"
---
"""
            )

            dedup = EventDeduplicator(content_dir)
            yield dedup

    def test_exact_url_match(self, dedup_with_events):
        """Test detection with exact URL match."""
        event = Event(
            name="Concert Jazz Différent",
            event_url="https://www.example.com/event/123",
            start_datetime=datetime(2026, 1, 27, 20, 0),
        )

        result = dedup_with_events.check_duplicate(event)

        assert result.is_duplicate is True
        assert result.confidence >= 0.9
        assert "Matching booking URL" in result.match_reasons[0]
        assert result.should_merge is True

    def test_url_with_different_protocol(self, dedup_with_events):
        """Test URL matching ignores protocol."""
        event = Event(
            name="Concert",
            event_url="http://www.example.com/event/123",  # http instead of https
            start_datetime=datetime(2026, 1, 27, 20, 0),
        )

        result = dedup_with_events.check_duplicate(event)
        assert result.is_duplicate is True

    def test_url_without_www(self, dedup_with_events):
        """Test URL matching ignores www prefix."""
        event = Event(
            name="Concert",
            event_url="https://example.com/event/123",  # no www
            start_datetime=datetime(2026, 1, 27, 20, 0),
        )

        result = dedup_with_events.check_duplicate(event)
        assert result.is_duplicate is True

    def test_url_with_trailing_slash(self, dedup_with_events):
        """Test URL matching ignores trailing slash."""
        event = Event(
            name="Concert",
            event_url="https://www.example.com/event/123/",  # trailing slash
            start_datetime=datetime(2026, 1, 27, 20, 0),
        )

        result = dedup_with_events.check_duplicate(event)
        assert result.is_duplicate is True

    def test_different_url_no_match(self, dedup_with_events):
        """Test no match with different URL and different name."""
        event = Event(
            name="Exposition Peinture",  # Completely different name
            event_url="https://www.different.com/event/456",
            start_datetime=datetime(2026, 1, 27, 20, 0),
            locations=["different-venue"],
        )

        result = dedup_with_events.check_duplicate(event)
        assert result.is_duplicate is False


class TestDuplicateDetectionByDateLocation:
    """Tests for date/time/location-based duplicate detection."""

    @pytest.fixture
    def dedup_with_events(self):
        """Create deduplicator with indexed events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir) / "events"
            content_dir.mkdir(parents=True)

            event_file = content_dir / "2026" / "02" / "15" / "danse.fr.md"
            event_file.parent.mkdir(parents=True)
            event_file.write_text(
                """---
title: "Spectacle de Danse Contemporaine"
date: 2026-02-15T19:30:00+01:00
name: "Spectacle de Danse Contemporaine"
eventURL: "https://klap.org/spectacle"
startTime: "19:30"
locations:
  - "klap"
---
"""
            )

            dedup = EventDeduplicator(content_dir)
            yield dedup

    def test_same_date_time_location_similar_name(self, dedup_with_events):
        """Test detection with same date/time/location and similar name."""
        event = Event(
            name="Spectacle Danse Contemporaine",  # Similar but not identical
            event_url="https://other-site.com/danse",
            start_datetime=datetime(2026, 2, 15, 19, 30),
            locations=["klap"],
        )

        result = dedup_with_events.check_duplicate(event)

        assert result.is_duplicate is True
        assert result.confidence >= 0.8
        assert any("date/time/location" in r.lower() for r in result.match_reasons)

    def test_same_date_time_location_different_name(self, dedup_with_events):
        """Test near-duplicate with same date/time/location but different name."""
        event = Event(
            name="Concert Rock",  # Completely different
            event_url="https://other-site.com/rock",
            start_datetime=datetime(2026, 2, 15, 19, 30),
            locations=["klap"],
        )

        result = dedup_with_events.check_duplicate(event)

        # Should be flagged but not as confident
        assert result.confidence < 0.7 or result.is_near_duplicate

    def test_different_time_no_match(self, dedup_with_events):
        """Test no match with different time and different name."""
        event = Event(
            name="Atelier Cuisine",  # Completely different name
            event_url="https://other-site.com/cuisine",
            start_datetime=datetime(2026, 2, 15, 14, 0),  # Different time
            locations=["klap"],
        )

        result = dedup_with_events.check_duplicate(event)
        assert result.is_duplicate is False

    def test_different_location_no_match(self, dedup_with_events):
        """Test no match with different location and different name."""
        event = Event(
            name="Concert Rock",  # Completely different name
            event_url="https://other-site.com/rock",
            start_datetime=datetime(2026, 2, 15, 19, 30),
            locations=["la-criee"],  # Different venue
        )

        result = dedup_with_events.check_duplicate(event)
        assert result.is_duplicate is False


class TestDuplicateDetectionByName:
    """Tests for name-based duplicate detection."""

    @pytest.fixture
    def dedup_with_events(self):
        """Create deduplicator with indexed events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir) / "events"
            content_dir.mkdir(parents=True)

            event_file = content_dir / "2026" / "03" / "10" / "theatre.fr.md"
            event_file.parent.mkdir(parents=True)
            event_file.write_text(
                """---
title: "Le Malade Imaginaire de Molière"
date: 2026-03-10T20:00:00+01:00
name: "Le Malade Imaginaire de Molière"
eventURL: "https://theatre.com/moliere"
startTime: "20:00"
locations:
  - "la-criee"
---
"""
            )

            dedup = EventDeduplicator(content_dir)
            yield dedup

    def test_very_similar_name_same_date(self, dedup_with_events):
        """Test detection with exact same normalized name on same date."""
        event = Event(
            name="Le Malade Imaginaire de Molière",  # Exact same name
            event_url="https://other-theatre.com/malade",
            start_datetime=datetime(2026, 3, 10, 21, 0),  # Different time
            locations=["another-venue"],
        )

        result = dedup_with_events.check_duplicate(event)

        assert result.is_duplicate is True
        assert result.confidence >= 0.7
        assert any("similar name" in r.lower() for r in result.match_reasons)

    def test_similar_name_different_date(self, dedup_with_events):
        """Test no match with similar name but different date."""
        event = Event(
            name="Le Malade Imaginaire de Molière",
            event_url="https://other-theatre.com/malade",
            start_datetime=datetime(2026, 4, 15, 20, 0),  # Different date
            locations=["la-criee"],
        )

        result = dedup_with_events.check_duplicate(event)
        assert result.is_duplicate is False


class TestNameSimilarity:
    """Tests for name similarity calculation."""

    @pytest.fixture
    def dedup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir) / "events"
            content_dir.mkdir()
            yield EventDeduplicator(content_dir)

    def test_identical_names(self, dedup):
        """Test similarity of identical names."""
        sim = dedup._name_similarity("Concert Jazz", "Concert Jazz")
        assert sim == 1.0

    def test_case_insensitive(self, dedup):
        """Test case-insensitive comparison."""
        sim = dedup._name_similarity("Concert Jazz", "CONCERT JAZZ")
        assert sim == 1.0

    def test_minor_differences(self, dedup):
        """Test high similarity with minor differences."""
        sim = dedup._name_similarity(
            "Concert de Jazz à Marseille", "Concert Jazz Marseille"
        )
        assert sim > 0.7

    def test_completely_different(self, dedup):
        """Test low similarity with different names."""
        sim = dedup._name_similarity("Concert Rock", "Exposition Peinture")
        assert sim < 0.3

    def test_punctuation_ignored(self, dedup):
        """Test that punctuation is ignored."""
        sim = dedup._name_similarity("L'Opéra de Paris", "L Opera de Paris")
        assert sim > 0.9


class TestURLNormalization:
    """Tests for URL normalization."""

    @pytest.fixture
    def dedup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir) / "events"
            content_dir.mkdir()
            yield EventDeduplicator(content_dir)

    def test_remove_protocol(self, dedup):
        """Test protocol removal."""
        assert dedup._normalize_url("https://example.com") == "example.com"
        assert dedup._normalize_url("http://example.com") == "example.com"

    def test_remove_www(self, dedup):
        """Test www removal."""
        assert dedup._normalize_url("https://www.example.com") == "example.com"

    def test_remove_trailing_slash(self, dedup):
        """Test trailing slash removal."""
        assert dedup._normalize_url("https://example.com/path/") == "example.com/path"

    def test_remove_tracking_params(self, dedup):
        """Test removal of tracking parameters."""
        assert (
            dedup._normalize_url("https://example.com/event?utm_source=google")
            == "example.com/event"
        )
        assert (
            dedup._normalize_url("https://example.com/event?ref=facebook")
            == "example.com/event"
        )

    def test_lowercase(self, dedup):
        """Test lowercase conversion."""
        assert dedup._normalize_url("HTTPS://EXAMPLE.COM/PATH") == "example.com/path"


class TestMergeEvent:
    """Tests for event merging functionality."""

    @pytest.fixture
    def temp_event_file(self):
        """Create temporary event file for merge testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            event_file = Path(tmpdir) / "test-event.fr.md"
            event_file.write_text(
                """---
title: "Concert Original"
date: 2026-01-27T20:00:00+01:00
name: "Concert Original"
eventURL: "https://original.com/event"
startTime: "20:00"
description: ""
locations:
  - "opera"
sourceId: "original:123"
---
Original content
"""
            )
            yield event_file

    @pytest.fixture
    def dedup(self, temp_event_file):
        """Create deduplicator instance."""
        content_dir = temp_event_file.parent
        return EventDeduplicator(content_dir)

    def test_merge_adds_description(self, dedup, temp_event_file):
        """Test merging adds missing description."""
        new_event = Event(
            name="Concert Original",
            event_url="https://alternate.com/event",
            start_datetime=datetime(2026, 1, 27, 20, 0),
            description="A wonderful jazz concert",
        )

        result = dedup.merge_event(temp_event_file, new_event)

        assert result.updated is True
        assert any("description" in c.lower() for c in result.changes)

        # Verify file was updated
        import frontmatter

        post = frontmatter.load(temp_event_file)
        assert post["description"] == "A wonderful jazz concert"

    def test_merge_adds_image(self, temp_event_file):
        """Test merging adds missing image."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir)
            content_dir.mkdir(exist_ok=True)

            # Create event without image
            event_file = content_dir / "event.md"
            event_file.write_text(
                """---
title: "Event"
date: 2026-01-27T20:00:00+01:00
name: "Event"
eventURL: "https://example.com"
startTime: "20:00"
---
"""
            )

            dedup = EventDeduplicator(content_dir)

            new_event = Event(
                name="Event",
                event_url="https://other.com",
                start_datetime=datetime(2026, 1, 27, 20, 0),
                image="/images/new-image.webp",
            )

            result = dedup.merge_event(event_file, new_event)

            assert result.updated is True
            assert any("image" in c.lower() for c in result.changes)

    def test_merge_adds_alternate_source(self, dedup, temp_event_file):
        """Test merging tracks alternate source URLs."""
        new_event = Event(
            name="Concert Original",
            event_url="https://alternate.com/event",
            start_datetime=datetime(2026, 1, 27, 20, 0),
        )

        result = dedup.merge_event(temp_event_file, new_event)

        assert result.updated is True
        assert any("alternate source" in c.lower() for c in result.changes)

        import frontmatter

        post = frontmatter.load(temp_event_file)
        assert "https://alternate.com/event" in post.get("alternateSources", [])

    def test_merge_no_changes_when_complete(self):
        """Test no merge when existing event is complete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            event_file = Path(tmpdir) / "complete.md"
            event_file.write_text(
                """---
title: "Complete Event"
date: 2026-01-27T20:00:00+01:00
name: "Complete Event"
eventURL: "https://example.com/event"
startTime: "20:00"
description: "Already has description"
image: "/images/already-has-image.webp"
---
"""
            )

            dedup = EventDeduplicator(tmpdir)

            new_event = Event(
                name="Complete Event",
                event_url="https://example.com/event",  # Same URL
                start_datetime=datetime(2026, 1, 27, 20, 0),
                description="Different description",
                image="/images/different.webp",
            )

            result = dedup.merge_event(event_file, new_event)

            # No changes because same URL and fields already filled
            assert result.updated is False


class TestRefreshIndex:
    """Tests for index refresh functionality."""

    def test_refresh_adds_new_events(self):
        """Test that refresh picks up new events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir) / "events"
            content_dir.mkdir()

            # Create initial event
            event1 = content_dir / "event1.md"
            event1.write_text(
                """---
title: "Event 1"
date: 2026-01-27T20:00:00+01:00
name: "Event 1"
eventURL: "https://example.com/1"
startTime: "20:00"
locations:
  - "venue"
---
"""
            )

            dedup = EventDeduplicator(content_dir)
            assert dedup.get_stats()["total_urls"] == 1

            # Add new event
            event2 = content_dir / "event2.md"
            event2.write_text(
                """---
title: "Event 2"
date: 2026-01-28T20:00:00+01:00
name: "Event 2"
eventURL: "https://example.com/2"
startTime: "20:00"
locations:
  - "venue"
---
"""
            )

            dedup.refresh_index()
            assert dedup.get_stats()["total_urls"] == 2


class TestRealWorldScenarios:
    """Tests with realistic duplicate scenarios."""

    @pytest.fixture
    def realistic_content_dir(self):
        """Create content directory with realistic event data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_dir = Path(tmpdir) / "events"
            (content_dir / "2026" / "01").mkdir(parents=True)

            # Event from source A
            (content_dir / "2026" / "01" / "concert-jazz.fr.md").write_text(
                """---
title: "Soirée Jazz - Trio Méditerranée"
date: 2026-01-30T20:30:00+01:00
name: "Soirée Jazz - Trio Méditerranée"
eventURL: "https://opera-marseille.com/spectacles/jazz-trio"
startTime: "20:30"
description: ""
locations:
  - "opera-de-marseille"
sourceId: "opera:jazz-trio-2026"
---
"""
            )

            # Theatre show
            (content_dir / "2026" / "01" / "theatre-moliere.fr.md").write_text(
                """---
title: "Le Bourgeois Gentilhomme"
date: 2026-01-30T19:00:00+01:00
name: "Le Bourgeois Gentilhomme"
eventURL: "https://theatre-lacriee.com/bourgeois"
startTime: "19:00"
description: "Comédie-ballet de Molière"
locations:
  - "la-criee"
sourceId: "criee:bourgeois-2026"
---
"""
            )

            yield content_dir

    def test_same_event_different_sources(self, realistic_content_dir):
        """Test detecting same event from different source websites."""
        dedup = EventDeduplicator(realistic_content_dir)

        # Same concert from different website
        event = Event(
            name="Soirée Jazz Trio Méditerranée",  # Slightly different formatting
            event_url="https://marseillejazz.com/events/trio-mediterranee",
            start_datetime=datetime(2026, 1, 30, 20, 30),
            locations=["opera-de-marseille"],
            description="Concert de jazz avec le Trio Méditerranée",
        )

        result = dedup.check_duplicate(event)

        # Should detect as duplicate based on date/time/location + similar name
        assert result.is_duplicate is True
        assert result.confidence >= 0.7

    def test_different_events_same_venue_date(self, realistic_content_dir):
        """Test distinguishing different events at same venue on same date."""
        dedup = EventDeduplicator(realistic_content_dir)

        # Different show at same venue, same date, different time
        event = Event(
            name="Atelier Théâtre Jeune Public",
            event_url="https://theatre-lacriee.com/atelier",
            start_datetime=datetime(2026, 1, 30, 14, 0),  # Different time
            locations=["la-criee"],
        )

        result = dedup.check_duplicate(event)

        # Should NOT be detected as duplicate
        assert result.is_duplicate is False

    def test_multi_day_festival_events(self, realistic_content_dir):
        """Test handling of multi-day festival with different daily events."""
        # Add festival day 1
        (realistic_content_dir / "2026" / "01" / "festival-jour1.fr.md").write_text(
            """---
title: "Festival Marseille - Jour 1"
date: 2026-01-31T18:00:00+01:00
name: "Festival Marseille"
eventURL: "https://festival.com/jour1"
startTime: "18:00"
locations:
  - "la-friche"
eventGroupId: "festival-2026"
dayOf: "Jour 1 sur 2"
---
"""
        )

        dedup = EventDeduplicator(realistic_content_dir)

        # Day 2 of same festival - should NOT be duplicate
        event = Event(
            name="Festival Marseille",
            event_url="https://festival.com/jour2",
            start_datetime=datetime(2026, 2, 1, 18, 0),  # Next day
            locations=["la-friche"],
            event_group_id="festival-2026",
            day_of="Jour 2 sur 2",
        )

        result = dedup.check_duplicate(event)

        # Different date means not a duplicate
        assert result.is_duplicate is False
