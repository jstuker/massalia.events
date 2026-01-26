"""Tests for configurable event parser."""

from datetime import datetime

import pytest

from src.parsers.base import (
    ConfigurableEventParser,
    ParsedEvent,
    SelectorConfig,
)


class TestSelectorConfig:
    """Tests for SelectorConfig dataclass."""

    def test_default_values(self):
        config = SelectorConfig()
        assert config.name == "h2, h3, .title, .event-title"
        assert config.date == ".date, .event-date, time"
        assert config.link == "a"

    def test_from_dict(self):
        data = {
            "event_list": ".events-container",
            "event_item": ".event-card",
            "name": ".event-name",
            "date": ".event-date",
        }
        config = SelectorConfig.from_dict(data)
        assert config.event_list == ".events-container"
        assert config.event_item == ".event-card"
        assert config.name == ".event-name"
        # Defaults still work for unspecified fields
        assert config.link == "a"

    def test_from_empty_dict(self):
        config = SelectorConfig.from_dict({})
        assert config.event_list == ""
        assert config.event_item == ""
        assert config.name == "h2, h3, .title, .event-title"


class TestParsedEvent:
    """Tests for ParsedEvent dataclass."""

    def test_minimal_event(self):
        event = ParsedEvent(
            name="Test Event",
            source_url="https://example.com/event/1",
        )
        assert event.name == "Test Event"
        assert event.source_url == "https://example.com/event/1"
        assert event.date is None
        assert event.tags == []

    def test_full_event(self):
        event = ParsedEvent(
            name="Concert Jazz",
            source_url="https://example.com/events/jazz",
            date=datetime(2026, 1, 26),
            start_time="20:30",
            location="La Friche",
            description="Amazing jazz concert",
            category="musique",
            image_url="https://example.com/images/jazz.jpg",
            tags=["jazz", "live", "free"],
            raw_date="26 janvier 2026",
            raw_time="20h30",
        )
        assert event.name == "Concert Jazz"
        assert event.date.year == 2026
        assert event.start_time == "20:30"
        assert len(event.tags) == 3


class TestConfigurableEventParser:
    """Tests for ConfigurableEventParser class."""

    @pytest.fixture
    def sample_html(self):
        """Sample HTML with event cards."""
        return """
        <html>
        <body>
            <div class="events-container">
                <div class="event-card">
                    <h2 class="event-title">Concert de Jazz</h2>
                    <a href="/events/jazz-concert">Details</a>
                    <img src="/images/jazz.jpg" alt="Jazz">
                    <span class="event-date">26 janvier 2026</span>
                    <span class="event-time">20h30</span>
                    <span class="event-venue">La Friche</span>
                    <p class="event-description">Un concert exceptionnel de jazz.</p>
                    <span class="event-category">Musique</span>
                    <span class="tag">jazz</span>
                    <span class="tag">live</span>
                </div>
                <div class="event-card">
                    <h2 class="event-title">Exposition Art Moderne</h2>
                    <a href="/events/art-expo">Details</a>
                    <img data-src="/images/art.jpg" alt="Art">
                    <span class="event-date">27/01/2026</span>
                    <span class="event-time">14:00</span>
                    <span class="event-venue">Galerie Sud</span>
                    <p class="event-description">Découvrez l'art moderne.</p>
                    <span class="event-category">Art</span>
                </div>
            </div>
        </body>
        </html>
        """

    @pytest.fixture
    def parser_config(self):
        """Parser configuration with selectors."""
        return {
            "selectors": {
                "event_list": ".events-container",
                "event_item": ".event-card",
                "name": ".event-title",
                "date": ".event-date",
                "time": ".event-time",
                "location": ".event-venue",
                "description": ".event-description",
                "category": ".event-category",
                "image": "img",
                "link": "a",
                "tags": ".tag",
            }
        }

    @pytest.fixture
    def parser(self, parser_config):
        """Create parser with config."""
        return ConfigurableEventParser(
            config=parser_config,
            base_url="https://example.com",
            source_id="test",
        )

    def test_parse_events(self, parser, sample_html):
        """Test parsing multiple events."""
        events = parser.parse(sample_html)
        assert len(events) == 2

    def test_parse_event_name(self, parser, sample_html):
        """Test event name extraction."""
        events = parser.parse(sample_html)
        assert events[0].name == "Concert de Jazz"
        assert events[1].name == "Exposition Art Moderne"

    def test_parse_event_url(self, parser, sample_html):
        """Test event URL extraction and resolution."""
        events = parser.parse(sample_html)
        assert events[0].source_url == "https://example.com/events/jazz-concert"
        assert events[1].source_url == "https://example.com/events/art-expo"

    def test_parse_event_date(self, parser, sample_html):
        """Test date parsing."""
        events = parser.parse(sample_html)
        assert events[0].date is not None
        assert events[0].date.day == 26
        assert events[0].date.month == 1
        assert events[0].date.year == 2026

        assert events[1].date is not None
        assert events[1].date.day == 27

    def test_parse_event_time(self, parser, sample_html):
        """Test time extraction."""
        events = parser.parse(sample_html)
        assert events[0].start_time == "20:30"
        assert events[1].start_time == "14:00"

    def test_parse_event_location(self, parser, sample_html):
        """Test location extraction."""
        events = parser.parse(sample_html)
        assert events[0].location == "La Friche"
        assert events[1].location == "Galerie Sud"

    def test_parse_event_description(self, parser, sample_html):
        """Test description extraction."""
        events = parser.parse(sample_html)
        assert "jazz" in events[0].description.lower()
        assert "art" in events[1].description.lower()

    def test_parse_event_category(self, parser, sample_html):
        """Test category extraction."""
        events = parser.parse(sample_html)
        assert events[0].category == "Musique"
        assert events[1].category == "Art"

    def test_parse_event_tags(self, parser, sample_html):
        """Test tags extraction."""
        events = parser.parse(sample_html)
        assert "jazz" in events[0].tags
        assert "live" in events[0].tags
        assert len(events[1].tags) == 0  # No tags

    def test_raw_date_preserved(self, parser, sample_html):
        """Test that raw date string is preserved."""
        events = parser.parse(sample_html)
        assert events[0].raw_date == "26 janvier 2026"
        assert events[1].raw_date == "27/01/2026"


class TestConfigurableEventParserConversion:
    """Tests for ParsedEvent to Event conversion."""

    @pytest.fixture
    def parser(self):
        return ConfigurableEventParser(
            config={"selectors": {}},
            base_url="https://example.com",
            source_id="test",
            category_map={"Concert": "musique"},
        )

    def test_to_event_basic(self, parser):
        """Test basic conversion."""
        parsed = ParsedEvent(
            name="Test Event",
            source_url="https://example.com/event/1",
            date=datetime(2026, 1, 26),
            start_time="20:00",
            category="Concert",
        )
        event = parser.to_event(parsed)

        assert event.name == "Test Event"
        assert event.event_url == "https://example.com/event/1"
        assert event.start_datetime is not None
        assert event.start_datetime.hour == 20
        assert "musique" in event.categories

    def test_to_event_default_time(self, parser):
        """Test default time is applied."""
        parsed = ParsedEvent(
            name="Test Event",
            source_url="https://example.com/event/1",
            date=datetime(2026, 1, 26),
        )
        event = parser.to_event(parsed, default_time="19:00")

        assert event.start_datetime.hour == 19
        assert event.start_datetime.minute == 0

    def test_to_event_source_id_generation(self, parser):
        """Test source ID is generated."""
        parsed = ParsedEvent(
            name="Test Event",
            source_url="https://example.com/events/my-event-123",
            date=datetime(2026, 1, 26),
        )
        event = parser.to_event(parsed)

        assert event.source_id == "test:my-event-123"

    def test_category_mapping(self, parser):
        """Test category mapping."""
        # Explicit mapping
        assert parser._map_category("Concert") == "musique"
        # Default mapping
        assert parser._map_category("Danse") == "danse"
        assert parser._map_category("Exposition") == "art"
        # Fallback
        assert parser._map_category("Unknown") == "communaute"
        assert parser._map_category(None) == "communaute"


class TestConfigurableEventParserFallback:
    """Tests for fallback selector behavior."""

    @pytest.fixture
    def html_with_fallback_selectors(self):
        """HTML using common fallback selectors."""
        return """
        <html>
        <body>
            <article class="event">
                <h3>Fallback Event</h3>
                <a href="/fallback">Link</a>
                <time>15 février 2026</time>
            </article>
        </body>
        </html>
        """

    def test_fallback_selectors(self, html_with_fallback_selectors):
        """Test fallback selectors are used when configured ones fail."""
        parser = ConfigurableEventParser(
            config={"selectors": {}},  # No configured selectors
            base_url="https://example.com",
            source_id="test",
        )
        events = parser.parse(html_with_fallback_selectors)
        assert len(events) == 1
        assert events[0].name == "Fallback Event"


class TestConfigurableEventParserEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_html(self):
        """Test parsing empty HTML."""
        parser = ConfigurableEventParser(
            config={"selectors": {}},
            base_url="https://example.com",
            source_id="test",
        )
        events = parser.parse("")
        assert len(events) == 0

    def test_html_without_events(self):
        """Test parsing HTML without event elements."""
        html = "<html><body><p>No events here</p></body></html>"
        parser = ConfigurableEventParser(
            config={"selectors": {}},
            base_url="https://example.com",
            source_id="test",
        )
        events = parser.parse(html)
        assert len(events) == 0

    def test_event_without_name_skipped(self):
        """Test events without names are skipped."""
        html = """
        <div class="event-card">
            <a href="/event/1">Link</a>
        </div>
        """
        parser = ConfigurableEventParser(
            config={"selectors": {"event_item": ".event-card"}},
            base_url="https://example.com",
            source_id="test",
        )
        events = parser.parse(html)
        assert len(events) == 0

    def test_event_without_url_skipped(self):
        """Test events without URLs are skipped."""
        html = """
        <div class="event-card">
            <h2>Event Without URL</h2>
        </div>
        """
        parser = ConfigurableEventParser(
            config={"selectors": {"event_item": ".event-card"}},
            base_url="https://example.com",
            source_id="test",
        )
        events = parser.parse(html)
        assert len(events) == 0

    def test_malformed_html(self):
        """Test parsing malformed HTML doesn't crash."""
        html = "<div class='event-card'><h2>Broken Event</h2><a href='/test'>Link"
        parser = ConfigurableEventParser(
            config={"selectors": {"event_item": ".event-card"}},
            base_url="https://example.com",
            source_id="test",
        )
        # Should not raise exception
        events = parser.parse(html)
        # BeautifulSoup should handle malformed HTML gracefully
        assert len(events) == 1
        assert events[0].name == "Broken Event"


class TestParseAndConvert:
    """Tests for the parse_and_convert convenience method."""

    @pytest.fixture
    def sample_html(self):
        return """
        <div class="event-card">
            <h2>Quick Event</h2>
            <a href="/quick">Link</a>
            <span class="date">28 janvier 2026</span>
        </div>
        """

    def test_parse_and_convert(self, sample_html):
        """Test combined parse and convert."""
        parser = ConfigurableEventParser(
            config={"selectors": {"event_item": ".event-card", "date": ".date"}},
            base_url="https://example.com",
            source_id="test",
        )
        events = parser.parse_and_convert(sample_html)

        assert len(events) == 1
        assert events[0].name == "Quick Event"
        assert events[0].event_url == "https://example.com/quick"
        assert events[0].start_datetime is not None
        assert events[0].source_id == "test:quick"
