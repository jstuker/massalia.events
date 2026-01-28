"""Tests for the Shotgun (shotgun.live) parser."""

import json
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.shotgun import (
    ShotgunParser,
    _extract_event_urls_from_html,
    _extract_json_ld,
    _map_category_from_json_ld,
    _parse_event_from_json_ld,
)
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_listing_html():
    """Sample Shotgun city listing page HTML with event links."""
    return """
    <html>
    <body>
        <div class="gap grid grid-cols-1">
            <h2 class="font-title">mer 28 janv.</h2>
            <a data-slot="tracked-link" href="/fr/events/electro-night">
                <div class="pt-4 pb-8">
                    <img alt="Electro Night" src="https://res.cloudinary.com/shotgun/image/upload/electro.jpg">
                    <p class="line-clamp-2 text-lg leading-tight font-bold">Electro Night</p>
                    <div class="text-muted-foreground">Baby Club - Marseille</div>
                    <time datetime="2026-01-28T22:59:00.000Z">mer. 28 janv.</time>
                </div>
            </a>
            <a data-slot="tracked-link" href="/fr/events/jazz-sunset">
                <div class="pt-4 pb-8">
                    <img alt="Jazz Sunset" src="https://res.cloudinary.com/shotgun/image/upload/jazz.jpg">
                    <p class="line-clamp-2 text-lg leading-tight font-bold">Jazz Sunset</p>
                    <div class="text-muted-foreground">Le Makeda</div>
                    <time datetime="2026-01-29T19:00:00.000Z">jeu. 29 janv.</time>
                </div>
            </a>
            <a data-slot="tracked-link" href="/fr/events/electro-night">
                <!-- Duplicate link to test dedup -->
                <div class="pt-4 pb-8">
                    <p>Electro Night</p>
                </div>
            </a>
            <!-- Non-event link -->
            <a href="/fr/search">Search</a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_html():
    """Sample Shotgun event detail page HTML with JSON-LD."""
    json_ld_brand = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "Brand",
            "name": "Shotgun",
        }
    )
    json_ld_event = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "MusicEvent",
            "name": "Electro Night",
            "url": "https://shotgun.live/fr/events/electro-night",
            "image": "https://res.cloudinary.com/shotgun/image/upload/electro.jpg",
            "startDate": "2026-01-28T22:00:00.000Z",
            "doorTime": "2026-01-28T22:00:00.000Z",
            "endDate": "2026-01-29T05:00:00.000Z",
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": {
                "@type": "Place",
                "name": "Baby Club, 13006 Marseille, France",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": "2 Rue André Poggioli",
                    "addressLocality": "Marseille",
                    "postalCode": "13006",
                    "addressCountry": "FR",
                },
                "geo": {
                    "@type": "GeoCoordinates",
                    "latitude": 43.2919,
                    "longitude": 5.3838,
                },
            },
            "description": "Une soirée électro au cœur de Marseille avec les meilleurs DJs locaux.",
            "organizer": {
                "@type": "LocalBusiness",
                "name": "Baby Club",
                "url": "https://shotgun.live/fr/venues/baby-club",
            },
            "performer": [
                {"@type": "MusicGroup", "name": "DJ Alpha"},
                {"@type": "MusicGroup", "name": "DJ Beta"},
            ],
            "offers": [
                {
                    "@type": "Offer",
                    "availability": "https://schema.org/InStock",
                    "name": "Early Bird",
                    "price": 10.0,
                    "priceCurrency": "EUR",
                }
            ],
        }
    )
    return f"""
    <html>
    <head>
        <title>Electro Night, Marseille · Billets Shotgun</title>
        <meta property="og:title" content="Electro Night, Marseille · Billets Shotgun">
        <meta property="og:description" content="Billets pour Electro Night à Aix-Marseille, France – le 28 janvier 2026">
        <meta property="og:image" content="https://res.cloudinary.com/shotgun/image/upload/electro.jpg">
        <script type="application/ld+json">{json_ld_brand}</script>
        <script type="application/ld+json">{json_ld_event}</script>
    </head>
    <body>
        <h1>Electro Night</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_json_ld_music_event():
    """A complete MusicEvent JSON-LD object."""
    return {
        "@context": "https://schema.org",
        "@type": "MusicEvent",
        "name": "Bass Miel #3",
        "url": "https://shotgun.live/fr/events/bass-miel-3",
        "image": "https://res.cloudinary.com/shotgun/image/upload/bass-miel.jpg",
        "startDate": "2026-01-29T20:00:00.000Z",
        "endDate": "2026-01-30T04:00:00.000Z",
        "location": {
            "@type": "Place",
            "name": "10 Rue des Trois Mages, 13006 Marseille, France",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "10 Rue des Trois Mages",
                "addressLocality": "Marseille",
                "postalCode": "13006",
                "addressCountry": "FR",
            },
        },
        "description": "Bass Miel revient pour sa troisième édition avec du trance et techno.",
        "organizer": {
            "@type": "LocalBusiness",
            "name": "Le Club",
            "url": "https://shotgun.live/fr/venues/le-club",
        },
        "performer": [
            {"@type": "MusicGroup", "name": "Zelezna"},
            {"@type": "MusicGroup", "name": "Immek"},
        ],
    }


@pytest.fixture
def category_map():
    """Standard category mapping from sources.yaml."""
    return {
        "Techno": "musique",
        "House": "musique",
        "Concert": "musique",
        "Spectacle": "theatre",
        "Exposition": "art",
        "Festival": "communaute",
    }


# ── Test _extract_event_urls_from_html ───────────────────────────────


class TestExtractEventUrls:
    """Tests for extracting event URLs from listing page HTML."""

    def test_extracts_event_urls(self, sample_listing_html):
        urls = _extract_event_urls_from_html(sample_listing_html)
        assert len(urls) == 2  # Deduped
        assert any("electro-night" in u for u in urls)
        assert any("jazz-sunset" in u for u in urls)

    def test_resolves_relative_urls(self, sample_listing_html):
        urls = _extract_event_urls_from_html(
            sample_listing_html, base_url="https://shotgun.live"
        )
        for url in urls:
            assert url.startswith("https://shotgun.live/")

    def test_excludes_non_event_links(self, sample_listing_html):
        urls = _extract_event_urls_from_html(sample_listing_html)
        assert not any("/search" in u for u in urls)

    def test_handles_empty_html(self):
        urls = _extract_event_urls_from_html("<html><body></body></html>")
        assert urls == []

    def test_handles_absolute_urls(self):
        html = '<html><body><a href="https://shotgun.live/fr/events/test-event">Test</a></body></html>'
        urls = _extract_event_urls_from_html(html)
        assert len(urls) == 1
        assert urls[0] == "https://shotgun.live/fr/events/test-event"


# ── Test _extract_json_ld ────────────────────────────────────────────


class TestExtractJsonLd:
    """Tests for extracting JSON-LD data from HTML."""

    def test_extracts_json_ld(self, sample_detail_html):
        results = _extract_json_ld(sample_detail_html)
        assert len(results) == 2  # Brand + MusicEvent

    def test_parses_music_event(self, sample_detail_html):
        results = _extract_json_ld(sample_detail_html)
        music_events = [r for r in results if r.get("@type") == "MusicEvent"]
        assert len(music_events) == 1
        assert music_events[0]["name"] == "Electro Night"

    def test_handles_no_json_ld(self):
        html = "<html><head></head><body></body></html>"
        results = _extract_json_ld(html)
        assert results == []

    def test_handles_invalid_json(self):
        html = '<html><head><script type="application/ld+json">{invalid json</script></head></html>'
        results = _extract_json_ld(html)
        assert results == []

    def test_handles_multiple_scripts(self):
        data1 = json.dumps({"@type": "Brand", "name": "Test"})
        data2 = json.dumps({"@type": "MusicEvent", "name": "Event"})
        html = f"""
        <html><head>
            <script type="application/ld+json">{data1}</script>
            <script type="application/ld+json">{data2}</script>
        </head></html>
        """
        results = _extract_json_ld(html)
        assert len(results) == 2


# ── Test _parse_event_from_json_ld ───────────────────────────────────


class TestParseEventFromJsonLd:
    """Tests for converting JSON-LD to Event objects."""

    def test_parses_basic_event(self, sample_json_ld_music_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_music_event,
            "https://shotgun.live/fr/events/bass-miel-3",
            category_map,
        )
        assert event is not None
        assert event.name == "Bass Miel #3"
        assert event.event_url == "https://shotgun.live/fr/events/bass-miel-3"
        assert event.source_id == "shotgun:bass-miel-3"

    def test_parses_start_datetime(self, sample_json_ld_music_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_music_event,
            "https://shotgun.live/fr/events/bass-miel-3",
            category_map,
        )
        # 2026-01-29T20:00:00.000Z = 2026-01-29T21:00:00+01:00 in Paris
        assert event.start_datetime.year == 2026
        assert event.start_datetime.month == 1
        assert event.start_datetime.day == 29
        assert event.start_datetime.hour == 21  # UTC+1

    def test_parses_description(self, sample_json_ld_music_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_music_event,
            "https://shotgun.live/fr/events/bass-miel-3",
            category_map,
        )
        assert "Bass Miel" in event.description

    def test_parses_image(self, sample_json_ld_music_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_music_event,
            "https://shotgun.live/fr/events/bass-miel-3",
            category_map,
        )
        assert (
            event.image
            == "https://res.cloudinary.com/shotgun/image/upload/bass-miel.jpg"
        )

    def test_parses_location(self, sample_json_ld_music_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_music_event,
            "https://shotgun.live/fr/events/bass-miel-3",
            category_map,
        )
        # Should use organizer name as venue
        assert len(event.locations) > 0

    def test_parses_performers_as_tags(self, sample_json_ld_music_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_music_event,
            "https://shotgun.live/fr/events/bass-miel-3",
            category_map,
        )
        assert "zelezna" in event.tags
        assert "immek" in event.tags

    def test_music_event_category(self, sample_json_ld_music_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_music_event,
            "https://shotgun.live/fr/events/bass-miel-3",
            category_map,
        )
        assert "musique" in event.categories

    def test_returns_none_for_missing_name(self, category_map):
        json_ld = {"@type": "MusicEvent", "startDate": "2026-01-28T22:00:00.000Z"}
        event = _parse_event_from_json_ld(json_ld, "https://example.com", category_map)
        assert event is None

    def test_returns_none_for_missing_date(self, category_map):
        json_ld = {"@type": "MusicEvent", "name": "Test Event"}
        event = _parse_event_from_json_ld(json_ld, "https://example.com", category_map)
        assert event is None

    def test_truncates_long_description(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T22:00:00.000Z",
            "description": "A" * 200,
        }
        event = _parse_event_from_json_ld(
            json_ld, "https://example.com/events/test", category_map
        )
        assert len(event.description) <= 160

    def test_handles_empty_performers(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T22:00:00.000Z",
            "performer": [],
        }
        event = _parse_event_from_json_ld(
            json_ld, "https://example.com/events/test", category_map
        )
        assert event.tags == []

    def test_handles_missing_location(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T22:00:00.000Z",
        }
        event = _parse_event_from_json_ld(
            json_ld, "https://example.com/events/test", category_map
        )
        assert event.locations == []

    def test_handles_utc_z_date_format(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T22:00:00.000Z",
        }
        event = _parse_event_from_json_ld(
            json_ld, "https://example.com/events/test", category_map
        )
        assert event is not None
        assert event.start_datetime.tzinfo is not None

    def test_handles_iso_date_with_offset(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T23:00:00+01:00",
        }
        event = _parse_event_from_json_ld(
            json_ld, "https://example.com/events/test", category_map
        )
        assert event is not None
        assert event.start_datetime.hour == 23

    def test_source_id_from_url_slug(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T22:00:00.000Z",
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://shotgun.live/fr/events/my-cool-event",
            category_map,
        )
        assert event.source_id == "shotgun:my-cool-event"

    def test_uses_organizer_as_venue_name(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T22:00:00.000Z",
            "location": {
                "@type": "Place",
                "name": "2 Rue André Poggioli, 13006 Marseille, France",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "Marseille",
                },
            },
            "organizer": {
                "@type": "LocalBusiness",
                "name": "Baby Club",
            },
        }
        event = _parse_event_from_json_ld(
            json_ld, "https://example.com/events/test", category_map
        )
        assert len(event.locations) > 0


# ── Test _map_category_from_json_ld ──────────────────────────────────


class TestMapCategoryFromJsonLd:
    """Tests for category mapping from JSON-LD."""

    def test_music_event_type(self, category_map):
        result = _map_category_from_json_ld({"@type": "MusicEvent"}, category_map)
        assert result == "musique"

    def test_dance_event_type(self, category_map):
        result = _map_category_from_json_ld({"@type": "DanceEvent"}, category_map)
        assert result == "danse"

    def test_theater_event_type(self, category_map):
        result = _map_category_from_json_ld({"@type": "TheaterEvent"}, category_map)
        assert result == "theatre"

    def test_visual_arts_event_type(self, category_map):
        result = _map_category_from_json_ld({"@type": "VisualArtsEvent"}, category_map)
        assert result == "art"

    def test_comedy_event_type(self, category_map):
        result = _map_category_from_json_ld({"@type": "ComedyEvent"}, category_map)
        assert result == "theatre"

    def test_festival_event_type(self, category_map):
        result = _map_category_from_json_ld({"@type": "Festival"}, category_map)
        assert result == "communaute"

    def test_unknown_type_defaults_to_musique(self, category_map):
        result = _map_category_from_json_ld({"@type": "Event"}, category_map)
        assert result == "musique"

    def test_no_type_defaults_to_musique(self, category_map):
        result = _map_category_from_json_ld({}, category_map)
        assert result == "musique"


# ── Test ShotgunParser integration ───────────────────────────────────


class TestShotgunParserIntegration:
    """Integration tests for ShotgunParser with mocked Playwright."""

    @pytest.fixture
    def mock_config(self):
        return {
            "name": "Shotgun",
            "id": "shotgun",
            "url": "https://shotgun.live/fr/cities/aix-marseille",
            "parser": "shotgun",
            "rate_limit": {"delay_between_pages": 0.0},
            "category_map": {
                "Techno": "musique",
                "House": "musique",
            },
        }

    @pytest.fixture
    def parser(self, mock_config):
        http_client = MagicMock()
        image_downloader = MagicMock()
        markdown_generator = MagicMock()
        return ShotgunParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=image_downloader,
            markdown_generator=markdown_generator,
        )

    def test_source_name(self, parser):
        assert parser.source_name == "Shotgun"

    @patch("src.parsers.shotgun._get_playwright_page")
    def test_fetch_page_uses_playwright(self, mock_playwright, parser):
        """Test that fetch_page uses Playwright instead of httpx."""
        mock_playwright.return_value = ("<html>OK</html>", None)
        result = parser.fetch_page("https://shotgun.live/fr/cities/aix-marseille")
        assert result == "<html>OK</html>"
        mock_playwright.assert_called_once()

    @patch("src.parsers.shotgun._get_playwright_page")
    def test_fetch_page_returns_empty_on_failure(self, mock_playwright, parser):
        """Test that fetch_page returns empty string on Playwright failure."""
        mock_playwright.return_value = (None, None)
        result = parser.fetch_page("https://shotgun.live/fr/cities/aix-marseille")
        assert result == ""

    @patch("src.parsers.shotgun._get_playwright_page")
    def test_parse_events_with_json_ld(
        self, mock_playwright, parser, sample_listing_html, sample_detail_html
    ):
        """Test full flow: first page via parser -> detail pages -> events."""
        # parse_events receives first page HTML via HTMLParser argument.
        # Playwright is only called for page 2+ listing and detail pages.
        empty_page = "<html><body></body></html>"
        mock_playwright.side_effect = [
            (empty_page, None),  # Listing page 2 (empty, stops pagination)
            (sample_detail_html, None),  # Event detail 1
            (sample_detail_html, None),  # Event detail 2
        ]

        # Simulate the HTMLParser that crawl() would create from fetch_page
        html_parser = HTMLParser(sample_listing_html, "https://shotgun.live")
        events = parser.parse_events(html_parser)

        assert len(events) == 2
        assert all(isinstance(e, Event) for e in events)
        assert all(e.name == "Electro Night" for e in events)

    def test_parse_events_with_empty_listing(self, parser):
        """Test graceful handling when listing page has no events."""
        html_parser = HTMLParser("<html><body></body></html>", "https://shotgun.live")
        events = parser.parse_events(html_parser)
        assert events == []

    @patch("src.parsers.shotgun._get_playwright_page")
    def test_handles_detail_page_failure(
        self, mock_playwright, parser, sample_listing_html
    ):
        """Test graceful handling when detail page fails to load."""
        empty_page = "<html><body></body></html>"
        mock_playwright.side_effect = [
            (empty_page, None),  # Listing page 2 (empty, stops pagination)
            (None, None),  # First detail fails
            (None, None),  # Second detail fails
        ]

        html_parser = HTMLParser(sample_listing_html, "https://shotgun.live")
        events = parser.parse_events(html_parser)

        assert events == []

    @patch("src.parsers.shotgun._get_playwright_page")
    def test_handles_detail_page_without_json_ld(
        self, mock_playwright, parser, sample_listing_html
    ):
        """Test fallback when detail page has no JSON-LD."""
        detail_html = """
        <html>
        <head>
            <meta property="og:description" content="Billets pour Test Event à Aix-Marseille, France – le 28 janvier 2026">
            <meta property="og:image" content="https://example.com/test.jpg">
        </head>
        <body>
            <h1>Test Event</h1>
        </body>
        </html>
        """
        empty_page = "<html><body></body></html>"
        mock_playwright.side_effect = [
            (empty_page, None),  # Listing page 2 (empty, stops pagination)
            (detail_html, None),  # First event detail
            (detail_html, None),  # Second event detail
        ]

        html_parser = HTMLParser(sample_listing_html, "https://shotgun.live")
        events = parser.parse_events(html_parser)

        # Should still find events via HTML fallback
        assert len(events) == 2
        assert events[0].name == "Test Event"

    def test_skips_empty_first_page(self, parser):
        """Test that no Playwright calls are made when first page is empty."""
        empty_html = "<html><body></body></html>"
        html_parser = HTMLParser(empty_html, "https://shotgun.live")
        events = parser.parse_events(html_parser)

        assert events == []


# ── Test HTML fallback parsing ──────────────────────────────────────


class TestHtmlFallbackParsing:
    """Tests for the HTML fallback when JSON-LD is unavailable."""

    @pytest.fixture
    def parser(self):
        config = {
            "name": "Shotgun",
            "id": "shotgun",
            "url": "https://shotgun.live/fr/cities/aix-marseille",
            "parser": "shotgun",
            "rate_limit": {"delay_between_pages": 0.0},
            "category_map": {},
        }
        return ShotgunParser(
            config=config,
            http_client=MagicMock(),
            image_downloader=MagicMock(),
            markdown_generator=MagicMock(),
        )

    def test_fallback_parses_from_og_tags(self, parser):
        html = """
        <html>
        <head>
            <meta property="og:description" content="Billets pour Mon Événement à Aix-Marseille, France – le 15 mars 2026">
            <meta property="og:image" content="https://example.com/image.jpg">
        </head>
        <body><h1>Mon Événement</h1></body>
        </html>
        """
        event = parser._parse_from_html(
            html, "https://shotgun.live/fr/events/mon-evenement"
        )
        assert event is not None
        assert event.name == "Mon Événement"
        assert event.start_datetime.month == 3
        assert event.start_datetime.day == 15
        assert event.image == "https://example.com/image.jpg"
        assert event.source_id == "shotgun:mon-evenement"

    def test_fallback_returns_none_without_h1(self, parser):
        html = """
        <html>
        <head>
            <meta property="og:description" content="le 15 mars 2026">
        </head>
        <body></body>
        </html>
        """
        event = parser._parse_from_html(html, "https://example.com/events/test")
        assert event is None

    def test_fallback_returns_none_without_date(self, parser):
        html = """
        <html>
        <head>
            <meta property="og:description" content="No date here">
        </head>
        <body><h1>No Date Event</h1></body>
        </html>
        """
        event = parser._parse_from_html(html, "https://example.com/events/test")
        assert event is None

    def test_fallback_parses_all_french_months(self, parser):
        months = {
            "janvier": 1,
            "février": 2,
            "mars": 3,
            "avril": 4,
            "mai": 5,
            "juin": 6,
            "juillet": 7,
            "août": 8,
            "septembre": 9,
            "octobre": 10,
            "novembre": 11,
            "décembre": 12,
        }
        for month_name, month_num in months.items():
            html = f"""
            <html>
            <head>
                <meta property="og:description" content="le 10 {month_name} 2026">
            </head>
            <body><h1>Event {month_name}</h1></body>
            </html>
            """
            event = parser._parse_from_html(
                html, f"https://example.com/events/{month_name}"
            )
            assert event is not None, f"Failed to parse {month_name}"
            assert event.start_datetime.month == month_num, (
                f"Wrong month for {month_name}"
            )
