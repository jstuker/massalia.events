"""Tests for the Théâtre de l'Œuvre parser."""

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.loeuvre import LoeuvreParser
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_listing_html():
    """Sample Théâtre de l'Œuvre programmation page HTML."""
    return """
    <html lang="fr">
    <body>
        <div class="grid-items">
            <a href="https://www.theatre-oeuvre.com/evenements/grems/">
                <img src="https://www.theatre-oeuvre.com/wp-content/uploads/2026/01/grems-800x480.jpg"
                     alt="GREMS">
                <ul>
                    <li>Musique</li>
                </ul>
                <h3>GREMS</h3>
                <div>samedi 04 avril</div>
                <div>20:30</div>
            </a>
            <a href="https://www.theatre-oeuvre.com/evenements/barbara-carlotti-duo/">
                <img src="https://www.theatre-oeuvre.com/wp-content/uploads/2026/01/carlotti-800x480.jpg"
                     alt="Barbara Carlotti">
                <ul>
                    <li>Musique</li>
                </ul>
                <h3>Barbara Carlotti (duo)</h3>
                <div>vendredi 27 mars</div>
                <div>20:30</div>
            </a>
            <a href="https://www.theatre-oeuvre.com/evenements/sold-out-event/">
                <img src="https://www.theatre-oeuvre.com/wp-content/uploads/2026/01/sold-800x480.jpg"
                     alt="Sold Out Show">
                <div>Complet</div>
                <ul>
                    <li>Théatre</li>
                </ul>
                <h3>Sold Out Show</h3>
                <div>vendredi 14 février</div>
                <div>20:00</div>
            </a>
            <a href="https://www.theatre-oeuvre.com/evenements/cancelled-event/">
                <img src="https://www.theatre-oeuvre.com/wp-content/uploads/2026/01/cancel-800x480.jpg"
                     alt="Cancelled Show">
                <div>Annulé</div>
                <ul>
                    <li>Musique</li>
                </ul>
                <h3>Cancelled Show</h3>
                <div>samedi 15 février</div>
                <div>20:30</div>
            </a>
            <a href="https://www.theatre-oeuvre.com/evenements/kiledjian-2/">
                <img src="https://www.theatre-oeuvre.com/wp-content/uploads/2026/01/kiledjian-800x480.jpg"
                     alt="Kiledjian">
                <ul>
                    <li>Musique</li>
                </ul>
                <h3>Kiledjian</h3>
                <div>samedi 31 janvier</div>
                <div>19:00</div>
            </a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_html():
    """Sample event detail page HTML."""
    return """
    <html lang="fr">
    <head>
        <meta property="og:description"
              content="Sur scène, GREMS se présente en trio expérimental.">
        <meta property="og:image"
              content="https://www.theatre-oeuvre.com/wp-content/uploads/2026/01/grems-visuel-web-800x480.jpg">
    </head>
    <body>
        <h1>GREMS</h1>
        <p>samedi 04 avril</p>
        <p>20:30</p>
        <ul>
            <li>Musique</li>
            <li>Rap</li>
            <li>Jazz</li>
        </ul>
        <p>Théâtre de l'Œuvre</p>
        <p>1, rue Mission de France, 13001 MARSEILLE</p>
        <p>1h30</p>
        <p>Tout public</p>
        <p>Tarif(s) : 15€/12€ (prévente) – 17€/14€ (sur place)</p>
        <p>Sur scène, GREMS se présente aujourd'hui en trio expérimental,
           aux côtés de Rose Kid et Nxquantize. Un live intense et organique.</p>
    </body>
    </html>
    """


@pytest.fixture
def detail_html_no_time():
    """Detail page HTML without explicit time."""
    return """
    <html lang="fr">
    <head>
        <meta property="og:description" content="Un spectacle unique.">
        <meta property="og:image"
              content="https://www.theatre-oeuvre.com/wp-content/uploads/2026/01/show.jpg">
    </head>
    <body>
        <h1>Le Spectacle</h1>
        <p>vendredi 14 mars</p>
        <ul>
            <li>Théatre</li>
        </ul>
        <p>Théâtre de l'Œuvre</p>
        <p>Un spectacle unique qui vous transportera dans un univers magique
           et poétique pendant une soirée inoubliable.</p>
    </body>
    </html>
    """


@pytest.fixture
def detail_html_with_year():
    """Detail page HTML with explicit year in date."""
    return """
    <html lang="fr">
    <head>
        <meta property="og:description" content="Concert exceptionnel.">
        <meta property="og:image"
              content="https://www.theatre-oeuvre.com/wp-content/uploads/2026/01/concert.jpg">
    </head>
    <body>
        <h1>Concert Exceptionnel</h1>
        <p>15 juin 2026</p>
        <p>21:00</p>
        <ul>
            <li>Musique</li>
        </ul>
        <p>Un concert exceptionnel à ne pas manquer dans cette salle magnifique.</p>
    </body>
    </html>
    """


@pytest.fixture
def mock_config():
    """Standard config for the parser."""
    return {
        "name": "Théâtre de l'Œuvre",
        "id": "loeuvre",
        "url": "https://www.theatre-oeuvre.com/agenda/programmation/",
        "parser": "loeuvre",
        "rate_limit": {
            "requests_per_second": 0.5,
            "delay_between_pages": 0.0,
        },
        "category_map": {
            "Musique": "musique",
            "Théatre": "theatre",
            "Théâtre": "theatre",
            "Theatre": "theatre",
            "Danse": "danse",
            "Cabaret": "theatre",
            "Humour": "theatre",
            "Chant": "musique",
            "Cinéma": "art",
            "Rap": "musique",
            "Jazz": "musique",
            "Pop": "musique",
            "Folk": "musique",
        },
    }


@pytest.fixture
def parser(mock_config):
    """Create a LoeuvreParser instance with mocked dependencies."""
    http_client = MagicMock()
    image_downloader = MagicMock()
    markdown_generator = MagicMock()
    return LoeuvreParser(
        config=mock_config,
        http_client=http_client,
        image_downloader=image_downloader,
        markdown_generator=markdown_generator,
    )


# ── Test _find_event_urls ──────────────────────────────────────────


class TestFindEventUrls:
    """Tests for extracting event URLs from listing page."""

    def test_finds_event_urls(self, parser, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html, "https://www.theatre-oeuvre.com/agenda/programmation/"
        )
        urls = parser._find_event_urls(html_parser)
        # Should find grems, carlotti, and kiledjian (not sold-out or cancelled)
        assert len(urls) == 3

    def test_skips_complet_events(self, parser, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html, "https://www.theatre-oeuvre.com/agenda/programmation/"
        )
        urls = parser._find_event_urls(html_parser)
        assert not any("sold-out-event" in url for url in urls)

    def test_skips_annule_events(self, parser, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html, "https://www.theatre-oeuvre.com/agenda/programmation/"
        )
        urls = parser._find_event_urls(html_parser)
        assert not any("cancelled-event" in url for url in urls)

    def test_includes_valid_events(self, parser, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html, "https://www.theatre-oeuvre.com/agenda/programmation/"
        )
        urls = parser._find_event_urls(html_parser)
        url_str = " ".join(urls)
        assert "grems" in url_str
        assert "barbara-carlotti-duo" in url_str
        assert "kiledjian-2" in url_str

    def test_returns_absolute_urls(self, parser):
        html = """
        <html><body>
            <a href="/evenements/test-event/">
                <h3>Test Event</h3>
            </a>
        </body></html>
        """
        html_parser = HTMLParser(html, "https://www.theatre-oeuvre.com")
        urls = parser._find_event_urls(html_parser)
        assert len(urls) == 1
        assert urls[0].startswith("https://")

    def test_handles_empty_page(self, parser):
        html_parser = HTMLParser(
            "<html><body></body></html>", "https://www.theatre-oeuvre.com"
        )
        urls = parser._find_event_urls(html_parser)
        assert urls == []

    def test_deduplicates_urls(self, parser):
        html = """
        <html><body>
            <a href="/evenements/test-event/"><h3>Test</h3></a>
            <a href="/evenements/test-event/"><h3>Test</h3></a>
        </body></html>
        """
        html_parser = HTMLParser(html, "https://www.theatre-oeuvre.com")
        urls = parser._find_event_urls(html_parser)
        assert len(urls) == 1


# ── Test _parse_detail_page ────────────────────────────────────────


class TestParseDetailPage:
    """Tests for parsing event detail pages."""

    def test_parses_complete_event(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/grems/"
        )
        assert event is not None
        assert event.name == "GREMS"
        assert isinstance(event.start_datetime, datetime)

    def test_extracts_time(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/grems/"
        )
        assert event.start_datetime.hour == 20
        assert event.start_datetime.minute == 30

    def test_extracts_description(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/grems/"
        )
        assert "trio expérimental" in event.description

    def test_extracts_image(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/grems/"
        )
        assert event.image is not None
        assert "grems-visuel-web" in event.image

    def test_extracts_category(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/grems/"
        )
        assert "musique" in event.categories

    def test_sets_location(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/grems/"
        )
        assert "theatre-de-l-oeuvre" in event.locations

    def test_generates_source_id(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/grems/"
        )
        assert event.source_id == "loeuvre:grems"

    def test_defaults_time_to_20h(self, parser, detail_html_no_time):
        parser.http_client.get_text.return_value = detail_html_no_time
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/le-spectacle/"
        )
        assert event is not None
        assert event.start_datetime.hour == 20
        assert event.start_datetime.minute == 0

    def test_parses_date_with_year(self, parser, detail_html_with_year):
        parser.http_client.get_text.return_value = detail_html_with_year
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/concert-exceptionnel/"
        )
        assert event is not None
        assert event.start_datetime.year == 2026
        assert event.start_datetime.month == 6
        assert event.start_datetime.day == 15
        assert event.start_datetime.hour == 21

    def test_returns_none_on_fetch_failure(self, parser):
        parser.http_client.get_text.side_effect = Exception("Network error")
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/test/"
        )
        assert event is None

    def test_returns_none_without_name(self, parser):
        html = """
        <html><body>
            <p>samedi 04 avril</p>
            <p>20:30</p>
        </body></html>
        """
        parser.http_client.get_text.return_value = html
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/no-name/"
        )
        assert event is None

    def test_returns_none_without_date(self, parser):
        html = """
        <html><body>
            <h1>Test Event</h1>
            <p>Some text without a date</p>
        </body></html>
        """
        parser.http_client.get_text.return_value = html
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/no-date/"
        )
        assert event is None

    def test_extracts_tags(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.theatre-oeuvre.com/evenements/grems/"
        )
        assert len(event.tags) > 0
        assert len(event.tags) <= 5


# ── Test French date parsing ───────────────────────────────────────


class TestFrenchDateParsing:
    """Tests for French date/time parsing methods."""

    def test_parses_date_with_day_name(self, parser):
        result = parser._parse_french_date("samedi 04 avril")
        assert result is not None
        assert result.month == 4
        assert result.day == 4

    def test_parses_date_without_day_name(self, parser):
        result = parser._parse_french_date("15 juin")
        assert result is not None
        assert result.month == 6
        assert result.day == 15

    def test_parses_date_with_year(self, parser):
        result = parser._parse_french_date("15 juin 2026")
        assert result is not None
        assert result.year == 2026
        assert result.month == 6
        assert result.day == 15

    def test_parses_date_with_accented_month(self, parser):
        result = parser._parse_french_date("10 février")
        assert result is not None
        assert result.month == 2

    def test_parses_date_with_december(self, parser):
        result = parser._parse_french_date("25 décembre")
        assert result is not None
        assert result.month == 12

    def test_returns_none_for_non_date(self, parser):
        result = parser._parse_french_date("just some text")
        assert result is None

    def test_returns_none_for_empty_string(self, parser):
        result = parser._parse_french_date("")
        assert result is None

    def test_returns_none_for_invalid_month(self, parser):
        result = parser._parse_french_date("15 notamonth")
        assert result is None

    def test_parse_time_colon_format(self, parser):
        result = parser._parse_time("20:30")
        assert result == (20, 30)

    def test_parse_time_h_format(self, parser):
        result = parser._parse_time("19h30")
        assert result == (19, 30)

    def test_parse_time_h_no_minutes(self, parser):
        result = parser._parse_time("19h")
        assert result == (19, 0)

    def test_parse_time_returns_none_for_no_time(self, parser):
        result = parser._parse_time("just text")
        assert result is None

    def test_parse_time_returns_none_for_empty(self, parser):
        result = parser._parse_time("")
        assert result is None


# ── Test _is_cancelled_or_sold_out ─────────────────────────────────


class TestCancelledOrSoldOut:
    """Tests for detecting sold out / cancelled events."""

    def test_detects_complet(self, parser):
        from bs4 import BeautifulSoup

        html = '<a href="/evenements/test/"><div>Complet</div><h3>Test</h3></a>'
        soup = BeautifulSoup(html, "lxml")
        link = soup.select_one("a")
        assert parser._is_cancelled_or_sold_out(link) is True

    def test_detects_annule(self, parser):
        from bs4 import BeautifulSoup

        html = '<a href="/evenements/test/"><div>Annulé</div><h3>Test</h3></a>'
        soup = BeautifulSoup(html, "lxml")
        link = soup.select_one("a")
        assert parser._is_cancelled_or_sold_out(link) is True

    def test_normal_event_not_detected(self, parser):
        from bs4 import BeautifulSoup

        html = '<a href="/evenements/test/"><h3>Normal Event</h3></a>'
        soup = BeautifulSoup(html, "lxml")
        link = soup.select_one("a")
        assert parser._is_cancelled_or_sold_out(link) is False


# ── Test _generate_source_id ───────────────────────────────────────


class TestGenerateSourceId:
    """Tests for source ID generation."""

    def test_generates_from_url(self, parser):
        result = parser._generate_source_id(
            "https://www.theatre-oeuvre.com/evenements/grems/"
        )
        assert result == "loeuvre:grems"

    def test_handles_trailing_slash(self, parser):
        result = parser._generate_source_id(
            "https://www.theatre-oeuvre.com/evenements/test-event/"
        )
        assert result == "loeuvre:test-event"

    def test_handles_no_trailing_slash(self, parser):
        result = parser._generate_source_id(
            "https://www.theatre-oeuvre.com/evenements/test-event"
        )
        assert result == "loeuvre:test-event"


# ── Test _extract_location ─────────────────────────────────────────


class TestExtractLocation:
    """Tests for location extraction."""

    def test_default_location(self, parser, sample_detail_html):
        detail_parser = HTMLParser(
            sample_detail_html, "https://www.theatre-oeuvre.com"
        )
        location = parser._extract_location(detail_parser)
        assert location == "theatre-de-l-oeuvre"


# ── Test category mapping ──────────────────────────────────────────


class TestCategoryMapping:
    """Tests for category extraction and mapping."""

    def test_maps_musique(self, parser):
        html = """
        <html><body>
            <h1>Test</h1>
            <ul><li>Musique</li></ul>
        </body></html>
        """
        detail_parser = HTMLParser(html, "https://www.theatre-oeuvre.com")
        category = parser._extract_category(detail_parser)
        assert category == "musique"

    def test_maps_theatre(self, parser):
        html = """
        <html><body>
            <h1>Test</h1>
            <ul><li>Théatre</li></ul>
        </body></html>
        """
        detail_parser = HTMLParser(html, "https://www.theatre-oeuvre.com")
        category = parser._extract_category(detail_parser)
        assert category == "theatre"

    def test_maps_danse(self, parser):
        html = """
        <html><body>
            <h1>Test</h1>
            <ul><li>Danse</li></ul>
        </body></html>
        """
        detail_parser = HTMLParser(html, "https://www.theatre-oeuvre.com")
        category = parser._extract_category(detail_parser)
        assert category == "danse"

    def test_defaults_to_communaute(self, parser):
        html = """
        <html><body>
            <h1>Test</h1>
        </body></html>
        """
        detail_parser = HTMLParser(html, "https://www.theatre-oeuvre.com")
        category = parser._extract_category(detail_parser)
        assert category == "communaute"


# ── Test parse_events integration ──────────────────────────────────


class TestParseEventsIntegration:
    """Integration tests for the full parse_events flow."""

    def test_parse_events_with_detail_pages(
        self, parser, sample_listing_html, sample_detail_html
    ):
        """Test full flow: listing page -> detail pages -> events."""
        parser.http_client.get_text.return_value = sample_detail_html

        html_parser = HTMLParser(
            sample_listing_html,
            "https://www.theatre-oeuvre.com/agenda/programmation/",
        )
        events = parser.parse_events(html_parser)

        # Should have events (excluding sold-out and cancelled)
        assert len(events) > 0
        assert all(isinstance(e, Event) for e in events)

    def test_parse_events_handles_fetch_failure(self, parser, sample_listing_html):
        """Test that parse_events handles detail page failures gracefully."""
        parser.http_client.get_text.side_effect = Exception("Network error")

        html_parser = HTMLParser(
            sample_listing_html,
            "https://www.theatre-oeuvre.com/agenda/programmation/",
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_parse_events_empty_listing(self, parser):
        html_parser = HTMLParser(
            "<html><body></body></html>",
            "https://www.theatre-oeuvre.com/agenda/programmation/",
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_source_name(self, parser):
        assert parser.source_name == "Théâtre de l'Œuvre"


# ── Test _infer_year ───────────────────────────────────────────────


class TestInferYear:
    """Tests for year inference logic."""

    def test_infer_year_returns_int(self, parser):
        year = parser._infer_year(6, 15)
        assert isinstance(year, int)

    def test_infer_year_handles_invalid_date(self, parser):
        # Feb 30 doesn't exist, should return current year
        year = parser._infer_year(2, 30)
        now = datetime.now(PARIS_TZ)
        assert year == now.year
