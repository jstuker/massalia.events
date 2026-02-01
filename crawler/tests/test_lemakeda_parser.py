"""Tests for the Le Makeda parser."""

import json
from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.lemakeda import LeMakedaParser, _strip_html
from src.utils.http import FetchResult
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_api_event():
    """Sample event from the Tribe Events API."""
    return {
        "id": 12345,
        "global_id": "lemakeda.com?id=12345",
        "title": "Les Nubians \u00b7 Sir Romy",
        "description": "<p>Soir\u00e9e Neo Soul avec le l\u00e9gendaire "
        "duo <strong>Les Nubians</strong>. "
        "Premi\u00e8re partie : Sir Romy en duo intimiste.</p>",
        "excerpt": "<p>Soir\u00e9e Neo Soul au Makeda</p>",
        "url": "https://www.lemakeda.com/evenements/les-nubians-makeda/",
        "slug": "les-nubians-makeda",
        "start_date": "2026-01-08 20:00:00",
        "end_date": "2026-01-08 23:00:00",
        "utc_start_date": "2026-01-08 19:00:00",
        "utc_end_date": "2026-01-08 22:00:00",
        "timezone": "Europe/Paris",
        "all_day": False,
        "image": {
            "url": "https://www.lemakeda.com/wp-content/uploads/2025/11/nubians.png",
            "id": 678,
            "width": 1200,
            "height": 630,
        },
        "categories": [
            {
                "name": "Concert",
                "slug": "concert",
                "id": 15,
                "taxonomy": "tribe_events_cat",
            }
        ],
        "tags": [
            {"name": "neo soul", "slug": "neo-soul"},
            {"name": "live", "slug": "live"},
        ],
        "venue": {
            "id": 100,
            "venue": "Le Makeda \u00e0 Marseille",
            "address": "103 rue Ferrari",
            "city": "Marseille",
            "zip": "13005",
            "country": "France",
        },
        "cost": "\u20ac20",
        "status": "publish",
    }


@pytest.fixture
def sample_api_event_dj_set():
    """Sample DJ Set event from the API."""
    return {
        "id": 12346,
        "title": "Rooted By Echoes Room",
        "description": "<p>Soir\u00e9e musique \u00e9lectronique.</p>",
        "url": "https://www.lemakeda.com/evenements/rooted-by-echoes-room/",
        "slug": "rooted-by-echoes-room",
        "start_date": "2026-01-09 22:30:00",
        "end_date": "2026-01-10 03:30:00",
        "all_day": False,
        "image": {
            "url": "https://www.lemakeda.com/wp-content/uploads/2025/12/echoes.png",
        },
        "categories": [{"name": "DJ Set", "slug": "dj-set", "id": 16}],
        "tags": [
            {"name": "house", "slug": "house"},
            {"name": "techno", "slug": "techno"},
        ],
        "venue": {
            "venue": "Le Makeda \u00e0 Marseille",
            "city": "Marseille",
        },
        "cost": "\u20ac10.99",
        "status": "publish",
    }


@pytest.fixture
def sample_api_event_minimal():
    """Minimal event with only required fields."""
    return {
        "id": 99999,
        "title": "Minimal Event",
        "url": "https://www.lemakeda.com/evenements/minimal-event/",
        "start_date": "2026-03-15 20:00:00",
        "categories": [],
        "tags": [],
    }


@pytest.fixture
def sample_api_event_no_title():
    """Event missing title."""
    return {
        "id": 11111,
        "title": "",
        "url": "https://www.lemakeda.com/evenements/no-title/",
        "start_date": "2026-03-15 20:00:00",
    }


@pytest.fixture
def sample_api_event_no_date():
    """Event missing start date."""
    return {
        "id": 22222,
        "title": "No Date Event",
        "url": "https://www.lemakeda.com/evenements/no-date/",
        "start_date": "",
    }


@pytest.fixture
def sample_api_event_html_title():
    """Event with HTML entities in title."""
    return {
        "id": 33333,
        "title": "DJ Set &#8211; Special &amp; Live",
        "url": "https://www.lemakeda.com/evenements/dj-set-special/",
        "start_date": "2026-04-01 22:00:00",
        "categories": [{"name": "DJ Set", "slug": "dj-set", "id": 16}],
        "tags": [],
        "image": {},
    }


@pytest.fixture
def sample_api_response(sample_api_event, sample_api_event_dj_set):
    """Sample full API response with pagination."""
    return {
        "events": [sample_api_event, sample_api_event_dj_set],
        "total": 2,
        "total_pages": 1,
        "rest_url": "https://www.lemakeda.com/wp-json/tribe/events/v1/events/",
    }


@pytest.fixture
def mock_config():
    """Standard config for the parser."""
    return {
        "name": "Le Makeda",
        "id": "lemakeda",
        "url": "https://www.lemakeda.com/evenements/",
        "parser": "lemakeda",
        "rate_limit": {
            "requests_per_second": 0.5,
            "delay_between_pages": 0.0,
        },
        "category_map": {
            "Concert": "musique",
            "DJ Set": "musique",
            "DJ set multisensoriel": "musique",
            "Live": "musique",
            "Showcase": "musique",
            "Open mic": "musique",
            "Danse": "danse",
            "Performances danse": "danse",
            "Festival": "communaute",
            "Festival The Echo": "communaute",
            "Open Air": "musique",
            "Karaoké": "communaute",
            "Drag": "theatre",
            "Ateliers": "communaute",
            "Evenement immersif & multisensoriel": "communaute",
        },
    }


@pytest.fixture
def parser(mock_config):
    """Create a LeMakedaParser instance with mocked dependencies."""
    http_client = MagicMock()
    image_downloader = MagicMock()
    markdown_generator = MagicMock()
    return LeMakedaParser(
        config=mock_config,
        http_client=http_client,
        image_downloader=image_downloader,
        markdown_generator=markdown_generator,
    )


# ── Test _parse_event ───────────────────────────────────────────────


class TestParseEvent:
    """Tests for parsing individual events from API data."""

    def test_parses_complete_event(self, parser, sample_api_event):
        event = parser._parse_event(sample_api_event)
        assert event is not None
        assert event.name == "Les Nubians \u00b7 Sir Romy"
        assert isinstance(event.start_datetime, datetime)

    def test_extracts_datetime(self, parser, sample_api_event):
        event = parser._parse_event(sample_api_event)
        assert event.start_datetime.year == 2026
        assert event.start_datetime.month == 1
        assert event.start_datetime.day == 8
        assert event.start_datetime.hour == 20
        assert event.start_datetime.minute == 0

    def test_datetime_has_timezone(self, parser, sample_api_event):
        event = parser._parse_event(sample_api_event)
        assert event.start_datetime.tzinfo == PARIS_TZ

    def test_extracts_description(self, parser, sample_api_event):
        event = parser._parse_event(sample_api_event)
        assert "Neo Soul" in event.description
        assert "Les Nubians" in event.description
        # Should not contain HTML tags
        assert "<strong>" not in event.description
        assert "<p>" not in event.description

    def test_extracts_image(self, parser, sample_api_event):
        event = parser._parse_event(sample_api_event)
        assert event.image is not None
        assert "nubians.png" in event.image

    def test_extracts_categories(self, parser, sample_api_event):
        event = parser._parse_event(sample_api_event)
        assert "musique" in event.categories

    def test_extracts_tags(self, parser, sample_api_event):
        event = parser._parse_event(sample_api_event)
        assert "neo soul" in event.tags
        assert "live" in event.tags

    def test_sets_location_to_le_makeda(self, parser, sample_api_event):
        event = parser._parse_event(sample_api_event)
        assert event.locations == ["le-makeda"]

    def test_generates_source_id(self, parser, sample_api_event):
        event = parser._parse_event(sample_api_event)
        assert event.source_id == "lemakeda:12345"

    def test_extracts_event_url(self, parser, sample_api_event):
        event = parser._parse_event(sample_api_event)
        assert (
            event.event_url == "https://www.lemakeda.com/evenements/les-nubians-makeda/"
        )

    def test_parses_dj_set_event(self, parser, sample_api_event_dj_set):
        event = parser._parse_event(sample_api_event_dj_set)
        assert event is not None
        assert event.name == "Rooted By Echoes Room"
        assert "musique" in event.categories
        assert event.start_datetime.hour == 22
        assert event.start_datetime.minute == 30

    def test_parses_minimal_event(self, parser, sample_api_event_minimal):
        event = parser._parse_event(sample_api_event_minimal)
        assert event is not None
        assert event.name == "Minimal Event"
        # Default category when none specified
        assert "musique" in event.categories

    def test_returns_none_without_title(self, parser, sample_api_event_no_title):
        event = parser._parse_event(sample_api_event_no_title)
        assert event is None

    def test_returns_none_without_date(self, parser, sample_api_event_no_date):
        event = parser._parse_event(sample_api_event_no_date)
        assert event is None

    def test_returns_none_without_url(self, parser):
        data = {
            "id": 44444,
            "title": "No URL Event",
            "start_date": "2026-03-15 20:00:00",
            "url": "",
        }
        event = parser._parse_event(data)
        assert event is None

    def test_strips_html_from_title(self, parser, sample_api_event_html_title):
        event = parser._parse_event(sample_api_event_html_title)
        assert event is not None
        assert "<" not in event.name
        assert "&amp;" not in event.name
        assert "&" in event.name

    def test_truncates_long_description(self, parser):
        data = {
            "id": 55555,
            "title": "Long Description Event",
            "url": "https://www.lemakeda.com/evenements/long-desc/",
            "start_date": "2026-03-15 20:00:00",
            "description": "<p>" + "A" * 300 + "</p>",
            "categories": [],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert event is not None
        assert len(event.description) <= 160

    def test_uses_excerpt_as_fallback(self, parser):
        data = {
            "id": 66666,
            "title": "Excerpt Event",
            "url": "https://www.lemakeda.com/evenements/excerpt/",
            "start_date": "2026-03-15 20:00:00",
            "description": "",
            "excerpt": "<p>Short excerpt text</p>",
            "categories": [],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert event is not None
        assert "Short excerpt text" in event.description

    def test_handles_empty_image(self, parser):
        data = {
            "id": 77777,
            "title": "No Image Event",
            "url": "https://www.lemakeda.com/evenements/no-image/",
            "start_date": "2026-03-15 20:00:00",
            "image": {},
            "categories": [],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert event is not None
        assert event.image is None

    def test_limits_tags_to_five(self, parser):
        data = {
            "id": 88888,
            "title": "Many Tags Event",
            "url": "https://www.lemakeda.com/evenements/many-tags/",
            "start_date": "2026-03-15 20:00:00",
            "categories": [],
            "tags": [{"name": f"tag{i}", "slug": f"tag{i}"} for i in range(10)],
        }
        event = parser._parse_event(data)
        assert event is not None
        assert len(event.tags) == 5

    def test_source_id_fallback_to_slug(self, parser):
        data = {
            "title": "Slug Event",
            "url": "https://www.lemakeda.com/evenements/slug-event/",
            "start_date": "2026-03-15 20:00:00",
            "slug": "slug-event",
            "categories": [],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert event is not None
        assert event.source_id == "lemakeda:slug-event"


# ── Test _fetch_api_events ──────────────────────────────────────────


class TestFetchApiEvents:
    """Tests for fetching events from the Tribe Events API."""

    def test_fetches_single_page(self, parser, sample_api_response):
        parser.http_client.fetch.return_value = FetchResult(
            url="https://www.lemakeda.com/wp-json/tribe/events/v1/events",
            status_code=200,
            html=json.dumps(sample_api_response),
            headers={},
        )
        events = parser._fetch_api_events()
        assert len(events) == 2

    def test_handles_multi_page(
        self, parser, sample_api_event, sample_api_event_dj_set
    ):
        page1_response = {
            "events": [sample_api_event],
            "total": 2,
            "total_pages": 2,
        }
        page2_response = {
            "events": [sample_api_event_dj_set],
            "total": 2,
            "total_pages": 2,
        }
        parser.http_client.fetch.side_effect = [
            FetchResult(
                url="url1",
                status_code=200,
                html=json.dumps(page1_response),
                headers={},
            ),
            FetchResult(
                url="url2",
                status_code=200,
                html=json.dumps(page2_response),
                headers={},
            ),
        ]
        events = parser._fetch_api_events()
        assert len(events) == 2
        assert parser.http_client.fetch.call_count == 2

    def test_handles_api_error(self, parser):
        parser.http_client.fetch.return_value = FetchResult(
            url="url",
            status_code=500,
            html=None,
            headers={},
            error="Internal Server Error",
        )
        events = parser._fetch_api_events()
        assert events == []

    def test_handles_network_exception(self, parser):
        parser.http_client.fetch.side_effect = Exception("Connection refused")
        events = parser._fetch_api_events()
        assert events == []

    def test_handles_invalid_json(self, parser):
        parser.http_client.fetch.return_value = FetchResult(
            url="url",
            status_code=200,
            html="not valid json",
            headers={},
        )
        events = parser._fetch_api_events()
        assert events == []

    def test_handles_empty_events_array(self, parser):
        response = {"events": [], "total": 0, "total_pages": 0}
        parser.http_client.fetch.return_value = FetchResult(
            url="url",
            status_code=200,
            html=json.dumps(response),
            headers={},
        )
        events = parser._fetch_api_events()
        assert events == []

    def test_stops_on_404(self, parser):
        parser.http_client.fetch.return_value = FetchResult(
            url="url",
            status_code=404,
            html=None,
            headers={},
            error="Not Found",
        )
        events = parser._fetch_api_events()
        assert events == []


# ── Test category mapping ───────────────────────────────────────────


class TestCategoryMapping:
    """Tests for category extraction and mapping."""

    def test_maps_concert(self, parser):
        data = {
            "id": 1,
            "title": "Test",
            "url": "https://example.com/e/1",
            "start_date": "2026-01-01 20:00:00",
            "categories": [{"name": "Concert", "slug": "concert", "id": 15}],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert "musique" in event.categories

    def test_maps_dj_set(self, parser):
        data = {
            "id": 2,
            "title": "Test",
            "url": "https://example.com/e/2",
            "start_date": "2026-01-01 22:00:00",
            "categories": [{"name": "DJ Set", "slug": "dj-set", "id": 16}],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert "musique" in event.categories

    def test_maps_danse(self, parser):
        data = {
            "id": 3,
            "title": "Test",
            "url": "https://example.com/e/3",
            "start_date": "2026-01-01 20:00:00",
            "categories": [{"name": "Danse", "slug": "danse", "id": 255}],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert "danse" in event.categories

    def test_maps_performances_danse(self, parser):
        data = {
            "id": 4,
            "title": "Test",
            "url": "https://example.com/e/4",
            "start_date": "2026-01-01 20:00:00",
            "categories": [
                {"name": "Performances danse", "slug": "performances-danse"}
            ],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert "danse" in event.categories

    def test_maps_drag_to_theatre(self, parser):
        data = {
            "id": 5,
            "title": "Test",
            "url": "https://example.com/e/5",
            "start_date": "2026-01-01 22:00:00",
            "categories": [{"name": "Drag", "slug": "drag-2", "id": 210}],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert "theatre" in event.categories

    def test_maps_festival(self, parser):
        data = {
            "id": 6,
            "title": "Test",
            "url": "https://example.com/e/6",
            "start_date": "2026-01-01 20:00:00",
            "categories": [{"name": "Festival", "slug": "festival", "id": 162}],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert "communaute" in event.categories

    def test_maps_karaoke(self, parser):
        data = {
            "id": 7,
            "title": "Test",
            "url": "https://example.com/e/7",
            "start_date": "2026-01-01 22:00:00",
            "categories": [{"name": "Karaoké", "slug": "karaoke", "id": 92}],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert "communaute" in event.categories

    def test_defaults_to_musique_when_no_categories(self, parser):
        data = {
            "id": 8,
            "title": "Test",
            "url": "https://example.com/e/8",
            "start_date": "2026-01-01 20:00:00",
            "categories": [],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert "musique" in event.categories

    def test_handles_multiple_categories(self, parser):
        data = {
            "id": 9,
            "title": "Test",
            "url": "https://example.com/e/9",
            "start_date": "2026-01-01 20:00:00",
            "categories": [
                {"name": "Concert", "slug": "concert", "id": 15},
                {"name": "Festival", "slug": "festival", "id": 162},
            ],
            "tags": [],
        }
        event = parser._parse_event(data)
        assert len(event.categories) >= 1


# ── Test parse_events integration ───────────────────────────────────


class TestParseEventsIntegration:
    """Integration tests for the full parse_events flow."""

    def test_parse_events_returns_events(self, parser, sample_api_response):
        """Test full flow: API fetch -> parse -> events."""
        parser.http_client.fetch.return_value = FetchResult(
            url="url",
            status_code=200,
            html=json.dumps(sample_api_response),
            headers={},
        )

        # parse_events receives an HTMLParser but ignores it for API parsing
        html_parser = HTMLParser("<html></html>", "https://www.lemakeda.com")
        events = parser.parse_events(html_parser)

        assert len(events) == 2
        assert all(isinstance(e, Event) for e in events)

    def test_parse_events_handles_api_failure(self, parser):
        parser.http_client.fetch.side_effect = Exception("Network error")

        html_parser = HTMLParser("<html></html>", "https://www.lemakeda.com")
        events = parser.parse_events(html_parser)
        assert events == []

    def test_parse_events_skips_invalid_events(self, parser):
        response = {
            "events": [
                {
                    "id": 1,
                    "title": "Valid Event",
                    "url": "https://www.lemakeda.com/evenements/valid/",
                    "start_date": "2026-01-15 20:00:00",
                    "categories": [],
                    "tags": [],
                },
                {
                    "id": 2,
                    "title": "",
                    "url": "https://www.lemakeda.com/evenements/no-title/",
                    "start_date": "2026-01-15 20:00:00",
                },
                {
                    "id": 3,
                    "title": "No Date",
                    "url": "https://www.lemakeda.com/evenements/no-date/",
                    "start_date": "",
                },
            ],
            "total": 3,
            "total_pages": 1,
        }
        parser.http_client.fetch.return_value = FetchResult(
            url="url",
            status_code=200,
            html=json.dumps(response),
            headers={},
        )

        html_parser = HTMLParser("<html></html>", "https://www.lemakeda.com")
        events = parser.parse_events(html_parser)
        assert len(events) == 1
        assert events[0].name == "Valid Event"

    def test_source_name(self, parser):
        assert parser.source_name == "Le Makeda"


# ── Test _strip_html utility ────────────────────────────────────────


class TestStripHtml:
    """Tests for the HTML stripping utility."""

    def test_strips_simple_tags(self):
        assert _strip_html("<p>Hello</p>") == "Hello"

    def test_strips_nested_tags(self):
        result = _strip_html("<p>Hello <strong>World</strong></p>")
        assert result == "Hello World"

    def test_decodes_html_entities(self):
        assert _strip_html("Rock &amp; Roll") == "Rock & Roll"

    def test_decodes_smart_quotes(self):
        result = _strip_html("&#8220;Hello&#8221;")
        assert result == '"Hello"'

    def test_collapses_whitespace(self):
        result = _strip_html("<p>Hello</p>   <p>World</p>")
        assert result == "Hello World"

    def test_handles_empty_string(self):
        assert _strip_html("") == ""

    def test_handles_nbsp(self):
        assert _strip_html("Hello&nbsp;World") == "Hello World"

    def test_handles_plain_text(self):
        assert _strip_html("No HTML here") == "No HTML here"


# ── Test _extract_datetime ──────────────────────────────────────────


class TestExtractDatetime:
    """Tests for datetime extraction."""

    def test_parses_standard_format(self, parser):
        data = {"start_date": "2026-01-08 20:00:00"}
        result = parser._extract_datetime(data)
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 8
        assert result.hour == 20
        assert result.minute == 0

    def test_parses_late_night(self, parser):
        data = {"start_date": "2026-01-09 22:30:00"}
        result = parser._extract_datetime(data)
        assert result.hour == 22
        assert result.minute == 30

    def test_returns_none_for_empty(self, parser):
        data = {"start_date": ""}
        result = parser._extract_datetime(data)
        assert result is None

    def test_returns_none_for_missing(self, parser):
        data = {}
        result = parser._extract_datetime(data)
        assert result is None

    def test_returns_none_for_invalid_format(self, parser):
        data = {"start_date": "not a date"}
        result = parser._extract_datetime(data)
        assert result is None

    def test_result_has_paris_timezone(self, parser):
        data = {"start_date": "2026-06-15 21:00:00"}
        result = parser._extract_datetime(data)
        assert result.tzinfo == PARIS_TZ


# ── Test _generate_source_id ────────────────────────────────────────


class TestGenerateSourceId:
    """Tests for source ID generation."""

    def test_generates_from_id(self, parser):
        result = parser._generate_source_id({"id": 12345})
        assert result == "lemakeda:12345"

    def test_falls_back_to_slug(self, parser):
        result = parser._generate_source_id({"slug": "test-event"})
        assert result == "lemakeda:test-event"

    def test_prefers_id_over_slug(self, parser):
        result = parser._generate_source_id({"id": 999, "slug": "test"})
        assert result == "lemakeda:999"

    def test_returns_empty_for_missing_fields(self, parser):
        result = parser._generate_source_id({})
        assert result == ""
