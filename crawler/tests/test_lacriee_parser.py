"""Tests for the La Criée - Théâtre National de Marseille parser."""

from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.lacriee import (
    LaCrieeParser,
    _extract_event_urls_from_html,
    _find_venue_in_lines,
    _generate_source_id,
    _is_external_venue,
    _parse_french_date,
    _parse_french_time,
    _parse_showtimes_from_html,
)
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_listing_html():
    """Sample La Criée listing page with event cards."""
    return """
    <html>
    <body>
        <div>
            <a href="/programmation/evenements/la-lecon">
                <img src="/storage/2026/01/la-lecon.jpg" alt="La Leçon">
                <div>Théâtre</div>
                <h3>La Leçon</h3>
                <div>29 janvier - 13 février 2026</div>
            </a>
            <a href="/programmation/evenements/dom-juan">
                <img src="/storage/2025/04/dom-juan.jpg" alt="Dom Juan">
                <div>Théâtre</div>
                <h3>Dom Juan</h3>
                <div>4 - 6 juin 2026</div>
            </a>
            <a href="/programmation/evenements/carmen">
                <img src="/storage/2025/04/carmen.jpg" alt="Carmen.">
                <div>Musique</div>
                <h3>Carmen.</h3>
                <div>19 - 21 mars 2026</div>
            </a>
            <!-- Non-event link -->
            <a href="/programmation/spectacles">Back to listing</a>
            <a href="/infos-pratiques/acces">Access</a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_html():
    """Sample event detail page with multiple dates."""
    # Dates are in the future (after Feb 3, 2026)
    return """
    <html>
    <head>
        <meta property="og:image" content="https://theatre-lacriee.com/storage/2026/01/la-lecon.jpg">
        <meta property="og:title" content="La Leçon - La Criée">
    </head>
    <body>
        <h1>La Leçon</h1>
        <h2>Eugène Ionesco / Robin Renucci</h2>
        <div>Théâtre</div>
        <p>Durée : 1h05</p>
        <p>Dès 14 ans</p>
        <p>Tarifs : De 6 à 26€</p>

        <p>Transmettre, apprendre, imposer : la frontière est mince. Que se passe-t-il quand elle est franchie ? Robin Renucci donne une interprétation magistrale de cette pièce d'Ionesco.</p>

        <div>
            <h3>Jeudi</h3>
            <p>5 mars 2026</p>
            <p>20h</p>
            <p>Représentation</p>
            <p>Première</p>
            <p>La Criée - Salle Déméter</p>
            <a href="https://theatre-lacriee.notre-billetterie.com/billets?spec=1816">Prendre des places</a>
        </div>

        <div>
            <h3>Vendredi</h3>
            <p>6 mars 2026</p>
            <p>20h</p>
            <p>Représentation</p>
            <p>La Criée - Salle Déméter</p>
        </div>

        <div>
            <h3>Samedi</h3>
            <p>7 mars 2026</p>
            <p>18h15</p>
            <p>Représentation</p>
            <p>La Criée - Salle Déméter</p>
        </div>

        <div>
            <h3>Tournée</h3>
            <p>15 avril 2026</p>
            <p>20h30</p>
            <p>Théâtre du Bois de l'Aune - Aix-en-Provence</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_single_date():
    """Sample event detail with a single date."""
    return """
    <html>
    <head>
        <meta property="og:image" content="https://theatre-lacriee.com/storage/2025/04/carmen.jpg">
    </head>
    <body>
        <h1>Alexandre Kantorow</h1>
        <div>Musique</div>
        <p>Un récital exceptionnel du pianiste Alexandre Kantorow avec des œuvres de Liszt et Brahms dans un programme virtuose.</p>

        <div>
            <h3>Mardi</h3>
            <p>7 avril 2026</p>
            <p>20h</p>
            <p>Représentation</p>
            <p>La Criée - Salle Déméter</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_external_venue():
    """Sample event detail at an external venue."""
    return """
    <html>
    <head>
        <meta property="og:image" content="https://theatre-lacriee.com/storage/2025/04/carmen.jpg">
    </head>
    <body>
        <h1>Carmen.</h1>
        <h2>François Gremaud / Rosemary Standley</h2>
        <div>Musique</div>
        <p>Une pièce d'opéra-théâtre avec Rosemary Standley explorant l'œuvre de Bizet et sa protagoniste révolutionnaire.</p>

        <div>
            <h3>Jeudi</h3>
            <p>19 mars 2026</p>
            <p>20h</p>
            <p>Représentation</p>
            <p>Première</p>
        </div>

        <div>
            <h3>Vendredi</h3>
            <p>20 mars 2026</p>
            <p>20h</p>
            <p>Représentation</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def category_map():
    """Standard category mapping for La Criée."""
    return {
        "Théâtre": "theatre",
        "Théâtre jeune public": "theatre",
        "Jeune public": "theatre",
        "Musique": "musique",
        "Danse": "danse",
        "Cinéma": "art",
        "Cinéma - Musique": "musique",
        "Conte": "theatre",
        "Lecture": "communaute",
        "Lecture théâtralisée": "theatre",
        "Rencontres": "communaute",
        "Théâtre et philosophie": "communaute",
    }


# ── Test _extract_name ────────────────────────────────────────────


class TestExtractName:
    """Tests for event name extraction from detail page HTML."""

    @pytest.fixture
    def parser(self, category_map):
        http_client = MagicMock()
        image_downloader = MagicMock()
        markdown_generator = MagicMock()
        return LaCrieeParser(
            config={
                "name": "La Criée",
                "id": "lacriee",
                "url": "https://theatre-lacriee.com/programmation/spectacles",
                "parser": "lacriee",
                "rate_limit": {"delay_between_pages": 0.0},
                "category_map": category_map,
            },
            http_client=http_client,
            image_downloader=image_downloader,
            markdown_generator=markdown_generator,
        )

    def test_extracts_plain_h1(self, parser):
        html_parser = HTMLParser("<html><body><h1>La Leçon</h1></body></html>")
        assert parser._extract_name(html_parser) == "La Leçon"

    def test_extracts_h1_with_nested_spans(self, parser):
        """Regression: h1 with child elements should preserve spaces between words."""
        html_parser = HTMLParser(
            "<html><body><h1><span>La</span> <span>Leçon</span></h1></body></html>"
        )
        assert parser._extract_name(html_parser) == "La Leçon"

    def test_extracts_h1_with_adjacent_spans_no_whitespace(self, parser):
        """Regression: h1 with adjacent child elements and no whitespace between them."""
        html_parser = HTMLParser(
            "<html><body><h1><span>La</span><span>Leçon</span></h1></body></html>"
        )
        assert parser._extract_name(html_parser) == "La Leçon"

    def test_collapses_extra_whitespace(self, parser):
        html_parser = HTMLParser(
            "<html><body><h1>  La   Leçon  </h1></body></html>"
        )
        assert parser._extract_name(html_parser) == "La Leçon"

    def test_falls_back_to_h2(self, parser):
        html_parser = HTMLParser(
            "<html><body><h2>Dom Juan</h2></body></html>"
        )
        assert parser._extract_name(html_parser) == "Dom Juan"

    def test_returns_empty_when_no_heading(self, parser):
        html_parser = HTMLParser("<html><body><p>No title</p></body></html>")
        assert parser._extract_name(html_parser) == ""


# ── Test _extract_event_urls_from_html ────────────────────────────


class TestExtractEventUrls:
    """Tests for extracting event URLs from listing page HTML."""

    def test_extracts_event_urls(self, sample_listing_html):
        urls = _extract_event_urls_from_html(
            sample_listing_html,
            "https://theatre-lacriee.com",
        )
        assert len(urls) == 3
        assert any("la-lecon" in u for u in urls)
        assert any("dom-juan" in u for u in urls)
        assert any("carmen" in u for u in urls)

    def test_excludes_non_event_links(self, sample_listing_html):
        urls = _extract_event_urls_from_html(
            sample_listing_html,
            "https://theatre-lacriee.com",
        )
        assert not any("/spectacles" in u for u in urls)
        assert not any("/acces" in u for u in urls)

    def test_resolves_relative_urls(self, sample_listing_html):
        urls = _extract_event_urls_from_html(
            sample_listing_html,
            "https://theatre-lacriee.com",
        )
        for url in urls:
            assert url.startswith("https://")

    def test_handles_empty_html(self):
        urls = _extract_event_urls_from_html("<html><body></body></html>")
        assert urls == []

    def test_deduplicates_urls(self):
        html = """
        <html><body>
            <a href="/programmation/evenements/test">Link 1</a>
            <a href="/programmation/evenements/test">Link 2</a>
        </body></html>
        """
        urls = _extract_event_urls_from_html(html, "https://theatre-lacriee.com")
        assert len(urls) == 1

    def test_handles_absolute_urls(self):
        html = """
        <html><body>
            <a href="https://theatre-lacriee.com/programmation/evenements/test-event">Test</a>
        </body></html>
        """
        urls = _extract_event_urls_from_html(html)
        assert len(urls) == 1
        assert (
            urls[0] == "https://theatre-lacriee.com/programmation/evenements/test-event"
        )


# ── Test _parse_french_date ───────────────────────────────────────


class TestParseFrenchDate:
    """Tests for French date parsing."""

    def test_parses_standard_date(self):
        dt = _parse_french_date("29 janvier 2026")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 29

    def test_parses_all_months(self):
        months_data = [
            ("15 janvier 2026", 1),
            ("15 février 2026", 2),
            ("15 mars 2026", 3),
            ("15 avril 2026", 4),
            ("15 mai 2026", 5),
            ("15 juin 2026", 6),
            ("15 juillet 2026", 7),
            ("15 août 2026", 8),
            ("15 septembre 2026", 9),
            ("15 octobre 2026", 10),
            ("15 novembre 2026", 11),
            ("15 décembre 2026", 12),
        ]
        for text, expected_month in months_data:
            dt = _parse_french_date(text)
            assert dt is not None, f"Failed to parse: {text}"
            assert dt.month == expected_month, f"Wrong month for: {text}"

    def test_returns_none_for_invalid(self):
        assert _parse_french_date("not a date") is None
        assert _parse_french_date("") is None
        assert _parse_french_date("32 janvier 2026") is None

    def test_has_paris_timezone(self):
        dt = _parse_french_date("15 mars 2026")
        assert dt.tzinfo == PARIS_TZ


# ── Test _parse_french_time ───────────────────────────────────────


class TestParseFrenchTime:
    """Tests for French time parsing."""

    def test_parses_hour_only(self):
        result = _parse_french_time("20h")
        assert result == (20, 0)

    def test_parses_hour_and_minutes(self):
        result = _parse_french_time("18h15")
        assert result == (18, 15)

    def test_parses_with_spaces(self):
        result = _parse_french_time("  20h30  ")
        assert result == (20, 30)

    def test_returns_none_for_invalid(self):
        assert _parse_french_time("not a time") is None
        assert _parse_french_time("") is None


# ── Test _parse_showtimes_from_html ───────────────────────────────


class TestParseShowtimesFromHtml:
    """Tests for extracting showtimes from detail page HTML."""

    def test_parses_multiple_dates(self, sample_detail_html):
        showtimes = _parse_showtimes_from_html(sample_detail_html)
        assert len(showtimes) >= 3  # At least 3 La Criée dates + possible tour

    def test_parses_date_components(self, sample_detail_html):
        showtimes = _parse_showtimes_from_html(sample_detail_html)
        # First showtime: 5 mars 2026, 20h
        first = showtimes[0]
        assert first["datetime"].year == 2026
        assert first["datetime"].month == 3
        assert first["datetime"].day == 5
        assert first["datetime"].hour == 20
        assert first["datetime"].minute == 0

    def test_parses_time_with_minutes(self, sample_detail_html):
        showtimes = _parse_showtimes_from_html(sample_detail_html)
        # Third showtime: 7 mars 2026, 18h15
        times_with_minutes = [st for st in showtimes if st["datetime"].minute == 15]
        assert len(times_with_minutes) >= 1
        assert times_with_minutes[0]["datetime"].hour == 18

    def test_parses_single_date(self, sample_detail_single_date):
        showtimes = _parse_showtimes_from_html(sample_detail_single_date)
        assert len(showtimes) == 1
        assert showtimes[0]["datetime"].day == 7
        assert showtimes[0]["datetime"].month == 4

    def test_deduplicates_showtimes(self):
        html = """
        <html><body>
            <p>15 mars 2026</p>
            <p>20h</p>
            <p>15 mars 2026</p>
            <p>20h</p>
        </body></html>
        """
        showtimes = _parse_showtimes_from_html(html)
        # Should deduplicate identical datetimes
        unique_times = {st["datetime"].isoformat() for st in showtimes}
        assert len(unique_times) == len(showtimes)

    def test_handles_no_dates(self):
        html = "<html><body><p>No dates here</p></body></html>"
        showtimes = _parse_showtimes_from_html(html)
        assert showtimes == []


# ── Test _find_venue_in_lines ─────────────────────────────────────


class TestFindVenueInLines:
    """Tests for venue detection in text lines."""

    def test_finds_criee_venue(self):
        lines = [
            "Représentation",
            "Première",
            "La Criée - Salle Déméter",
            "Prendre des places",
        ]
        venue = _find_venue_in_lines(lines, 0)
        assert venue is not None
        assert "La Criée" in venue

    def test_skips_labels(self):
        lines = [
            "Représentation",
            "Première",
            "La Criée - Salle Ouranos",
        ]
        venue = _find_venue_in_lines(lines, 0)
        assert venue is not None
        assert "La Criée" in venue

    def test_returns_none_when_no_venue(self):
        lines = [
            "Représentation",
            "Première",
            "Complet",
        ]
        venue = _find_venue_in_lines(lines, 0)
        assert venue is None

    def test_finds_university_venue(self):
        """Test that university venues are detected."""
        lines = [
            "Représentation",
            "Aix-Marseille Université",
            "Prendre des places",
        ]
        venue = _find_venue_in_lines(lines, 0)
        assert venue is not None
        assert "Université" in venue


# ── Test _is_external_venue ───────────────────────────────────────


class TestIsExternalVenue:
    """Tests for external venue detection."""

    def test_criee_venue_is_not_external(self):
        assert _is_external_venue("La Criée - Salle Déméter") is False
        assert _is_external_venue("La Criée - Salle Ouranos") is False

    def test_university_is_external(self):
        assert _is_external_venue("Aix-Marseille Université") is True
        assert _is_external_venue("Avec Aix-Marseille Université") is True

    def test_aix_en_provence_is_external(self):
        assert _is_external_venue("Théâtre du Bois de l'Aune - Aix-en-Provence") is True

    def test_none_is_not_external(self):
        """None venue (undetected) should not be considered external."""
        assert _is_external_venue(None) is False

    def test_empty_string_is_not_external(self):
        assert _is_external_venue("") is False

    def test_criee_with_university_is_not_external(self):
        """If venue explicitly mentions La Criée, it's not external."""
        assert _is_external_venue("La Criée - Université partenaire") is False


# ── Test _generate_source_id ──────────────────────────────────────


class TestGenerateSourceId:
    """Tests for source ID generation."""

    def test_generates_from_url(self):
        sid = _generate_source_id(
            "https://theatre-lacriee.com/programmation/evenements/la-lecon"
        )
        assert sid == "lacriee:la-lecon"

    def test_generates_from_url_with_hyphen(self):
        sid = _generate_source_id(
            "https://theatre-lacriee.com/programmation/evenements/dom-juan"
        )
        assert sid == "lacriee:dom-juan"


# ── Test LaCrieeParser integration ────────────────────────────────


class TestLaCrieeParserIntegration:
    """Integration tests for LaCrieeParser with mocked HTTP."""

    @pytest.fixture
    def mock_config(self, category_map):
        return {
            "name": "La Criée",
            "id": "lacriee",
            "url": "https://theatre-lacriee.com/programmation/spectacles",
            "parser": "lacriee",
            "rate_limit": {"delay_between_pages": 0.0},
            "category_map": category_map,
        }

    @pytest.fixture
    def parser(self, mock_config):
        http_client = MagicMock()
        image_downloader = MagicMock()
        markdown_generator = MagicMock()
        return LaCrieeParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=image_downloader,
            markdown_generator=markdown_generator,
        )

    def test_source_name(self, parser):
        assert parser.source_name == "La Criée"

    def test_parse_events_with_multi_date(
        self, parser, sample_listing_html, sample_detail_html
    ):
        """Test that multi-date events produce multiple Event objects."""
        parser.http_client.get_text.side_effect = [
            sample_detail_html,  # la-lecon
            sample_detail_html,  # carmen (reuse same fixture)
            sample_detail_html,  # dom-juan (reuse same fixture)
        ]

        html_parser = HTMLParser(
            sample_listing_html,
            "https://theatre-lacriee.com",
        )
        events = parser.parse_events(html_parser)

        assert len(events) > 0
        assert all(isinstance(e, Event) for e in events)
        assert all(e.name == "La Leçon" for e in events)

    def test_parse_events_single_date(self, parser, sample_detail_single_date):
        """Test single-date event."""
        listing_html = """
        <html><body>
            <a href="/programmation/evenements/kantorow">Kantorow</a>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [
            sample_detail_single_date,
        ]

        html_parser = HTMLParser(
            listing_html,
            "https://theatre-lacriee.com",
        )
        events = parser.parse_events(html_parser)

        assert len(events) == 1
        assert events[0].name == "Alexandre Kantorow"
        assert events[0].categories == ["musique"]

    def test_parse_events_empty_listing(self, parser):
        """Test graceful handling of empty listing page."""
        parser.http_client.get_text.return_value = ""

        html_parser = HTMLParser(
            "<html><body></body></html>",
            "https://theatre-lacriee.com",
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_handles_detail_page_failure(self, parser):
        """Test graceful handling when detail page fails to load."""
        listing_html = """
        <html><body>
            <a href="/programmation/evenements/test">Test</a>
        </body></html>
        """
        parser.http_client.get_text.return_value = ""

        html_parser = HTMLParser(
            listing_html,
            "https://theatre-lacriee.com",
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_extracts_og_image(self, parser, sample_detail_html):
        """Test that og:image is extracted from detail page."""
        listing_html = """
        <html><body>
            <a href="/programmation/evenements/la-lecon">La Leçon</a>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [sample_detail_html]

        html_parser = HTMLParser(
            listing_html,
            "https://theatre-lacriee.com",
        )
        events = parser.parse_events(html_parser)

        assert len(events) > 0
        assert (
            events[0].image
            == "https://theatre-lacriee.com/storage/2026/01/la-lecon.jpg"
        )

    def test_extracts_description(self, parser, sample_detail_html):
        """Test that description is extracted from detail page."""
        listing_html = """
        <html><body>
            <a href="/programmation/evenements/la-lecon">La Leçon</a>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [sample_detail_html]

        html_parser = HTMLParser(
            listing_html,
            "https://theatre-lacriee.com",
        )
        events = parser.parse_events(html_parser)

        assert len(events) > 0
        assert "frontière" in events[0].description

    def test_extracts_tags_from_subtitle(self, parser, sample_detail_external_venue):
        """Test that creator/director tags are extracted."""
        listing_html = """
        <html><body>
            <a href="/programmation/evenements/carmen">Carmen.</a>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [sample_detail_external_venue]

        html_parser = HTMLParser(
            listing_html,
            "https://theatre-lacriee.com",
        )
        events = parser.parse_events(html_parser)

        assert len(events) > 0
        assert any("françois gremaud" in t for t in events[0].tags)
        assert any("rosemary standley" in t for t in events[0].tags)

    def test_source_id_includes_datetime(self, parser, sample_detail_html):
        """Test that multi-date events get datetime-suffixed source IDs."""
        listing_html = """
        <html><body>
            <a href="/programmation/evenements/la-lecon">La Leçon</a>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [sample_detail_html]

        html_parser = HTMLParser(
            listing_html,
            "https://theatre-lacriee.com",
        )
        events = parser.parse_events(html_parser)

        source_ids = [e.source_id for e in events]
        assert len(source_ids) == len(set(source_ids)), "Source IDs should be unique"
        for sid in source_ids:
            assert sid.startswith("lacriee:la-lecon:")

    def test_location_defaults_to_la_criee(self, parser, sample_detail_single_date):
        """Test that location defaults to la-criee when venue mentions La Criée."""
        listing_html = """
        <html><body>
            <a href="/programmation/evenements/kantorow">Kantorow</a>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [sample_detail_single_date]

        html_parser = HTMLParser(
            listing_html,
            "https://theatre-lacriee.com",
        )
        events = parser.parse_events(html_parser)

        assert len(events) == 1
        assert "la-criee" in events[0].locations

    def test_filters_external_venue_tour_dates(self, parser):
        """Test that tour dates at external venues (e.g., universities) are filtered out."""
        detail_html = """
        <html>
        <head>
            <meta property="og:image" content="https://theatre-lacriee.com/storage/2026/01/test.jpg">
        </head>
        <body>
            <h1>Test Event</h1>
            <div>Théâtre</div>
            <p>A test event description that is long enough to be extracted as the description.</p>

            <div>
                <h3>Mercredi</h3>
                <p>10 mars 2026</p>
                <p>20h</p>
                <p>La Criée - Salle Déméter</p>
            </div>

            <div>
                <h3>Tournée</h3>
                <p>15 mars 2026</p>
                <p>20h</p>
                <p>Aix-Marseille Université</p>
            </div>
        </body>
        </html>
        """
        listing_html = """
        <html><body>
            <a href="/programmation/evenements/test-event">Test Event</a>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [detail_html]

        html_parser = HTMLParser(
            listing_html,
            "https://theatre-lacriee.com",
        )
        events = parser.parse_events(html_parser)

        # Should only have the La Criée date, not the university tour date
        assert len(events) == 1
        assert events[0].start_datetime.day == 10
        assert events[0].start_datetime.month == 3
