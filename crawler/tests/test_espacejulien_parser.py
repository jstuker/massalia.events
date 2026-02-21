"""Tests for the Espace Julien parser."""

import json
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.espacejulien import (
    EspaceJulienParser,
    _extract_event_categories,
    _extract_event_urls,
    _extract_image_url,
    _extract_json_ld,
    _extract_venue_name,
    _generate_source_id,
    _is_sold_out,
    _parse_iso_datetime,
)
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_listing_html():
    """Sample Espace Julien listing page with event cards."""
    return """
    <html>
    <body>
        <div class="views-results--agenda">
            <div class="views-row" role="listitem">
                <article class="h-full">
                    <a href="/agenda/oxmo-puccino" aria-label="OXMO PUCCINO">
                        <div data-field-name="field_illustration">
                            <img src="/sites/espacejulien/files/styles/16x9_640/public/oxmo.webp"
                                 alt="" loading="lazy">
                        </div>
                        <div class="evt-date agenda--evt-date"
                             data-day="07" data-month="Mars" data-year="2026">
                            <span class="evt-date-from-hour evt-date-hour"> 20:00</span>
                        </div>
                        <div class="font-bold uppercase">
                            <span> OXMO PUCCINO </span>
                        </div>
                        <div class="flex flex-wrap">
                            <span class="badge badge-outline-default"
                                  data-term-name="rap-hip-hop"> Rap / Hip-Hop </span>
                            <span class="badge badge-outline-default"
                                  data-term-name="festival-avec-le-temps"> Festival Avec Le Temps </span>
                        </div>
                    </a>
                </article>
            </div>
            <div class="views-row" role="listitem">
                <article class="h-full">
                    <a href="/agenda/paul-taylor" aria-label="PAUL TAYLOR">
                        <div data-field-name="field_illustration">
                            <img src="/sites/espacejulien/files/styles/16x9_640/public/paul.webp"
                                 alt="" loading="lazy">
                        </div>
                        <div class="evt-date agenda--evt-date"
                             data-day="22" data-month="Février" data-year="2026">
                            <span class="evt-date-from-hour evt-date-hour"> 18:00</span>
                        </div>
                        <div class="font-bold uppercase">
                            <span> PAUL TAYLOR </span>
                        </div>
                        <div class="flex flex-wrap">
                            <span class="badge bg-danger --evt-status-full"> Complet </span>
                            <span class="badge badge-outline-default"
                                  data-term-name="humour"> Humour </span>
                        </div>
                    </a>
                </article>
            </div>
            <div class="views-row" role="listitem">
                <article class="h-full">
                    <a href="/agenda/lej" aria-label="LEJ">
                        <div data-field-name="field_illustration">
                            <img src="/sites/espacejulien/files/styles/16x9_640/public/lej.webp"
                                 alt="" loading="lazy">
                        </div>
                        <div class="evt-date agenda--evt-date"
                             data-day="15" data-month="Mars" data-year="2026">
                            <span class="evt-date-from-hour evt-date-hour"> 20:00</span>
                        </div>
                        <div class="font-bold uppercase">
                            <span> LEJ </span>
                        </div>
                        <div class="flex flex-wrap">
                            <span class="badge badge-outline-default"
                                  data-term-name="pop"> Pop </span>
                        </div>
                    </a>
                </article>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_json_ld():
    """Sample JSON-LD from an event detail page."""
    return {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": "OXMO PUCCINO",
        "url": "https://espace-julien.com/agenda/oxmo-puccino",
        "startDate": "2026-03-07T20:00:00+01:00",
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": {
            "@type": "Place",
            "name": "Espace Julien",
            "address": {
                "streetAddress": "39, cours Julien",
                "addressLocality": "MARSEILLE",
                "postalCode": "13006",
                "addressCountry": "FR",
            },
        },
        "performer": [
            {
                "@type": "Organization",
                "name": "Oxmo Puccino",
                "description": "Oxmo Puccino revient avec un nouveau spectacle. Un artiste incontournable de la scene rap francaise.",
            },
            {
                "@type": "Organization",
                "name": "TIFOL",
            },
        ],
        "keywords": "Festival Avec Le Temps, Rap / Hip-Hop",
        "image": {
            "@type": "ImageObject",
            "url": "https://espace-julien.com/sites/espacejulien/files/styles/16x9_1920/public/oxmo.jpg",
            "width": 1920,
            "height": 1080,
        },
        "isAccessibleForFree": False,
        "offers": {
            "@type": "Offer",
            "name": "Tarif Plein",
            "price": 35.2,
            "priceCurrency": "EUR",
            "availability": "http://schema.org/InStock",
        },
    }


@pytest.fixture
def sample_detail_html(sample_detail_json_ld):
    """Sample event detail page HTML with JSON-LD."""
    json_ld = json.dumps(sample_detail_json_ld)
    return f"""
    <html>
    <head>
        <script type="application/ld+json">{json_ld}</script>
        <meta name="description" content="OXMO PUCCINO en concert a l'Espace Julien le 7 mars 2026.">
    </head>
    <body>
        <h1>OXMO PUCCINO</h1>
        <div class="evt-date">Sam. 07/ 03 /26 20:00</div>
        <p>Oxmo Puccino revient avec un nouveau spectacle.</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_makeda_detail_html():
    """Sample detail page for an event at Le Makeda venue."""
    json_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "Event",
            "name": "JAZZ NIGHT",
            "startDate": "2026-04-10T21:00:00+02:00",
            "location": {
                "@type": "Place",
                "name": "Le Makeda",
                "address": {
                    "streetAddress": "18 Place aux Huiles",
                    "addressLocality": "MARSEILLE",
                    "postalCode": "13001",
                },
            },
            "performer": [
                {"@type": "Organization", "name": "Jazz Quartet"},
            ],
            "image": "https://espace-julien.com/sites/espacejulien/files/jazz.jpg",
            "keywords": "blues-jazz",
        }
    )
    return f"""
    <html>
    <head>
        <script type="application/ld+json">{json_ld}</script>
    </head>
    <body><h1>JAZZ NIGHT</h1></body>
    </html>
    """


@pytest.fixture
def category_map():
    """Standard category mapping from sources.yaml."""
    return {
        "blues-jazz": "musique",
        "chanson": "musique",
        "electro": "musique",
        "festival-avec-le-temps": "communaute",
        "humour": "theatre",
        "l-ej-c-est-le-s": "communaute",
        "pop": "musique",
        "rap-hip-hop": "musique",
        "rnb-soul": "musique",
        "rock": "musique",
    }


@pytest.fixture
def mock_config(category_map):
    return {
        "name": "Espace Julien",
        "id": "espacejulien",
        "url": "https://espace-julien.com/agenda",
        "parser": "espacejulien",
        "rate_limit": {"delay_between_pages": 0.0},
        "category_map": category_map,
    }


@pytest.fixture
def parser(mock_config):
    http_client = MagicMock()
    image_downloader = MagicMock()
    markdown_generator = MagicMock()
    return EspaceJulienParser(
        config=mock_config,
        http_client=http_client,
        image_downloader=image_downloader,
        markdown_generator=markdown_generator,
    )


# ── Test _extract_event_urls ────────────────────────────────────────


class TestExtractEventUrls:
    """Tests for extracting event URLs from listing page."""

    def test_extracts_event_urls(self, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html, "https://espace-julien.com/agenda"
        )
        urls = _extract_event_urls(html_parser)
        assert len(urls) == 3
        assert any("oxmo-puccino" in u for u in urls)
        assert any("paul-taylor" in u for u in urls)
        assert any("lej" in u for u in urls)

    def test_resolves_to_absolute_urls(self, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html, "https://espace-julien.com/agenda"
        )
        urls = _extract_event_urls(html_parser)
        for url in urls:
            assert url.startswith("https://")

    def test_handles_empty_html(self):
        html_parser = HTMLParser(
            "<html><body></body></html>", "https://espace-julien.com/agenda"
        )
        urls = _extract_event_urls(html_parser)
        assert urls == []

    def test_deduplicates_urls(self):
        html = """
        <html><body>
            <div class="views-row"><a href="/agenda/test">Test 1</a></div>
            <div class="views-row"><a href="/agenda/test">Test 2</a></div>
        </body></html>
        """
        html_parser = HTMLParser(html, "https://espace-julien.com")
        urls = _extract_event_urls(html_parser)
        assert len(urls) == 1

    def test_excludes_listing_page_link(self):
        html = """
        <html><body>
            <div class="views-row"><a href="/agenda">Agenda</a></div>
            <div class="views-row"><a href="/agenda/">Agenda</a></div>
            <div class="views-row"><a href="/agenda/real-event">Event</a></div>
        </body></html>
        """
        html_parser = HTMLParser(html, "https://espace-julien.com")
        urls = _extract_event_urls(html_parser)
        assert len(urls) == 1
        assert "real-event" in urls[0]


# ── Test _extract_event_categories ──────────────────────────────────


class TestExtractEventCategories:
    """Tests for extracting categories from event cards."""

    def test_extracts_categories(self, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html, "https://espace-julien.com/agenda"
        )
        cards = html_parser.select("div.views-row")
        # First card: Oxmo Puccino has rap-hip-hop and festival-avec-le-temps
        categories = _extract_event_categories(cards[0])
        assert "rap-hip-hop" in categories
        assert "festival-avec-le-temps" in categories

    def test_single_category(self, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html, "https://espace-julien.com/agenda"
        )
        cards = html_parser.select("div.views-row")
        # Third card: LEJ has only pop
        categories = _extract_event_categories(cards[2])
        assert categories == ["pop"]

    def test_no_categories(self):
        html = '<div class="views-row"><a href="/agenda/test">Test</a></div>'
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        card = soup.select_one("div.views-row")
        categories = _extract_event_categories(card)
        assert categories == []


# ── Test _is_sold_out ───────────────────────────────────────────────


class TestIsSoldOut:
    """Tests for sold-out detection."""

    def test_detects_sold_out(self, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html, "https://espace-julien.com/agenda"
        )
        cards = html_parser.select("div.views-row")
        # Second card (Paul Taylor) has --evt-status-full
        assert _is_sold_out(cards[1]) is True

    def test_not_sold_out(self, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html, "https://espace-julien.com/agenda"
        )
        cards = html_parser.select("div.views-row")
        assert _is_sold_out(cards[0]) is False
        assert _is_sold_out(cards[2]) is False


# ── Test _extract_json_ld ───────────────────────────────────────────


class TestExtractJsonLd:
    """Tests for JSON-LD extraction."""

    def test_extracts_event_json_ld(self, sample_detail_html):
        results = _extract_json_ld(sample_detail_html)
        assert len(results) == 1
        assert results[0]["@type"] == "Event"
        assert results[0]["name"] == "OXMO PUCCINO"

    def test_handles_no_json_ld(self):
        results = _extract_json_ld("<html><head></head><body></body></html>")
        assert results == []

    def test_handles_invalid_json(self):
        html = '<html><head><script type="application/ld+json">{invalid</script></head></html>'
        results = _extract_json_ld(html)
        assert results == []

    def test_handles_list_json_ld(self):
        data = json.dumps(
            [{"@type": "Event", "name": "A"}, {"@type": "Event", "name": "B"}]
        )
        html = f'<html><head><script type="application/ld+json">{data}</script></head></html>'
        results = _extract_json_ld(html)
        assert len(results) == 2


# ── Test _parse_iso_datetime ────────────────────────────────────────


class TestParseIsoDatetime:
    """Tests for ISO datetime parsing."""

    def test_parses_offset_format(self):
        dt = _parse_iso_datetime("2026-03-07T20:00:00+01:00")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 7
        assert dt.hour == 20
        assert dt.tzinfo == PARIS_TZ

    def test_parses_z_format(self):
        dt = _parse_iso_datetime("2026-03-07T19:00:00Z")
        assert dt is not None
        assert dt.tzinfo == PARIS_TZ
        # UTC 19:00 = CET 20:00
        assert dt.hour == 20

    def test_parses_microseconds_z_format(self):
        dt = _parse_iso_datetime("2026-03-07T19:00:00.000000Z")
        assert dt is not None
        assert dt.hour == 20

    def test_returns_none_for_invalid(self):
        assert _parse_iso_datetime("not-a-date") is None

    def test_returns_none_for_empty(self):
        assert _parse_iso_datetime("") is None


# ── Test _extract_image_url ─────────────────────────────────────────


class TestExtractImageUrl:
    """Tests for image URL extraction from JSON-LD."""

    def test_image_as_dict(self):
        json_ld = {
            "image": {
                "@type": "ImageObject",
                "url": "https://example.com/img.jpg",
            }
        }
        assert _extract_image_url(json_ld) == "https://example.com/img.jpg"

    def test_image_as_string(self):
        json_ld = {"image": "https://example.com/img.jpg"}
        assert _extract_image_url(json_ld) == "https://example.com/img.jpg"

    def test_image_as_list(self):
        json_ld = {"image": ["https://example.com/a.jpg", "https://example.com/b.jpg"]}
        assert _extract_image_url(json_ld) == "https://example.com/a.jpg"

    def test_image_as_empty_list(self):
        assert _extract_image_url({"image": []}) is None

    def test_no_image(self):
        assert _extract_image_url({}) is None


# ── Test _extract_venue_name ────────────────────────────────────────


class TestExtractVenueName:
    """Tests for venue name extraction."""

    def test_extracts_venue_name(self):
        json_ld = {"location": {"@type": "Place", "name": "Espace Julien"}}
        assert _extract_venue_name(json_ld) == "Espace Julien"

    def test_extracts_le_makeda(self):
        json_ld = {"location": {"@type": "Place", "name": "Le Makeda"}}
        assert _extract_venue_name(json_ld) == "Le Makeda"

    def test_defaults_to_espace_julien(self):
        assert _extract_venue_name({}) == "Espace Julien"

    def test_handles_non_dict_location(self):
        json_ld = {"location": "Some string"}
        assert _extract_venue_name(json_ld) == "Espace Julien"


# ── Test _generate_source_id ────────────────────────────────────────


class TestGenerateSourceId:
    """Tests for source ID generation."""

    def test_generates_from_url(self):
        sid = _generate_source_id("https://espace-julien.com/agenda/oxmo-puccino")
        assert sid == "espacejulien:oxmo-puccino"

    def test_handles_trailing_slash(self):
        sid = _generate_source_id("https://espace-julien.com/agenda/test-event/")
        assert sid == "espacejulien:test-event"

    def test_handles_suffix(self):
        sid = _generate_source_id("https://espace-julien.com/agenda/ajar-0")
        assert sid == "espacejulien:ajar-0"


# ── Test EspaceJulienParser integration ─────────────────────────────


class TestEspaceJulienParserIntegration:
    """Integration tests for EspaceJulienParser with mocked HTTP."""

    def test_source_name(self, parser):
        assert parser.source_name == "Espace Julien"

    def test_parse_events_single_page(
        self, parser, sample_listing_html, sample_detail_html
    ):
        """Test parsing events from a single listing page."""
        # Page 1 pagination returns empty (stop), then 3 detail pages
        parser.http_client.get_text.side_effect = [
            "",  # Page 1 (pagination, empty = stop)
            sample_detail_html,  # Detail: oxmo-puccino
            sample_detail_html,  # Detail: paul-taylor
            sample_detail_html,  # Detail: lej
        ]

        html_parser = HTMLParser(
            sample_listing_html, "https://espace-julien.com/agenda"
        )
        events = parser.parse_events(html_parser)

        assert len(events) == 3
        assert all(isinstance(e, Event) for e in events)
        assert all(e.name == "OXMO PUCCINO" for e in events)

    def test_parse_events_maps_categories(
        self, parser, sample_listing_html, sample_detail_html
    ):
        """Test that categories from listing page badges are mapped."""
        parser.http_client.get_text.side_effect = [
            "",  # Pagination stop
            sample_detail_html,  # oxmo-puccino
            sample_detail_html,  # paul-taylor
            sample_detail_html,  # lej
        ]

        html_parser = HTMLParser(
            sample_listing_html, "https://espace-julien.com/agenda"
        )
        events = parser.parse_events(html_parser)

        # First event (oxmo) should have rap-hip-hop -> musique and festival -> communaute
        oxmo_event = events[0]
        assert (
            "musique" in oxmo_event.categories or "communaute" in oxmo_event.categories
        )

    def test_parse_events_maps_venue(
        self, parser, sample_detail_html, sample_makeda_detail_html
    ):
        """Test that venue names are mapped from JSON-LD location."""
        # Simple listing with one Espace Julien and one Le Makeda event
        listing_html = """
        <html><body>
            <div class="views-row">
                <a href="/agenda/oxmo-puccino">
                    <span class="badge" data-term-name="rap-hip-hop">Rap</span>
                </a>
            </div>
            <div class="views-row">
                <a href="/agenda/jazz-night">
                    <span class="badge" data-term-name="blues-jazz">Jazz</span>
                </a>
            </div>
        </body></html>
        """

        # Map URLs to responses for deterministic results
        url_responses = {
            "https://espace-julien.com/agenda/oxmo-puccino": sample_detail_html,
            "https://espace-julien.com/agenda/jazz-night": sample_makeda_detail_html,
        }

        def mock_get_text(url):
            return url_responses.get(url, "")

        parser.http_client.get_text.side_effect = mock_get_text

        html_parser = HTMLParser(listing_html, "https://espace-julien.com/agenda")
        events = parser.parse_events(html_parser)

        # Find the jazz event (Le Makeda venue)
        makeda_events = [e for e in events if e.name == "JAZZ NIGHT"]
        assert len(makeda_events) == 1
        assert "le-makeda" in makeda_events[0].locations

        # Espace Julien events
        ej_events = [e for e in events if e.name == "OXMO PUCCINO"]
        assert len(ej_events) == 1
        assert "espace-julien" in ej_events[0].locations

    def test_parse_events_empty_listing(self, parser):
        """Test graceful handling of empty listing page."""
        parser.http_client.get_text.return_value = ""

        html_parser = HTMLParser(
            "<html><body></body></html>", "https://espace-julien.com/agenda"
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_handles_detail_page_failure(self, parser):
        """Test graceful handling when detail page fails."""
        listing_html = """
        <html><body>
            <div class="views-row"><a href="/agenda/test-event">Test</a></div>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [
            "",  # Pagination stop
            "",  # Detail page fails
        ]

        html_parser = HTMLParser(listing_html, "https://espace-julien.com/agenda")
        events = parser.parse_events(html_parser)
        assert events == []

    def test_handles_detail_page_without_json_ld(self, parser):
        """Test handling of detail page without JSON-LD."""
        listing_html = """
        <html><body>
            <div class="views-row"><a href="/agenda/test-event">Test</a></div>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [
            "",  # Pagination stop
            "<html><head></head><body><h1>Test</h1></body></html>",
        ]

        html_parser = HTMLParser(listing_html, "https://espace-julien.com/agenda")
        events = parser.parse_events(html_parser)
        assert events == []

    def test_extracts_description_from_performer(self, parser, sample_detail_html):
        """Test description extraction from performer field in JSON-LD."""
        parser.http_client.get_text.side_effect = [
            "",  # Pagination stop
            sample_detail_html,
        ]

        listing_html = """
        <html><body>
            <div class="views-row">
                <a href="/agenda/oxmo-puccino">
                    <span class="badge" data-term-name="rap-hip-hop">Rap</span>
                </a>
            </div>
        </body></html>
        """
        html_parser = HTMLParser(listing_html, "https://espace-julien.com/agenda")
        events = parser.parse_events(html_parser)

        assert len(events) == 1
        assert "Oxmo Puccino" in events[0].description

    def test_extracts_performer_tags(self, parser, sample_detail_html):
        """Test that performer names are extracted as tags."""
        parser.http_client.get_text.side_effect = [
            "",  # Pagination stop
            sample_detail_html,
        ]

        listing_html = """
        <html><body>
            <div class="views-row">
                <a href="/agenda/oxmo-puccino">
                    <span class="badge" data-term-name="rap-hip-hop">Rap</span>
                </a>
            </div>
        </body></html>
        """
        html_parser = HTMLParser(listing_html, "https://espace-julien.com/agenda")
        events = parser.parse_events(html_parser)

        assert len(events) == 1
        # "oxmo puccino" is same as event name (lowered), so excluded
        # "tifol" should be included
        assert "tifol" in events[0].tags

    def test_source_id_format(self, parser, sample_detail_html):
        """Test that source IDs follow the expected format."""
        parser.http_client.get_text.side_effect = [
            "",  # Pagination stop
            sample_detail_html,
        ]

        listing_html = """
        <html><body>
            <div class="views-row">
                <a href="/agenda/oxmo-puccino">Oxmo</a>
            </div>
        </body></html>
        """
        html_parser = HTMLParser(listing_html, "https://espace-julien.com/agenda")
        events = parser.parse_events(html_parser)

        assert len(events) == 1
        assert events[0].source_id == "espacejulien:oxmo-puccino"

    def test_skips_past_events(self, parser):
        """Test that events with past dates are skipped."""
        past_json_ld = json.dumps(
            {
                "@type": "Event",
                "name": "PAST EVENT",
                "startDate": "2020-01-01T20:00:00+01:00",
                "location": {"@type": "Place", "name": "Espace Julien"},
                "image": "https://example.com/img.jpg",
            }
        )
        past_detail = f"""
        <html>
        <head><script type="application/ld+json">{past_json_ld}</script></head>
        <body><h1>PAST EVENT</h1></body>
        </html>
        """
        listing_html = """
        <html><body>
            <div class="views-row"><a href="/agenda/past-event">Past</a></div>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [
            "",  # Pagination stop
            past_detail,
        ]

        html_parser = HTMLParser(listing_html, "https://espace-julien.com/agenda")
        events = parser.parse_events(html_parser)
        assert events == []

    def test_fallback_to_keywords_for_categories(self, parser):
        """Test fallback to JSON-LD keywords when listing has no categories."""
        json_ld = json.dumps(
            {
                "@type": "Event",
                "name": "KEYWORD EVENT",
                "startDate": "2027-06-01T20:00:00+02:00",
                "location": {"@type": "Place", "name": "Espace Julien"},
                "keywords": "electro, rock",
                "image": "https://example.com/img.jpg",
            }
        )
        detail = f"""
        <html>
        <head><script type="application/ld+json">{json_ld}</script></head>
        <body><h1>KEYWORD EVENT</h1></body>
        </html>
        """
        listing_html = """
        <html><body>
            <div class="views-row"><a href="/agenda/keyword-event">Event</a></div>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [
            "",  # Pagination stop
            detail,
        ]

        html_parser = HTMLParser(listing_html, "https://espace-julien.com/agenda")
        events = parser.parse_events(html_parser)

        assert len(events) == 1
        assert "musique" in events[0].categories

    def test_default_category_for_music_venue(self, parser):
        """Test default to musique when no categories found."""
        json_ld = json.dumps(
            {
                "@type": "Event",
                "name": "NO CATEGORY EVENT",
                "startDate": "2027-06-01T20:00:00+02:00",
                "location": {"@type": "Place", "name": "Espace Julien"},
                "image": "https://example.com/img.jpg",
            }
        )
        detail = f"""
        <html>
        <head><script type="application/ld+json">{json_ld}</script></head>
        <body><h1>NO CATEGORY EVENT</h1></body>
        </html>
        """
        listing_html = """
        <html><body>
            <div class="views-row"><a href="/agenda/no-cat">Event</a></div>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [
            "",  # Pagination stop
            detail,
        ]

        html_parser = HTMLParser(listing_html, "https://espace-julien.com/agenda")
        events = parser.parse_events(html_parser)

        assert len(events) == 1
        assert events[0].categories == ["musique"]

    def test_pagination_stops_when_no_new_events(self, parser, sample_detail_html):
        """Test that pagination stops when a page yields no new events."""
        listing_html = """
        <html><body>
            <div class="views-row"><a href="/agenda/event-a">A</a></div>
        </body></html>
        """
        # Page 1 repeats same events (no new cards), page 2 never fetched
        parser.http_client.get_text.side_effect = [
            listing_html,  # Page 1 (same events as page 0)
            sample_detail_html,  # Detail for event-a
        ]

        html_parser = HTMLParser(listing_html, "https://espace-julien.com/agenda")
        events = parser.parse_events(html_parser)

        assert len(events) == 1
