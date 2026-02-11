"""Tests for the Cité de la Musique parser."""

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.citemusique import CiteMusiqueParser
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_listing_html():
    """Sample Cité de la Musique listing page HTML."""
    return """
    <html lang="fr">
    <body>
        <div id="events-listing-bg">
        <ul id="monthly-events" class="events-listing-content sort-destination">
            <li class="event-v2-list-item col-md-4 col-sm-6 grid-item concert musique-du-monde auditorium d-20260213 m-202602">
                <div class="shadow">
                <a href="https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/">
                    <div class="event-v2-picture">
                        <div class="hidden-xs">
                            <noscript><img src="https://www.citemusique-marseille.com/wp-html/uploads/2025/08/AIDA-NOSTRAT-TRIO-1.jpg" class="attachment-480x700 size-480x700" alt="" /></noscript>
                        </div>
                        <div class="lined-info-hover lined-info-hover-top">
                            <div class="truncate">Vendredi 13 Février à 20h00</div>
                            <div class="truncate">Cité de la Musique, Auditorium<br/></div>
                        </div>
                    </div>
                    <div class="lined-info-static">
                        <h4>AIDA NOSRAT TRIO</h4>
                        <div class="truncate">Vendredi 13 Février</div>
                    </div>
                </a>
                </div>
            </li>
            <li class="event-v2-list-item col-md-4 col-sm-6 grid-item scene-ouverte jazz club-27 d-20260323 m-202603">
                <div class="shadow">
                <a href="https://www.citemusique-marseille.com/evenement/jazz-club-session/">
                    <div class="event-v2-picture">
                        <div class="hidden-xs">
                            <noscript><img src="https://www.citemusique-marseille.com/wp-html/uploads/2025/09/JAZZ-SESSION.jpg" /></noscript>
                        </div>
                        <div class="lined-info-hover lined-info-hover-top">
                            <div class="truncate">Lundi 23 Mars à 20h00</div>
                            <div class="truncate">Cité de la Musique, Club 27<br/></div>
                        </div>
                    </div>
                    <div class="lined-info-static">
                        <h4>JAZZ'N CITE</h4>
                        <div class="truncate">Lundi 23 Mars</div>
                    </div>
                </a>
                </div>
            </li>
            <li class="event-v2-list-item col-md-4 col-sm-6 grid-item spectacle jeune-public musique-du-monde auditorium d-20260313 m-202603">
                <div class="shadow">
                <a href="https://www.citemusique-marseille.com/evenement/spectacle-jeune-public/">
                    <div class="event-v2-picture">
                        <div class="hidden-xs">
                            <noscript><img src="https://www.citemusique-marseille.com/wp-html/uploads/2025/09/JEUNE-PUBLIC.jpg" /></noscript>
                        </div>
                        <div class="lined-info-hover lined-info-hover-top">
                            <div class="truncate">Vendredi 13 Mars à 14h30</div>
                            <div class="truncate">Cité de la Musique, Auditorium<br/></div>
                        </div>
                    </div>
                    <div class="lined-info-static">
                        <h4>SPECTACLE JEUNE PUBLIC</h4>
                        <div class="truncate">Vendredi 13 Mars</div>
                    </div>
                </a>
                </div>
            </li>
        </ul>
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
              content="COMMON ROUTES - Connue en France pour sa maîtrise des répertoires classique et populaire iraniens, la chanteuse et violoniste Aïda Nosrat s'est entourée de deux musiciens d'exception.">
        <meta property="og:image"
              content="https://www.citemusique-marseille.com/wp-html/uploads/2025/08/AIDA-NOSTRAT-TRIO.jpg">
    </head>
    <body>
        <div class="content full">
            <h2 class="event-title">AIDA NOSRAT TRIO</h2>
            <div class="event-details-left">
                <a href="https://www.citemusique-marseille.com/wp-html/uploads/2025/08/AIDA-NOSTRAT-TRIO.jpg" class="magnific-image">
                    <img src="https://www.citemusique-marseille.com/wp-html/uploads/2025/08/AIDA-NOSTRAT-TRIO.jpg" />
                </a>
            </div>
            <div class="event-details-right">
                <div class="evenement_date active" data-date="178770">
                    Vendredi 13 Février 2026 à 20h00
                </div>
                <div class="evenement_salle" data-date="178770">
                    Cité de la Musique, Auditorium
                    <br/>4 rue Bernard du Bois - 13001 Marseille
                </div>
                <div class="evenement_reservation" data-date="178770">
                    <a href="https://www.mapado.com/" class="btn btn-lg btn-block btn-primary event-tickets">Billetterie ></a>
                </div>
                <div class="evenement_programme event-schedule" data-date="178770">
                    <div class="event-prog">
                        <div class="event-prog-content">
                            19H00 ouverture billetterie
                        </div>
                    </div>
                    <div class="event-prog">
                        <div class="event-prog-content">
                            20H00 début du concert
                        </div>
                    </div>
                </div>
            </div>
            <div class="heading-wbg">Programme</div>
            <p>Aida NOSRAT (Violon), Antoine GIRARD (Accordéon)</p>
            <p>Connue en France pour sa maîtrise des répertoires classique et populaire iraniens, la chanteuse et violoniste Aïda Nosrat s'est entourée de deux musiciens d'exception.</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def detail_html_no_og():
    """Detail page HTML without og:description, with content paragraphs."""
    return """
    <html lang="fr">
    <head></head>
    <body>
        <div class="content full">
            <h2 class="event-title">LA CABRA</h2>
            <div class="event-details-right">
                <div class="evenement_date active">
                    Vendredi 20 Février 2026 à 20h00
                </div>
                <div class="evenement_salle">
                    Cité de la Musique, Auditorium
                </div>
            </div>
            <p>Short text</p>
            <p>La Cabra est un ensemble musical qui mêle les traditions musicales méditerranéennes avec des influences contemporaines.</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def detail_html_club27():
    """Detail page for a Club 27 event."""
    return """
    <html lang="fr">
    <head>
        <meta property="og:description" content="Scène ouverte jazz au Club 27.">
    </head>
    <body>
        <div class="content full">
            <h2 class="event-title">JAZZ'N CITE</h2>
            <div class="event-details-right">
                <div class="evenement_date active">
                    Lundi 23 Mars 2026 à 20h00
                </div>
                <div class="evenement_salle">
                    Cité de la Musique, Club 27
                </div>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_config():
    """Standard config for the parser."""
    return {
        "name": "Cité de la Musique",
        "id": "citemusique",
        "url": "https://www.citemusique-marseille.com/concerts-spectacles/",
        "parser": "citemusique",
        "rate_limit": {
            "requests_per_second": 0.5,
            "delay_between_pages": 0.0,
        },
        "category_map": {
            "concert": "musique",
            "musique-du-monde": "musique",
            "jazz": "musique",
            "musique-classique": "musique",
            "musique-contemporaine": "musique",
            "musique-electroacoustique": "musique",
            "scene-ouverte": "musique",
            "spectacle": "theatre",
            "jeune-public": "theatre",
            "rencontre": "communaute",
            "projection": "art",
            "conference": "communaute",
        },
    }


@pytest.fixture
def parser(mock_config):
    """Create a CiteMusiqueParser instance with mocked dependencies."""
    http_client = MagicMock()
    image_downloader = MagicMock()
    markdown_generator = MagicMock()
    return CiteMusiqueParser(
        config=mock_config,
        http_client=http_client,
        image_downloader=image_downloader,
        markdown_generator=markdown_generator,
    )


# ── Test listing page parsing ─────────────────────────────────────


class TestListingParsing:
    """Tests for extracting event data from the listing page."""

    def test_finds_event_items(self, parser, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html,
            "https://www.citemusique-marseille.com/concerts-spectacles/",
        )
        items = html_parser.select("li.event-v2-list-item")
        assert len(items) == 3

    def test_extracts_event_urls(self, parser, sample_listing_html):
        html_parser = HTMLParser(
            sample_listing_html,
            "https://www.citemusique-marseille.com/concerts-spectacles/",
        )
        items = html_parser.select("li.event-v2-list-item")
        urls = []
        for item in items:
            link = item.select_one("a[href*='/evenement/']")
            if link:
                urls.append(link.get("href"))
        assert len(urls) == 3
        assert "aida-nosrat-trio" in urls[0]

    def test_handles_empty_listing(self, parser):
        html_parser = HTMLParser(
            "<html><body></body></html>",
            "https://www.citemusique-marseille.com/concerts-spectacles/",
        )
        events = parser.parse_events(html_parser)
        assert events == []


# ── Test CSS class extraction ─────────────────────────────────────


class TestCssClassExtraction:
    """Tests for extracting metadata from listing CSS classes."""

    def test_extract_date_from_classes(self, parser):
        classes = ["event-v2-list-item", "concert", "d-20260213", "m-202602"]
        result = parser._extract_date_from_classes(classes)
        assert result == "20260213"

    def test_extract_date_no_date_class(self, parser):
        classes = ["event-v2-list-item", "concert"]
        result = parser._extract_date_from_classes(classes)
        assert result == ""

    def test_extract_categories_concert(self, parser):
        classes = ["concert", "musique-du-monde", "auditorium"]
        categories = parser._extract_categories_from_classes(classes)
        assert "musique" in categories

    def test_extract_categories_spectacle(self, parser):
        classes = ["spectacle", "jeune-public"]
        categories = parser._extract_categories_from_classes(classes)
        assert "theatre" in categories

    def test_extract_categories_default(self, parser):
        classes = ["grid-item", "col-md-4"]
        categories = parser._extract_categories_from_classes(classes)
        assert categories == ["musique"]

    def test_extract_tags_from_genres(self, parser):
        classes = ["concert", "musique-du-monde", "jazz"]
        tags = parser._extract_tags_from_classes(classes)
        assert "musique du monde" in tags
        assert "jazz" in tags

    def test_extract_tags_empty_for_no_genres(self, parser):
        classes = ["concert", "auditorium"]
        tags = parser._extract_tags_from_classes(classes)
        assert tags == []


# ── Test detail page parsing ──────────────────────────────────────


class TestParseDetailPage:
    """Tests for parsing event detail pages."""

    def test_parses_complete_event(self, parser, sample_detail_html):
        listing_meta = {
            "date_class": "20260213",
            "categories": ["musique"],
            "tags": ["musique du monde"],
            "classes": ["concert", "musique-du-monde", "d-20260213"],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/",
            sample_detail_html,
            listing_meta,
        )
        assert event is not None
        assert event.name == "AIDA NOSRAT TRIO"
        assert isinstance(event.start_datetime, datetime)

    def test_extracts_title(self, parser, sample_detail_html):
        listing_meta = {
            "date_class": "20260213",
            "categories": ["musique"],
            "tags": [],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/",
            sample_detail_html,
            listing_meta,
        )
        assert event.name == "AIDA NOSRAT TRIO"

    def test_extracts_date_from_class(self, parser, sample_detail_html):
        listing_meta = {
            "date_class": "20260213",
            "categories": ["musique"],
            "tags": [],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/",
            sample_detail_html,
            listing_meta,
        )
        assert event.start_datetime.year == 2026
        assert event.start_datetime.month == 2
        assert event.start_datetime.day == 13

    def test_extracts_time(self, parser, sample_detail_html):
        listing_meta = {
            "date_class": "20260213",
            "categories": ["musique"],
            "tags": [],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/",
            sample_detail_html,
            listing_meta,
        )
        assert event.start_datetime.hour == 20
        assert event.start_datetime.minute == 0

    def test_extracts_description_from_og(self, parser, sample_detail_html):
        listing_meta = {
            "date_class": "20260213",
            "categories": ["musique"],
            "tags": [],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/",
            sample_detail_html,
            listing_meta,
        )
        assert "COMMON ROUTES" in event.description
        assert len(event.description) <= 163  # 160 + "..."

    def test_extracts_description_from_content(self, parser, detail_html_no_og):
        listing_meta = {
            "date_class": "20260220",
            "categories": ["musique"],
            "tags": [],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/la-cabra/",
            detail_html_no_og,
            listing_meta,
        )
        assert "La Cabra" in event.description

    def test_extracts_image_from_magnific(self, parser, sample_detail_html):
        listing_meta = {
            "date_class": "20260213",
            "categories": ["musique"],
            "tags": [],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/",
            sample_detail_html,
            listing_meta,
        )
        assert event.image is not None
        assert "AIDA-NOSTRAT-TRIO" in event.image

    def test_sets_location_auditorium(self, parser, sample_detail_html):
        listing_meta = {
            "date_class": "20260213",
            "categories": ["musique"],
            "tags": [],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/",
            sample_detail_html,
            listing_meta,
        )
        assert "cite-de-la-musique" in event.locations

    def test_sets_location_club27(self, parser, detail_html_club27):
        listing_meta = {
            "date_class": "20260323",
            "categories": ["musique"],
            "tags": [],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/jazz-club-session/",
            detail_html_club27,
            listing_meta,
        )
        assert "cite-de-la-musique" in event.locations

    def test_generates_source_id(self, parser, sample_detail_html):
        listing_meta = {
            "date_class": "20260213",
            "categories": ["musique"],
            "tags": [],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/",
            sample_detail_html,
            listing_meta,
        )
        assert event.source_id == "citemusique:aida-nosrat-trio"

    def test_uses_listing_categories(self, parser, sample_detail_html):
        listing_meta = {
            "date_class": "20260213",
            "categories": ["musique"],
            "tags": ["musique du monde"],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/",
            sample_detail_html,
            listing_meta,
        )
        assert "musique" in event.categories

    def test_uses_listing_tags(self, parser, sample_detail_html):
        listing_meta = {
            "date_class": "20260213",
            "categories": ["musique"],
            "tags": ["musique du monde"],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/",
            sample_detail_html,
            listing_meta,
        )
        assert "musique du monde" in event.tags

    def test_returns_none_without_title(self, parser):
        html = """
        <html><body>
            <div class="content">
                <div class="evenement_date active">
                    Vendredi 13 Février 2026 à 20h00
                </div>
            </div>
        </body></html>
        """
        listing_meta = {
            "date_class": "20260213",
            "categories": ["musique"],
            "tags": [],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/test/",
            html,
            listing_meta,
        )
        assert event is None

    def test_returns_none_without_date(self, parser):
        html = """
        <html><body>
            <div class="content">
                <h2 class="event-title">Test Event</h2>
            </div>
        </body></html>
        """
        listing_meta = {
            "date_class": "",
            "categories": ["musique"],
            "tags": [],
            "classes": [],
        }
        event = parser._parse_detail_page(
            "https://www.citemusique-marseille.com/evenement/test/",
            html,
            listing_meta,
        )
        assert event is None


# ── Test date parsing ─────────────────────────────────────────────


class TestDateParsing:
    """Tests for date parsing methods."""

    def test_parse_date_class(self, parser):
        result = parser._parse_date_class("20260213")
        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 13

    def test_parse_date_class_invalid(self, parser):
        result = parser._parse_date_class("invalid")
        assert result is None

    def test_parse_date_class_empty(self, parser):
        result = parser._parse_date_class("")
        assert result is None

    def test_parse_french_datetime(self, parser):
        result = parser._parse_french_datetime("Vendredi 13 Février 2026 à 20h00")
        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 13
        assert result.hour == 20
        assert result.minute == 0

    def test_parse_french_datetime_with_minutes(self, parser):
        result = parser._parse_french_datetime("Samedi 14 Mars 2026 à 19h30")
        assert result is not None
        assert result.hour == 19
        assert result.minute == 30

    def test_parse_french_datetime_returns_none(self, parser):
        result = parser._parse_french_datetime("just some text")
        assert result is None

    def test_parse_french_datetime_empty(self, parser):
        result = parser._parse_french_datetime("")
        assert result is None


# ── Test source ID generation ─────────────────────────────────────


class TestGenerateSourceId:
    """Tests for source ID generation."""

    def test_generates_from_url(self, parser):
        result = parser._generate_source_id(
            "https://www.citemusique-marseille.com/evenement/aida-nosrat-trio/"
        )
        assert result == "citemusique:aida-nosrat-trio"

    def test_handles_trailing_slash(self, parser):
        result = parser._generate_source_id(
            "https://www.citemusique-marseille.com/evenement/test-event/"
        )
        assert result == "citemusique:test-event"

    def test_handles_no_trailing_slash(self, parser):
        result = parser._generate_source_id(
            "https://www.citemusique-marseille.com/evenement/test-event"
        )
        assert result == "citemusique:test-event"


# ── Test parse_events integration ─────────────────────────────────


class TestParseEventsIntegration:
    """Integration tests for the full parse_events flow."""

    def test_parse_events_with_detail_pages(
        self, parser, sample_listing_html, sample_detail_html
    ):
        """Test full flow: listing page -> detail pages -> events."""
        parser.http_client.get_text.return_value = sample_detail_html

        html_parser = HTMLParser(
            sample_listing_html,
            "https://www.citemusique-marseille.com/concerts-spectacles/",
        )
        events = parser.parse_events(html_parser)

        assert len(events) > 0
        assert all(isinstance(e, Event) for e in events)

    def test_parse_events_handles_fetch_failure(self, parser, sample_listing_html):
        """Test graceful handling when detail pages fail to load."""
        parser.http_client.get_text.return_value = ""

        html_parser = HTMLParser(
            sample_listing_html,
            "https://www.citemusique-marseille.com/concerts-spectacles/",
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_parse_events_empty_listing(self, parser):
        html_parser = HTMLParser(
            "<html><body></body></html>",
            "https://www.citemusique-marseille.com/concerts-spectacles/",
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_source_name(self, parser):
        assert parser.source_name == "Cité de la Musique"

    def test_deduplicates_urls(self, parser, sample_detail_html):
        """Test that duplicate URLs in listing are deduplicated."""
        parser.http_client.get_text.return_value = sample_detail_html

        html = """
        <html><body>
        <ul>
            <li class="event-v2-list-item concert d-20260213 m-202602">
                <a href="https://www.citemusique-marseille.com/evenement/test/">
                    <h4>Test</h4>
                </a>
            </li>
            <li class="event-v2-list-item concert d-20260213 m-202602">
                <a href="https://www.citemusique-marseille.com/evenement/test/">
                    <h4>Test</h4>
                </a>
            </li>
        </ul>
        </body></html>
        """
        html_parser = HTMLParser(
            html,
            "https://www.citemusique-marseille.com/concerts-spectacles/",
        )
        events = parser.parse_events(html_parser)
        # Should only fetch and parse the URL once
        assert len(events) <= 1
