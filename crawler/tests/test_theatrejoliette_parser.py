"""Tests for the Théâtre Joliette parser."""

import json
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.theatrejoliette import (
    TheatreJolietteParser,
    _extract_category_from_html,
    _extract_description_from_html,
    _extract_event_urls,
    _extract_json_ld,
    _extract_showtimes,
    _generate_source_id,
    _parse_iso_date,
)
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_listing_html():
    """Sample Théâtre Joliette listing page with event tiles."""
    return """
    <html>
    <body>
        <h2>Événements à venir</h2>
        <div class="tile_item tile_simple">
            <a href="/programmation/25-26/minga-de-una-casa-en-ruinas">
                <div class="image__contain"></div>
                <div class="tile__inner">
                    <span class="label_status">théâtre</span>
                    <h3>Minga de una casa en ruinas</h3>
                    <time>19-20 mars 2026</time>
                </div>
            </a>
        </div>
        <div class="tile_item tile_simple">
            <a href="/programmation/25-26/good-sex">
                <div class="image__contain"></div>
                <div class="tile__inner">
                    <span class="label_status">théâtre</span>
                    <h3>Good Sex</h3>
                    <time>24-27 mars 2026</time>
                </div>
            </a>
        </div>
        <div class="tile_item tile_simple">
            <a href="/programmation/25-26/ni-ni-ya-mo-mo">
                <div class="image__contain"></div>
                <div class="tile__inner">
                    <span class="label_status">danse</span>
                    <h3>Ni ni ya mo mo</h3>
                    <time>20 mai 2026</time>
                </div>
            </a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_html():
    """Sample Théâtre Joliette event detail page with JSON-LD and showtimes."""
    json_ld = json.dumps(
        {
            "@type": "Event",
            "name": "MINGA DE UNA CASA EN RUINAS",
            "eventStatus": "EventScheduled",
            "url": "https://www.theatrejoliette.fr/programmation/25-26/minga-de-una-casa-en-ruinas",
            "description": "Sur l'île de Chiloé, au sud du Chili, la minga est un rituel communautaire ancestral.",
            "image": "https://www.theatrejoliette.fr/media/pages/programmation/25-26/minga/minga.jpg",
            "startDate": "2026-03-19",
            "endDate": "2026-03-20",
            "offers": {
                "@type": "Offer",
                "availability": "https://schema.org/InStock",
                "url": "https://theatrejoliette.notre-billetterie.fr/billets?spec=722",
            },
            "location": {
                "type": "Place",
                "name": "Théâtre Joliette",
                "address": {
                    "streetAddress": "2 place Henri Verneuil",
                    "postalCode": "F-13002",
                    "addressLocality": "Marseille, France",
                },
            },
        }
    )
    return f"""
    <html>
    <head>
        <meta name="description" content="Sur l'île de Chiloé, au sud du Chili, la minga est un rituel communautaire.">
        <script type="application/ld+json">{json_ld}</script>
    </head>
    <body>
        <h1 class="heading__page">MINGA DE UNA CASA EN RUINAS</h1>
        <ul>
            <li>théâtre</li>
            <li>à partir de 12 ans</li>
            <li>Durée : 1h30</li>
        </ul>
        <span class="label_status">théâtre</span>
        <h3>Séances</h3>
        <p>grande salle</p>
        <ul>
            <li>jeudi 19 mars 2026 à 19h</li>
            <li>vendredi 20 mars 2026 à 21h</li>
        </ul>
        <p>Sur l'île de Chiloé, au sud du Chili, la minga est un rituel.</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_no_showtimes():
    """Detail page with JSON-LD but no individual showtimes in HTML."""
    json_ld = json.dumps(
        {
            "@type": "Event",
            "name": "Good Sex",
            "startDate": "2026-03-24",
            "endDate": "2026-03-27",
            "description": "Un spectacle audacieux.",
            "image": "https://www.theatrejoliette.fr/media/good-sex.jpg",
        }
    )
    return f"""
    <html>
    <head>
        <script type="application/ld+json">{json_ld}</script>
    </head>
    <body>
        <h1>Good Sex</h1>
        <span class="label_status">théâtre</span>
        <p>Un spectacle audacieux et provocateur.</p>
    </body>
    </html>
    """


@pytest.fixture
def category_map():
    """Standard category mapping for Théâtre Joliette."""
    return {
        "théâtre": "theatre",
        "theatre": "theatre",
        "danse": "danse",
        "poésie": "communaute",
        "marionnette": "theatre",
        "cirque": "theatre",
        "performance": "theatre",
        "slam": "communaute",
    }


# ── Test _extract_event_urls ────────────────────────────────────────


class TestExtractEventUrls:
    """Tests for extracting event URLs from listing page."""

    def test_extracts_event_urls(self, sample_listing_html):
        parser = HTMLParser(
            sample_listing_html,
            "https://www.theatrejoliette.fr/programmation/25-26",
        )
        urls = _extract_event_urls(parser)
        assert len(urls) == 3
        assert any("minga" in u for u in urls)
        assert any("good-sex" in u for u in urls)
        assert any("ni-ni-ya-mo-mo" in u for u in urls)

    def test_resolves_relative_urls(self, sample_listing_html):
        parser = HTMLParser(
            sample_listing_html,
            "https://www.theatrejoliette.fr/programmation/25-26",
        )
        urls = _extract_event_urls(parser)
        for url in urls:
            assert url.startswith("https://")

    def test_handles_empty_html(self):
        parser = HTMLParser(
            "<html><body></body></html>",
            "https://www.theatrejoliette.fr/programmation/25-26",
        )
        urls = _extract_event_urls(parser)
        assert urls == []

    def test_deduplicates_urls(self):
        html = """
        <div class="tile_item tile_simple">
            <a href="/programmation/25-26/test-event">Link 1</a>
        </div>
        <div class="tile_item tile_simple">
            <a href="/programmation/25-26/test-event">Link 2</a>
        </div>
        """
        parser = HTMLParser(
            html,
            "https://www.theatrejoliette.fr/programmation/25-26",
        )
        urls = _extract_event_urls(parser)
        assert len(urls) == 1


# ── Test _extract_json_ld ───────────────────────────────────────────


class TestExtractJsonLd:
    """Tests for extracting JSON-LD Event data from HTML."""

    def test_extracts_direct_event(self, sample_detail_html):
        result = _extract_json_ld(sample_detail_html)
        assert result is not None
        assert result["@type"] == "Event"
        assert result["name"] == "MINGA DE UNA CASA EN RUINAS"

    def test_extracts_main_entity_event(self):
        json_ld = json.dumps(
            {
                "@type": "WebPage",
                "mainEntity": {
                    "@type": "Event",
                    "name": "Nested Event",
                },
            }
        )
        html = f'<html><head><script type="application/ld+json">{json_ld}</script></head></html>'
        result = _extract_json_ld(html)
        assert result is not None
        assert result["name"] == "Nested Event"

    def test_handles_no_json_ld(self):
        html = "<html><head></head><body></body></html>"
        result = _extract_json_ld(html)
        assert result is None

    def test_handles_invalid_json(self):
        html = '<html><head><script type="application/ld+json">{invalid</script></head></html>'
        result = _extract_json_ld(html)
        assert result is None


# ── Test _parse_iso_date ────────────────────────────────────────────


class TestParseIsoDate:
    """Tests for ISO date parsing."""

    def test_parses_basic_date(self):
        dt = _parse_iso_date("2026-03-19")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 19
        assert dt.tzinfo == PARIS_TZ

    def test_parses_date_with_time(self):
        dt = _parse_iso_date("2026-03-19T20:00:00")
        assert dt is not None
        assert dt.day == 19

    def test_returns_none_for_invalid(self):
        assert _parse_iso_date("not-a-date") is None

    def test_returns_none_for_empty(self):
        assert _parse_iso_date("") is None


# ── Test _extract_showtimes ─────────────────────────────────────────


class TestExtractShowtimes:
    """Tests for extracting individual showtimes from HTML."""

    def test_extracts_multiple_showtimes(self):
        html = """
        <ul>
            <li>jeudi 19 mars 2026 à 19h</li>
            <li>vendredi 20 mars 2026 à 21h</li>
        </ul>
        """
        showtimes = _extract_showtimes(html)
        assert len(showtimes) == 2
        assert showtimes[0].day == 19
        assert showtimes[0].hour == 19
        assert showtimes[0].minute == 0
        assert showtimes[1].day == 20
        assert showtimes[1].hour == 21

    def test_extracts_time_with_minutes(self):
        html = "<li>samedi 21 mars 2026 à 20h30</li>"
        showtimes = _extract_showtimes(html)
        assert len(showtimes) == 1
        assert showtimes[0].hour == 20
        assert showtimes[0].minute == 30

    def test_handles_no_showtimes(self):
        html = "<p>No schedule information</p>"
        showtimes = _extract_showtimes(html)
        assert showtimes == []

    def test_handles_various_months(self):
        html = """
        <li>lundi 5 janvier 2026 à 20h</li>
        <li>mardi 3 février 2026 à 19h</li>
        <li>mercredi 1 avril 2026 à 18h30</li>
        """
        showtimes = _extract_showtimes(html)
        assert len(showtimes) == 3
        assert showtimes[0].month == 1
        assert showtimes[1].month == 2
        assert showtimes[2].month == 4


# ── Test _extract_category_from_html ────────────────────────────────


class TestExtractCategoryFromHtml:
    """Tests for category extraction from HTML."""

    def test_extracts_from_label_status(self):
        html = '<span class="label_status">danse</span>'
        category = _extract_category_from_html(html)
        assert category == "danse"

    def test_returns_none_for_no_category(self):
        html = "<html><body><p>No category</p></body></html>"
        category = _extract_category_from_html(html)
        assert category is None

    def test_extracts_lowercase(self):
        html = '<span class="label_status">Théâtre</span>'
        category = _extract_category_from_html(html)
        assert category == "théâtre"


# ── Test _extract_description_from_html ─────────────────────────────


class TestExtractDescriptionFromHtml:
    """Tests for description extraction from HTML."""

    def test_extracts_from_meta(self):
        html = """
        <html>
        <head>
            <meta name="description" content="A wonderful theatre performance with amazing actors.">
        </head>
        <body></body>
        </html>
        """
        description = _extract_description_from_html(html)
        assert "wonderful theatre" in description

    def test_truncates_long_description(self):
        long_text = "A" * 300
        html = f"""
        <html>
        <head>
            <meta name="description" content="{long_text}">
        </head>
        </html>
        """
        description = _extract_description_from_html(html)
        assert len(description) <= 160

    def test_falls_back_to_paragraph(self):
        html = """
        <html><body>
            <p>This is a substantial paragraph with enough text to be considered a description.</p>
        </body></html>
        """
        description = _extract_description_from_html(html)
        assert "substantial paragraph" in description


# ── Test _generate_source_id ────────────────────────────────────────


class TestGenerateSourceId:
    """Tests for source ID generation."""

    def test_generates_from_url(self):
        sid = _generate_source_id(
            "https://www.theatrejoliette.fr/programmation/25-26/minga-de-una-casa-en-ruinas"
        )
        assert sid == "theatrejoliette:minga-de-una-casa-en-ruinas"

    def test_generates_from_url_with_trailing_slash(self):
        sid = _generate_source_id(
            "https://www.theatrejoliette.fr/programmation/25-26/good-sex/"
        )
        assert sid == "theatrejoliette:good-sex"


# ── Test TheatreJolietteParser integration ──────────────────────────


class TestTheatreJolietteParserIntegration:
    """Integration tests for TheatreJolietteParser with mocked HTTP."""

    @pytest.fixture
    def mock_config(self, category_map):
        return {
            "name": "Théâtre Joliette",
            "id": "theatrejoliette",
            "url": "https://www.theatrejoliette.fr/programmation/25-26",
            "parser": "theatrejoliette",
            "rate_limit": {"delay_between_pages": 0.0},
            "category_map": category_map,
        }

    @pytest.fixture
    def parser(self, mock_config):
        return TheatreJolietteParser(
            config=mock_config,
            http_client=MagicMock(),
            image_downloader=MagicMock(),
            markdown_generator=MagicMock(),
        )

    def test_source_name(self, parser):
        assert "Joliette" in parser.source_name

    def test_parse_detail_page_with_showtimes(self, parser, sample_detail_html):
        """Test parsing a detail page with individual showtimes."""
        events = parser._parse_detail_page(
            "https://www.theatrejoliette.fr/programmation/25-26/minga-de-una-casa-en-ruinas",
            html=sample_detail_html,
        )

        assert len(events) == 2
        assert all(isinstance(e, Event) for e in events)
        assert events[0].name == "MINGA DE UNA CASA EN RUINAS"
        assert events[0].start_datetime.day == 19
        assert events[0].start_datetime.hour == 19
        assert events[1].start_datetime.day == 20
        assert events[1].start_datetime.hour == 21
        assert all("theatre-joliette" in e.locations for e in events)
        assert all("theatre" in e.categories for e in events)

    def test_multi_day_events_have_group_id(self, parser, sample_detail_html):
        """Test that multi-day events share a group ID."""
        events = parser._parse_detail_page(
            "https://www.theatrejoliette.fr/programmation/25-26/minga-de-una-casa-en-ruinas",
            html=sample_detail_html,
        )

        assert len(events) == 2
        assert events[0].event_group_id is not None
        assert events[0].event_group_id == events[1].event_group_id
        assert events[0].day_of == "Jour 1 sur 2"
        assert events[1].day_of == "Jour 2 sur 2"

    def test_parse_detail_page_no_showtimes_fallback(
        self, parser, sample_detail_no_showtimes
    ):
        """Test fallback to JSON-LD startDate when no showtimes found."""
        events = parser._parse_detail_page(
            "https://www.theatrejoliette.fr/programmation/25-26/good-sex",
            html=sample_detail_no_showtimes,
        )

        assert len(events) == 1
        assert events[0].name == "Good Sex"
        assert events[0].start_datetime.day == 24
        assert events[0].start_datetime.hour == 20  # Default time
        assert events[0].event_group_id is None  # Single event, no group

    def test_parse_detail_page_no_json_ld(self, parser):
        """Test graceful handling of pages without JSON-LD."""
        html = "<html><body><h1>Test</h1></body></html>"
        events = parser._parse_detail_page(
            "https://www.theatrejoliette.fr/programmation/25-26/test",
            html=html,
        )
        assert events == []

    def test_parse_detail_page_empty_html(self, parser):
        """Test graceful handling of empty HTML."""
        events = parser._parse_detail_page(
            "https://www.theatrejoliette.fr/programmation/25-26/test",
            html="",
        )
        assert events == []

    def test_parse_events_full_flow(
        self, parser, sample_listing_html, sample_detail_html
    ):
        """Test full parsing flow: listing -> detail pages."""
        parser.http_client.get_text.return_value = sample_detail_html

        listing_parser = HTMLParser(
            sample_listing_html,
            "https://www.theatrejoliette.fr/programmation/25-26",
        )
        events = parser.parse_events(listing_parser)

        assert len(events) > 0
        assert all(isinstance(e, Event) for e in events)

    def test_parse_events_empty_listing(self, parser):
        """Test graceful handling of empty listing page."""
        listing_parser = HTMLParser(
            "<html><body></body></html>",
            "https://www.theatrejoliette.fr/programmation/25-26",
        )
        events = parser.parse_events(listing_parser)
        assert events == []

    def test_category_mapping(self, parser):
        """Test that categories are correctly mapped."""
        json_ld = json.dumps(
            {
                "@type": "Event",
                "name": "Dance Show",
                "startDate": "2026-06-01",
                "description": "A dance performance.",
            }
        )
        html = f"""
        <html>
        <head><script type="application/ld+json">{json_ld}</script></head>
        <body>
            <span class="label_status">danse</span>
            <h1>Dance Show</h1>
        </body>
        </html>
        """
        events = parser._parse_detail_page(
            "https://www.theatrejoliette.fr/programmation/25-26/dance-show",
            html=html,
        )

        assert len(events) == 1
        assert "danse" in events[0].categories

    def test_image_extraction(self, parser, sample_detail_html):
        """Test that image is extracted from JSON-LD."""
        events = parser._parse_detail_page(
            "https://www.theatrejoliette.fr/programmation/25-26/minga-de-una-casa-en-ruinas",
            html=sample_detail_html,
        )

        assert len(events) > 0
        assert events[0].image is not None
        assert "minga" in events[0].image

    def test_description_from_json_ld(self, parser, sample_detail_html):
        """Test that description is extracted from JSON-LD."""
        events = parser._parse_detail_page(
            "https://www.theatrejoliette.fr/programmation/25-26/minga-de-una-casa-en-ruinas",
            html=sample_detail_html,
        )

        assert len(events) > 0
        assert "Chiloé" in events[0].description

    def test_source_id_format(self, parser, sample_detail_html):
        """Test that source IDs follow the expected format."""
        events = parser._parse_detail_page(
            "https://www.theatrejoliette.fr/programmation/25-26/minga-de-una-casa-en-ruinas",
            html=sample_detail_html,
        )

        assert len(events) > 0
        for event in events:
            assert event.source_id.startswith("theatrejoliette:")
