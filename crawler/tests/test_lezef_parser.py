"""Tests for the Le Zef - Scene nationale de Marseille parser."""

import json
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.lezef import (
    LeZefParser,
    _extract_category_from_html,
    _extract_description_from_html,
    _extract_event_urls_from_ajax_html,
    _extract_json_ld,
    _extract_performer_from_html,
    _extract_time_from_html,
    _generate_source_id,
    _parse_iso_date,
)
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_ajax_html():
    """Sample Le Zef AJAX listing response with event cards."""
    return """
    <section id="septembre-2025" class="mois">
        <header>
            <h1>septembre <span class="annee">2025</span></h1>
        </header>
        <div class="container">
            <div>
                <article class="item-event en-cours">
                    <figure class="embed-responsive embed-responsive-16by9 thumbnail-item">
                        <a href="https://www.lezef.org/fr/saison/25-26/l-oeil-noir-898">
                            <img class="embed-responsive-item"
                                src="data:image/gif;base64,..."
                                data-src="https://www.lezef.org/public_data/diapo/event/1739961132/800/rita_web.jpg" />
                        </a>
                    </figure>
                    <div class="description">
                        <header>
                            <p class="date">du mardi 25 2025 au vendredi 13 février 2026</p>
                            <p class="category">
                                <a href="https://www.lezef.org/fr/saison/25-26?genres=expo" class="expo">EXPO</a>
                            </p>
                            <h2><a href="https://www.lezef.org/fr/saison/25-26/l-oeil-noir-898">
                            L'œil noir</a></h2>
                            <p class="artiste">Yohanne Lamoulère</p>
                        </header>
                    </div>
                </article>
                <article class="item-event">
                    <figure class="embed-responsive embed-responsive-16by9 thumbnail-item">
                        <a href="https://www.lezef.org/fr/saison/25-26/opening-festival-964">
                            <img class="embed-responsive-item"
                                data-src="https://www.lezef.org/public_data/diapo/event/opening.jpg" />
                        </a>
                    </figure>
                    <div class="description">
                        <header>
                            <p class="date">Le mardi 23 septembre 2025 à 19h</p>
                            <p class="category">
                                <a href="?genres=danse" class="danse">DANSE</a>
                                <a href="?genres=musique" class="musique">MUSIQUE</a>
                            </p>
                            <h2><a href="https://www.lezef.org/fr/saison/25-26/opening-festival-964">
                            Ouverture !</a></h2>
                            <p class="artiste">Pierre Rigal</p>
                            <p class="compagnie">Ensemble C Barré</p>
                        </header>
                    </div>
                </article>
            </div>
        </div>
    </section>
    """


@pytest.fixture
def sample_detail_html():
    """Sample Le Zef event detail page with JSON-LD."""
    json_ld = json.dumps(
        {
            "@type": "WebPage",
            "name": "L'œil noir",
            "mainEntity": {
                "@type": "Event",
                "name": "L'œil noir ",
                "url": "https://www.lezef.org/fr/saison/25-26/l-oeil-noir-898",
                "description": "Premier film de Yohanne Lamoulère, L'œil noir est le fruit de plusieurs années d'un travail photographique.",
                "image": "https://www.lezef.org/public_data/diapo/event/1739961132/640/rita_web.jpg",
                "location": {
                    "@type": "PerformingArtsTheater",
                    "name": "Le Zef : Merlan",
                    "address": {
                        "@type": "PostalAddress",
                        "streetAddress": "Avenue Raimu",
                        "addressLocality": "Marseille, France",
                        "postalCode": "F-13014",
                    },
                },
                "performer": [
                    {"@type": "Person", "name": "Yohanne Lamoulère"},
                    {"@type": "PerformingGroup", "name": "Tendance Floue"},
                ],
                "startDate": "2025-09-23",
                "endDate": "2026-02-25",
            },
        }
    )
    return f"""
    <html>
    <head>
        <meta name="description" content="L'œil noir est le fruit de plusieurs années d'un travail photographique...">
        <script type="application/ld+json">{json_ld}</script>
    </head>
    <body>
        <nav>
            <p class="date">du mardi 25 2025 au vendredi 13 février 2026</p>
            <p class="category">
                <a href="?genres=expo" class="expo">EXPO</a>
            </p>
            <h1>L'œil noir</h1>
            <p class="artiste">Yohanne Lamoulère</p>
            <p class="compagnie">Tendance Floue</p>
        </nav>
        <div id="presentation">
            <p>Premier film de Yohanne Lamoulère...</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_with_time():
    """Sample detail page with specific showtime."""
    json_ld = json.dumps(
        {
            "@type": "WebPage",
            "mainEntity": {
                "@type": "Event",
                "name": "Concert Test",
                "startDate": "2026-03-15",
                "description": "Un concert magnifique.",
                "image": "https://www.lezef.org/img/concert.jpg",
            },
        }
    )
    return f"""
    <html>
    <head>
        <script type="application/ld+json">{json_ld}</script>
    </head>
    <body>
        <p class="date">Le dimanche 15 mars 2026 à 20h30</p>
        <p class="category">
            <a href="?genres=musique" class="musique">MUSIQUE</a>
        </p>
        <h1>Concert Test</h1>
        <p class="artiste">Artiste Principal</p>
    </body>
    </html>
    """


@pytest.fixture
def category_map():
    """Standard category mapping from sources.yaml."""
    return {
        "danse": "danse",
        "DANSE": "danse",
        "musique": "musique",
        "MUSIQUE": "musique",
        "theatre": "theatre",
        "THEATRE": "theatre",
        "expo": "art",
        "EXPO": "art",
        "cuisine": "communaute",
        "CUISINE": "communaute",
        "cirque": "theatre",
        "CIRQUE": "theatre",
    }


# ── Test _extract_event_urls_from_ajax_html ───────────────────────


class TestExtractEventUrlsFromAjax:
    """Tests for extracting event URLs from AJAX listing response."""

    def test_extracts_event_urls(self, sample_ajax_html):
        urls = _extract_event_urls_from_ajax_html(
            sample_ajax_html, "https://www.lezef.org"
        )
        assert len(urls) == 2
        assert any("l-oeil-noir-898" in u for u in urls)
        assert any("opening-festival-964" in u for u in urls)

    def test_handles_absolute_urls(self, sample_ajax_html):
        urls = _extract_event_urls_from_ajax_html(
            sample_ajax_html, "https://www.lezef.org"
        )
        for url in urls:
            assert url.startswith("https://")

    def test_handles_relative_urls(self):
        html = """
        <article class="item-event">
            <figure>
                <a href="/fr/saison/25-26/test-event">
                    <img />
                </a>
            </figure>
        </article>
        """
        urls = _extract_event_urls_from_ajax_html(html, "https://www.lezef.org")
        assert len(urls) == 1
        assert urls[0] == "https://www.lezef.org/fr/saison/25-26/test-event"

    def test_handles_empty_html(self):
        urls = _extract_event_urls_from_ajax_html("<html><body></body></html>")
        assert urls == []

    def test_deduplicates_urls(self):
        html = """
        <article class="item-event">
            <figure><a href="https://www.lezef.org/fr/saison/25-26/test">Link 1</a></figure>
        </article>
        <article class="item-event">
            <figure><a href="https://www.lezef.org/fr/saison/25-26/test">Link 2</a></figure>
        </article>
        """
        urls = _extract_event_urls_from_ajax_html(html, "https://www.lezef.org")
        assert len(urls) == 1


# ── Test _extract_json_ld ─────────────────────────────────────────


class TestExtractJsonLd:
    """Tests for extracting JSON-LD Event data from HTML."""

    def test_extracts_event_from_main_entity(self, sample_detail_html):
        result = _extract_json_ld(sample_detail_html)
        assert result is not None
        assert result["@type"] == "Event"
        assert result["name"] == "L'œil noir "

    def test_handles_no_json_ld(self):
        html = "<html><head></head><body></body></html>"
        result = _extract_json_ld(html)
        assert result is None

    def test_handles_invalid_json(self):
        html = '<html><head><script type="application/ld+json">{invalid</script></head></html>'
        result = _extract_json_ld(html)
        assert result is None

    def test_extracts_direct_event(self):
        json_ld = json.dumps({"@type": "Event", "name": "Direct Event"})
        html = f'<html><head><script type="application/ld+json">{json_ld}</script></head></html>'
        result = _extract_json_ld(html)
        assert result is not None
        assert result["name"] == "Direct Event"


# ── Test _parse_iso_date ──────────────────────────────────────────


class TestParseIsoDate:
    """Tests for ISO date parsing."""

    def test_parses_basic_date(self):
        dt = _parse_iso_date("2026-03-15")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 15
        assert dt.tzinfo == PARIS_TZ

    def test_parses_date_with_time(self):
        dt = _parse_iso_date("2026-03-15T20:00:00")
        assert dt is not None
        assert dt.year == 2026
        assert dt.day == 15

    def test_returns_none_for_invalid(self):
        dt = _parse_iso_date("not-a-date")
        assert dt is None

    def test_returns_none_for_empty(self):
        dt = _parse_iso_date("")
        assert dt is None


# ── Test _extract_time_from_html ─────────────────────────────────


class TestExtractTimeFromHtml:
    """Tests for extracting time from HTML."""

    def test_extracts_time_with_minutes(self):
        html = "<p class='date'>Le dimanche 15 mars 2026 à 20h30</p>"
        result = _extract_time_from_html(html)
        assert result == (20, 30)

    def test_extracts_time_without_minutes(self):
        html = "<p class='date'>Le dimanche 15 mars 2026 à 19h</p>"
        result = _extract_time_from_html(html)
        assert result == (19, 0)

    def test_handles_no_time(self):
        html = "<p class='date'>du mardi 25 au vendredi 13 février 2026</p>"
        result = _extract_time_from_html(html)
        assert result is None

    def test_extracts_time_case_insensitive(self):
        html = "<p>LE CONCERT À 21H00</p>"
        result = _extract_time_from_html(html)
        assert result == (21, 0)


# ── Test _extract_category_from_html ─────────────────────────────


class TestExtractCategoryFromHtml:
    """Tests for category extraction from HTML."""

    def test_extracts_category(self, sample_detail_html):
        category = _extract_category_from_html(sample_detail_html)
        assert category == "expo"

    def test_handles_no_category(self):
        html = "<html><body><p>No category</p></body></html>"
        category = _extract_category_from_html(html)
        assert category is None

    def test_extracts_first_category(self):
        html = """
        <p class="category">
            <a class="danse">DANSE</a>
            <a class="musique">MUSIQUE</a>
        </p>
        """
        category = _extract_category_from_html(html)
        assert category == "danse"


# ── Test _extract_description_from_html ───────────────────────────


class TestExtractDescriptionFromHtml:
    """Tests for description extraction from HTML."""

    def test_extracts_from_meta(self):
        html = """
        <html>
        <head>
            <meta name="description" content="A great event with amazing performances.">
        </head>
        <body></body>
        </html>
        """
        description = _extract_description_from_html(html)
        assert "great event" in description

    def test_extracts_from_presentation(self):
        html = """
        <html><body>
            <div id="presentation">
                <p>This is a wonderful exhibition featuring local artists.</p>
            </div>
        </body></html>
        """
        description = _extract_description_from_html(html)
        assert "wonderful exhibition" in description

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


# ── Test _extract_performer_from_html ────────────────────────────


class TestExtractPerformerFromHtml:
    """Tests for performer extraction from HTML."""

    def test_extracts_artiste(self):
        html = """
        <html><body>
            <p class="artiste">Pierre Rigal</p>
        </body></html>
        """
        performers = _extract_performer_from_html(html)
        assert "pierre rigal" in performers

    def test_extracts_compagnie(self):
        html = """
        <html><body>
            <p class="compagnie">Ensemble C Barré</p>
        </body></html>
        """
        performers = _extract_performer_from_html(html)
        assert "ensemble c barré" in performers

    def test_extracts_both(self, sample_detail_html):
        performers = _extract_performer_from_html(sample_detail_html)
        assert len(performers) >= 1

    def test_limits_to_five(self):
        html = """
        <html><body>
            <p class="artiste">Artist 1</p>
            <p class="artiste">Artist 2</p>
            <p class="artiste">Artist 3</p>
            <p class="artiste">Artist 4</p>
            <p class="artiste">Artist 5</p>
            <p class="artiste">Artist 6</p>
        </body></html>
        """
        performers = _extract_performer_from_html(html)
        assert len(performers) <= 5


# ── Test _generate_source_id ──────────────────────────────────────


class TestGenerateSourceId:
    """Tests for source ID generation."""

    def test_generates_from_url(self):
        sid = _generate_source_id(
            "https://www.lezef.org/fr/saison/25-26/l-oeil-noir-898"
        )
        assert sid == "lezef:l-oeil-noir-898"

    def test_generates_from_url_with_trailing_slash(self):
        sid = _generate_source_id(
            "https://www.lezef.org/fr/saison/25-26/opening-festival-964/"
        )
        assert sid == "lezef:opening-festival-964"


# ── Test LeZefParser integration ─────────────────────────────────


class TestLeZefParserIntegration:
    """Integration tests for LeZefParser with mocked HTTP."""

    @pytest.fixture
    def mock_config(self, category_map):
        return {
            "name": "Le Zef - Scene nationale de Marseille",
            "id": "lezef",
            "url": "https://www.lezef.org/fr/saison/25-26",
            "parser": "lezef",
            "rate_limit": {"delay_between_pages": 0.0},
            "category_map": category_map,
        }

    @pytest.fixture
    def parser(self, mock_config):
        http_client = MagicMock()
        image_downloader = MagicMock()
        markdown_generator = MagicMock()
        return LeZefParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=image_downloader,
            markdown_generator=markdown_generator,
        )

    def test_source_name(self, parser):
        # source_name is overridden by config name
        assert "Le Zef" in parser.source_name

    def test_fetch_ajax_events(self, parser, sample_ajax_html):
        """Test AJAX endpoint is called correctly."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.text = sample_ajax_html
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = parser._fetch_ajax_events()

            assert result == sample_ajax_html
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "saison_ajax" in call_args.args[0]
            assert call_args.kwargs["data"]["saisonAddr"] == "25-26"

    def test_parse_events_with_detail_pages(
        self, parser, sample_ajax_html, sample_detail_with_time
    ):
        """Test full parsing flow with mocked HTTP."""
        with patch("requests.post") as mock_post:
            # Mock AJAX response
            mock_ajax_response = MagicMock()
            mock_ajax_response.text = sample_ajax_html
            mock_ajax_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_ajax_response

            # Mock detail page fetches
            parser.http_client.get_text.return_value = sample_detail_with_time

            html_parser = HTMLParser(
                "<html></html>", "https://www.lezef.org/fr/saison/25-26"
            )
            events = parser.parse_events(html_parser)

            # We have 2 event URLs from AJAX, both should be parsed
            assert len(events) > 0
            assert all(isinstance(e, Event) for e in events)

    def test_parse_events_empty_ajax(self, parser):
        """Test graceful handling of empty AJAX response."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.text = "<html><body></body></html>"
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            html_parser = HTMLParser(
                "<html></html>", "https://www.lezef.org/fr/saison/25-26"
            )
            events = parser.parse_events(html_parser)
            assert events == []

    def test_parse_detail_page(self, parser, sample_detail_with_time):
        """Test parsing a single detail page."""
        parser.http_client.get_text.return_value = sample_detail_with_time

        event = parser._parse_detail_page(
            "https://www.lezef.org/fr/saison/25-26/concert-test-123"
        )

        assert event is not None
        assert event.name == "Concert Test"
        assert event.start_datetime.year == 2026
        assert event.start_datetime.month == 3
        assert event.start_datetime.hour == 20
        assert event.start_datetime.minute == 30
        assert "musique" in event.categories
        assert "le-zef-theatre-du-merlan" in event.locations

    def test_parse_detail_page_failure(self, parser):
        """Test graceful handling of failed detail page fetch."""
        parser.http_client.get_text.return_value = ""

        event = parser._parse_detail_page(
            "https://www.lezef.org/fr/saison/25-26/test-event"
        )
        assert event is None

    def test_parse_detail_page_no_json_ld(self, parser):
        """Test handling of detail page without JSON-LD."""
        parser.http_client.get_text.return_value = "<html><body><h1>Test</h1></body></html>"

        event = parser._parse_detail_page(
            "https://www.lezef.org/fr/saison/25-26/test-event"
        )
        assert event is None

    def test_default_time_when_not_found(self, parser):
        """Test that default time 20:00 is used when not found in HTML."""
        json_ld = json.dumps(
            {
                "@type": "WebPage",
                "mainEntity": {
                    "@type": "Event",
                    "name": "Test Event",
                    "startDate": "2026-05-01",
                    "description": "Test",
                },
            }
        )
        html = f"""
        <html>
        <head><script type="application/ld+json">{json_ld}</script></head>
        <body>
            <p class="date">du vendredi 1er au dimanche 3 mai 2026</p>
            <p class="category"><a class="theatre">THEATRE</a></p>
        </body>
        </html>
        """
        parser.http_client.get_text.return_value = html

        event = parser._parse_detail_page(
            "https://www.lezef.org/fr/saison/25-26/test-event"
        )

        assert event is not None
        assert event.start_datetime.hour == 20
        assert event.start_datetime.minute == 0

    def test_category_mapping(self, parser):
        """Test that categories are correctly mapped."""
        # Create a detail page with a future date
        json_ld = json.dumps(
            {
                "@type": "WebPage",
                "mainEntity": {
                    "@type": "Event",
                    "name": "Exposition Test",
                    "startDate": "2026-06-01",
                    "description": "Une exposition magnifique.",
                },
            }
        )
        html = f"""
        <html>
        <head><script type="application/ld+json">{json_ld}</script></head>
        <body>
            <p class="category"><a class="expo">EXPO</a></p>
            <h1>Exposition Test</h1>
        </body>
        </html>
        """
        parser.http_client.get_text.return_value = html

        event = parser._parse_detail_page(
            "https://www.lezef.org/fr/saison/25-26/exposition-test"
        )

        # "expo" should map to "art"
        assert event is not None
        assert "art" in event.categories

    def test_performers_in_tags(self, parser):
        """Test that performers are added to tags."""
        # Create a detail page with performers
        json_ld = json.dumps(
            {
                "@type": "WebPage",
                "mainEntity": {
                    "@type": "Event",
                    "name": "Concert Test",
                    "startDate": "2026-06-15",
                    "description": "Un concert magnifique.",
                    "performer": [
                        {"@type": "Person", "name": "Artiste Principal"},
                        {"@type": "PerformingGroup", "name": "Le Groupe"},
                    ],
                },
            }
        )
        html = f"""
        <html>
        <head><script type="application/ld+json">{json_ld}</script></head>
        <body>
            <p class="category"><a class="musique">MUSIQUE</a></p>
            <h1>Concert Test</h1>
            <p class="artiste">Artiste Principal</p>
            <p class="compagnie">Le Groupe</p>
        </body>
        </html>
        """
        parser.http_client.get_text.return_value = html

        event = parser._parse_detail_page(
            "https://www.lezef.org/fr/saison/25-26/concert-test"
        )

        assert event is not None
        # Performers should be in tags (lowercase)
        tags_lower = [t.lower() for t in event.tags]
        assert any("artiste" in t for t in tags_lower) or any(
            "groupe" in t for t in tags_lower
        )

    def test_ongoing_exhibition_uses_today(self, parser):
        """Test that ongoing exhibitions with past startDate use today's date."""
        # Create an exhibition that started in the past but ends in the future
        json_ld = json.dumps(
            {
                "@type": "WebPage",
                "mainEntity": {
                    "@type": "Event",
                    "name": "Ongoing Exhibition",
                    "startDate": "2025-09-01",  # Past date
                    "endDate": "2026-12-31",  # Future date
                    "description": "An ongoing exhibition.",
                },
            }
        )
        html = f"""
        <html>
        <head><script type="application/ld+json">{json_ld}</script></head>
        <body>
            <p class="category"><a class="expo">EXPO</a></p>
            <h1>Ongoing Exhibition</h1>
        </body>
        </html>
        """
        parser.http_client.get_text.return_value = html

        event = parser._parse_detail_page(
            "https://www.lezef.org/fr/saison/25-26/ongoing-exhibition"
        )

        assert event is not None
        assert event.name == "Ongoing Exhibition"
        # The event date should be today (not the past startDate)
        from datetime import datetime
        from zoneinfo import ZoneInfo

        today = datetime.now(ZoneInfo("Europe/Paris")).date()
        assert event.start_datetime.date() == today
        # Time should be 10:00 for exhibitions
        assert event.start_datetime.hour == 10

    def test_past_event_without_enddate_is_skipped(self, parser):
        """Test that past events without endDate are still skipped."""
        json_ld = json.dumps(
            {
                "@type": "WebPage",
                "mainEntity": {
                    "@type": "Event",
                    "name": "Past Event",
                    "startDate": "2025-01-01",  # Past date, no endDate
                    "description": "A past event.",
                },
            }
        )
        html = f"""
        <html>
        <head><script type="application/ld+json">{json_ld}</script></head>
        <body>
            <p class="category"><a class="theatre">THEATRE</a></p>
            <h1>Past Event</h1>
        </body>
        </html>
        """
        parser.http_client.get_text.return_value = html

        event = parser._parse_detail_page(
            "https://www.lezef.org/fr/saison/25-26/past-event"
        )

        assert event is None  # Should be skipped
