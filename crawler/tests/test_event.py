"""Tests for the Event data model."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event, format_french_date, slugify


class TestSlugify:
    """Tests for slugify function."""

    def test_basic_text(self):
        assert slugify("Hello World") == "hello-world"

    def test_french_accents(self):
        assert slugify("Événement à Marseille") == "evenement-a-marseille"
        assert slugify("Château de Servières") == "chateau-de-servieres"
        assert slugify("Noël en fête") == "noel-en-fete"

    def test_special_characters(self):
        assert slugify("Event #1 - 2026!") == "event-1-2026"
        assert slugify("Concert @ La Friche") == "concert-la-friche"

    def test_multiple_spaces(self):
        assert slugify("Hello   World") == "hello-world"

    def test_leading_trailing(self):
        assert slugify("  Hello  ") == "hello"
        assert slugify("--hello--") == "hello"


class TestFormatFrenchDate:
    """Tests for French date formatting."""

    def test_monday(self):
        dt = datetime(2026, 1, 26, 19, 0)  # Monday
        assert format_french_date(dt) == "lundi-26-janvier"

    def test_saturday(self):
        dt = datetime(2026, 2, 7, 20, 0)  # Saturday
        assert format_french_date(dt) == "samedi-07-fevrier"

    def test_december(self):
        dt = datetime(2026, 12, 25, 20, 0)  # Friday
        assert format_french_date(dt) == "vendredi-25-decembre"


class TestEvent:
    """Tests for Event class."""

    @pytest.fixture
    def sample_event(self):
        """Create a sample event for testing."""
        return Event(
            name="Concert de Jazz",
            event_url="https://lafriche.org/concert-jazz",
            start_datetime=datetime(
                2026, 1, 26, 20, 0, tzinfo=ZoneInfo("Europe/Paris")
            ),
            description="Un concert de jazz exceptionnel à La Friche.",
            categories=["Musique"],
            locations=["La Friche"],
            tags=["jazz", "concert"],
            source_id="lafriche:concert-jazz",
        )

    def test_required_fields(self):
        """Test that required fields are validated."""
        with pytest.raises(ValueError, match="name is required"):
            Event(
                name="",
                event_url="https://example.com",
                start_datetime=datetime.now(),
            )

        with pytest.raises(ValueError, match="URL is required"):
            Event(
                name="Test Event",
                event_url="",
                start_datetime=datetime.now(),
            )

    def test_category_normalization(self, sample_event):
        """Test that categories are normalized to lowercase."""
        assert sample_event.categories == ["musique"]

    def test_location_slugification(self, sample_event):
        """Test that locations are slugified."""
        assert sample_event.locations == ["la-friche"]

    def test_title_property(self, sample_event):
        """Test title generation."""
        assert sample_event.title == "Concert de Jazz"

    def test_title_with_day_of(self):
        """Test title includes day indicator for multi-day events."""
        event = Event(
            name="Festival de Marseille",
            event_url="https://example.com",
            start_datetime=datetime(2026, 2, 6, 20, 0),
            day_of="Jour 1 sur 3",
        )
        assert event.title == "Festival de Marseille - Jour 1 sur 3"

    def test_slug_property(self, sample_event):
        """Test slug generation."""
        assert sample_event.slug == "concert-de-jazz"

    def test_start_time_property(self, sample_event):
        """Test start time formatting."""
        assert sample_event.start_time == "20:00"

    def test_expiry_date_property(self, sample_event):
        """Test expiry date is next day midnight."""
        expiry = sample_event.expiry_date
        assert expiry.year == 2026
        assert expiry.month == 1
        assert expiry.day == 27
        assert expiry.hour == 0
        assert expiry.minute == 0

    def test_dates_taxonomy(self, sample_event):
        """Test French date taxonomy generation."""
        assert sample_event.dates_taxonomy == ["lundi-26-janvier"]

    def test_file_path(self, sample_event):
        """Test Hugo file path generation."""
        assert sample_event.file_path == "2026/01/26/concert-de-jazz.fr.md"

    def test_to_front_matter(self, sample_event):
        """Test front matter dictionary generation."""
        fm = sample_event.to_front_matter()

        assert fm["title"] == "Concert de Jazz"
        assert fm["name"] == "Concert de Jazz"
        assert fm["eventURL"] == "https://lafriche.org/concert-jazz"
        assert fm["startTime"] == "20:00"
        assert fm["description"] == "Un concert de jazz exceptionnel à La Friche."
        assert fm["categories"] == ["musique"]
        assert fm["locations"] == ["la-friche"]
        assert fm["dates"] == ["lundi-26-janvier"]
        assert fm["tags"] == ["jazz", "concert"]
        assert fm["sourceId"] == "lafriche:concert-jazz"
        assert fm["draft"] is False
        assert fm["expired"] is False
        assert "date" in fm
        assert "expiryDate" in fm
        assert "lastCrawled" in fm

    def test_front_matter_optional_fields(self, sample_event):
        """Test optional fields are included when set."""
        sample_event.image = "/images/concert.webp"
        sample_event.event_group_id = "festival-2026"
        sample_event.day_of = "Jour 2 sur 3"

        fm = sample_event.to_front_matter()

        assert fm["image"] == "/images/concert.webp"
        assert fm["eventGroupId"] == "festival-2026"
        assert fm["dayOf"] == "Jour 2 sur 3"

    def test_from_dict(self):
        """Test creating Event from dictionary."""
        data = {
            "name": "Test Event",
            "event_url": "https://example.com",
            "start_datetime": "2026-01-26T19:00:00+01:00",
            "description": "A test event",
            "categories": ["art"],
            "locations": ["klap"],
        }

        event = Event.from_dict(data)

        assert event.name == "Test Event"
        assert event.event_url == "https://example.com"
        assert event.description == "A test event"
        assert event.categories == ["art"]
        assert event.locations == ["klap"]
