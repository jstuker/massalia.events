"""Tests for the Le Cepac Silo parser."""

import json
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.cepacsilo import (
    CepacSiloParser,
    _extract_event_urls_from_html,
    _extract_json_ld,
    _generate_source_id,
    _parse_event_dates_from_html,
    _parse_event_from_json_ld,
    _parse_iso_datetime,
)
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_listing_html():
    """Sample Le Cepac Silo listing page with event cards."""
    return """
    <html>
    <body>
        <div class="bl-evc__list">
            <a href="/evenement/haroun/">
                <div class="card-event" data-title="HAROUN" data-category="One man show">
                    <img src="/wp-content/uploads/haroun.jpg" alt="HAROUN">
                    <div class="card-event__content">
                        <span class="card-event__tag">One man show</span>
                        <h3 class="card-event__title">HAROUN</h3>
                    </div>
                </div>
            </a>
            <a href="/evenement/djal-2/">
                <div class="card-event" data-title="D'JAL" data-category="One man show">
                    <img src="/wp-content/uploads/djal.jpg" alt="D'JAL">
                    <div class="card-event__content">
                        <span class="card-event__tag">One man show</span>
                        <h3 class="card-event__title">D'JAL</h3>
                    </div>
                </div>
            </a>
            <a href="/evenement/ballet-national/">
                <div class="card-event" data-title="Ballet National" data-category="Ballet">
                    <img src="/wp-content/uploads/ballet.jpg" alt="Ballet National">
                    <div class="card-event__content">
                        <span class="card-event__tag">Ballet</span>
                        <h3 class="card-event__title">Ballet National</h3>
                    </div>
                </div>
            </a>
            <!-- Non-event link -->
            <a href="/evenements/page/2/">Page 2</a>
        </div>
        <nav>
            <a href="https://www.cepacsilo-marseille.fr/evenements/page/2/">2</a>
            <a href="https://www.cepacsilo-marseille.fr/evenements/page/3/">3</a>
        </nav>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_html():
    """Sample event detail page with JSON-LD and multiple dates."""
    json_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "Event",
            "name": "HAROUN",
            "startDate": "2026-02-14T18:00:00.000000Z",
            "endDate": "2027-02-06T21:00:00.000000Z",
            "eventStatus": "https://schema.org/EventScheduled",
            "location": {
                "@type": "Place",
                "name": "CEPAC SILO",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": "35 quai du Lazaret",
                    "addressLocality": "Marseille",
                    "postalCode": "13002",
                    "addressCountry": "FR",
                },
            },
            "image": "https://www.cepacsilo-marseille.fr/wp-content/uploads/haroun.jpg",
            "description": "The Adventures of Kira and Morrison is coming to Snickertown in a can't miss performance.",
            "performer": {"@type": "Person", "name": "HAROUN"},
        }
    )
    return f"""
    <html>
    <head>
        <script type="application/ld+json">{json_ld}</script>
    </head>
    <body>
        <div class="content-header">
            <span class="term">One man show</span>
        </div>
        <h1 class="bl-he__title">HAROUN</h1>
        <h2>Bonjour quand même</h2>
        <div class="about">
            <p>NOUVEAU SPECTACLE - Haroun revient avec un spectacle hilarant et profond.</p>
        </div>
        <ul>
            <li>samedi 14 février 2026 · 18h00</li>
            <li>samedi 14 février 2026 · 21h00</li>
            <li>samedi 06 février 2027 · 18h00</li>
            <li>samedi 06 février 2027 · 21h00</li>
        </ul>
    </body>
    </html>
    """


@pytest.fixture
def sample_single_date_detail():
    """Sample event detail page with a single date."""
    json_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "Event",
            "name": "D'JAL",
            "startDate": "2026-12-06T20:30:00.000000Z",
            "endDate": "2026-12-06T20:30:00.000000Z",
            "eventStatus": "https://schema.org/EventScheduled",
            "location": {
                "@type": "Place",
                "name": "CEPAC SILO",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": "35 quai du Lazaret",
                    "addressLocality": "Marseille",
                    "postalCode": "13002",
                    "addressCountry": "FR",
                },
            },
            "image": "https://www.cepacsilo-marseille.fr/wp-content/uploads/djal.jpg",
            "description": "D'jal revient avec un nouveau spectacle.",
            "performer": {"@type": "Person", "name": "D'JAL"},
        }
    )
    return f"""
    <html>
    <head>
        <script type="application/ld+json">{json_ld}</script>
    </head>
    <body>
        <div class="content-header">
            <span class="term">One man show</span>
        </div>
        <h1 class="bl-he__title">D'JAL</h1>
        <div class="about">
            <p>D'jal revient avec un nouveau spectacle mêlant personnages dingues et situations folles!</p>
        </div>
        <ul>
            <li>dimanche 06 décembre 2026 · 20h30</li>
        </ul>
    </body>
    </html>
    """


@pytest.fixture
def sample_json_ld_event():
    """A complete Event JSON-LD object from Cepac Silo."""
    return {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": "DJAL",
        "startDate": "2026-02-06T20:30:00.000000Z",
        "endDate": "2026-02-06T20:30:00.000000Z",
        "eventStatus": "https://schema.org/EventScheduled",
        "location": {
            "@type": "Place",
            "name": "CEPAC SILO",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "35 quai du Lazaret",
                "addressLocality": "Marseille",
                "postalCode": "13002",
                "addressCountry": "FR",
            },
        },
        "image": "https://www.cepacsilo-marseille.fr/wp-content/uploads/djal.jpg",
        "description": "D'jal revient pour sa troisième édition.",
        "performer": {"@type": "Person", "name": "D'JAL"},
    }


@pytest.fixture
def category_map():
    """Standard category mapping from sources.yaml."""
    return {
        "Ballet": "danse",
        "Comédie musicale": "theatre",
        "Concert": "musique",
        "Concert - Rap/Urbain": "musique",
        "Danse": "danse",
        "Événement": "communaute",
        "Festival": "communaute",
        "Humour": "theatre",
        "Jeune Public": "theatre",
        "Magie": "theatre",
        "One man show": "theatre",
        "Spectacle": "theatre",
        "Théâtre": "theatre",
    }


# ── Test _extract_event_urls_from_html ────────────────────────────


class TestExtractEventUrls:
    """Tests for extracting event URLs from listing page HTML."""

    def test_extracts_event_urls(self, sample_listing_html):
        urls = _extract_event_urls_from_html(
            sample_listing_html,
            "https://www.cepacsilo-marseille.fr",
        )
        assert len(urls) == 3
        assert any("haroun" in u for u in urls)
        assert any("djal-2" in u for u in urls)
        assert any("ballet-national" in u for u in urls)

    def test_excludes_listing_page_links(self, sample_listing_html):
        urls = _extract_event_urls_from_html(
            sample_listing_html,
            "https://www.cepacsilo-marseille.fr",
        )
        assert not any("/evenements/" in u for u in urls)

    def test_resolves_relative_urls(self, sample_listing_html):
        urls = _extract_event_urls_from_html(
            sample_listing_html,
            "https://www.cepacsilo-marseille.fr",
        )
        for url in urls:
            assert url.startswith("https://")

    def test_handles_empty_html(self):
        urls = _extract_event_urls_from_html("<html><body></body></html>")
        assert urls == []

    def test_deduplicates_urls(self):
        html = """
        <html><body>
            <a href="/evenement/test/">Link 1</a>
            <a href="/evenement/test/">Link 2</a>
        </body></html>
        """
        urls = _extract_event_urls_from_html(html, "https://www.cepacsilo-marseille.fr")
        assert len(urls) == 1

    def test_handles_absolute_urls(self):
        html = """
        <html><body>
            <a href="https://www.cepacsilo-marseille.fr/evenement/test-event/">Test</a>
        </body></html>
        """
        urls = _extract_event_urls_from_html(html)
        assert len(urls) == 1
        assert urls[0] == "https://www.cepacsilo-marseille.fr/evenement/test-event/"


# ── Test _extract_json_ld ─────────────────────────────────────────


class TestExtractJsonLd:
    """Tests for extracting JSON-LD data from HTML."""

    def test_extracts_json_ld(self, sample_detail_html):
        results = _extract_json_ld(sample_detail_html)
        assert len(results) == 1
        assert results[0]["@type"] == "Event"

    def test_handles_no_json_ld(self):
        html = "<html><head></head><body></body></html>"
        results = _extract_json_ld(html)
        assert results == []

    def test_handles_invalid_json(self):
        html = '<html><head><script type="application/ld+json">{invalid</script></head></html>'
        results = _extract_json_ld(html)
        assert results == []

    def test_handles_multiple_scripts(self):
        data1 = json.dumps({"@type": "WebSite", "name": "Test"})
        data2 = json.dumps({"@type": "Event", "name": "Concert"})
        html = f"""
        <html><head>
            <script type="application/ld+json">{data1}</script>
            <script type="application/ld+json">{data2}</script>
        </head></html>
        """
        results = _extract_json_ld(html)
        assert len(results) == 2


# ── Test _parse_event_dates_from_html ─────────────────────────────


class TestParseEventDatesFromHtml:
    """Tests for extracting individual showtimes from HTML."""

    def test_parses_multiple_dates(self, sample_detail_html):
        dates = _parse_event_dates_from_html(sample_detail_html)
        assert len(dates) == 4

    def test_parses_date_components(self, sample_detail_html):
        dates = _parse_event_dates_from_html(sample_detail_html)
        # First date: samedi 14 février 2026 · 18h00
        assert dates[0].year == 2026
        assert dates[0].month == 2
        assert dates[0].day == 14
        assert dates[0].hour == 18
        assert dates[0].minute == 0
        assert dates[0].tzinfo == PARIS_TZ

    def test_parses_different_times(self, sample_detail_html):
        dates = _parse_event_dates_from_html(sample_detail_html)
        # Second date: samedi 14 février 2026 · 21h00
        assert dates[1].hour == 21
        assert dates[1].minute == 0

    def test_parses_single_date(self, sample_single_date_detail):
        dates = _parse_event_dates_from_html(sample_single_date_detail)
        assert len(dates) == 1
        assert dates[0].hour == 20
        assert dates[0].minute == 30

    def test_handles_no_dates(self):
        html = "<html><body><p>No dates here</p></body></html>"
        dates = _parse_event_dates_from_html(html)
        assert dates == []

    def test_handles_various_french_months(self):
        months_data = [
            ("janvier", 1),
            ("mars", 3),
            ("septembre", 9),
            ("décembre", 12),
        ]
        for month_name, month_num in months_data:
            html = f"<html><body><li>samedi 15 {month_name} 2026 · 20h30</li></body></html>"
            dates = _parse_event_dates_from_html(html)
            assert len(dates) == 1, f"Failed for {month_name}"
            assert dates[0].month == month_num, f"Wrong month for {month_name}"

    def test_handles_time_without_minutes(self):
        html = "<html><body><li>samedi 15 mars 2026 · 20h</li></body></html>"
        dates = _parse_event_dates_from_html(html)
        # The pattern requires at least "20h" which our regex handles (minutes optional)
        # This should match with minute=0 via the (\d{2})? group
        assert len(dates) == 1
        assert dates[0].hour == 20
        assert dates[0].minute == 0

    def test_excludes_dates_from_booking_modals(self):
        """Dates in modal-booking-event popups (main + related) must be ignored.

        The real site has the event's own dates in .bl-he__list-sessions in
        the article, and separate booking modals for the main event AND each
        related event.  Only .bl-he__list-sessions dates should be kept.
        """
        html = """
        <html><body>
            <ul class="bl-he__list-sessions">
                <li><time>dimanche 04 octobre 2026 · 17h00</time></li>
            </ul>
            <div class="modal modal-booking-event" data-title="BREL !">
                <ul class="list-date">
                    <li><span>dimanche 04 octobre 2026 · 17h00</span></li>
                </ul>
            </div>
            <div class="modal modal-booking-event" data-title="Jean dans la salle">
                <ul class="list-date">
                    <li><span>dimanche 01 février 2026 · 18h00</span></li>
                </ul>
            </div>
            <div class="modal modal-booking-event" data-title="GUS">
                <ul class="list-date">
                    <li><span>dimanche 07 juin 2026 · 19h00</span></li>
                </ul>
            </div>
        </body></html>
        """
        dates = _parse_event_dates_from_html(html)
        assert len(dates) == 1
        assert dates[0].month == 10
        assert dates[0].day == 4
        assert dates[0].hour == 17

    def test_excludes_dates_from_card_event_elements(self):
        """Dates inside card-event elements (related events carousel) must be ignored."""
        html = """
        <html><body>
            <ul>
                <li>samedi 15 mars 2026 · 20h30</li>
            </ul>
            <div class="card-event">
                <li>dimanche 01 février 2026 · 18h00</li>
            </div>
        </body></html>
        """
        dates = _parse_event_dates_from_html(html)
        assert len(dates) == 1
        assert dates[0].month == 3
        assert dates[0].day == 15


# ── Test _parse_event_from_json_ld ────────────────────────────────


class TestParseEventFromJsonLd:
    """Tests for converting JSON-LD to Event objects."""

    def test_parses_basic_event(self, sample_json_ld_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_event,
            "https://www.cepacsilo-marseille.fr/evenement/djal-2/",
            category_map,
        )
        assert event is not None
        assert event.name == "DJAL"
        assert event.event_url == "https://www.cepacsilo-marseille.fr/evenement/djal-2/"

    def test_parses_start_datetime(self, sample_json_ld_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_event,
            "https://www.cepacsilo-marseille.fr/evenement/djal-2/",
            category_map,
        )
        # 2026-02-06T20:30:00Z = 2026-02-06T21:30:00+01:00 in Paris
        assert event.start_datetime.year == 2026
        assert event.start_datetime.month == 2
        assert event.start_datetime.day == 6
        assert event.start_datetime.hour == 21  # UTC+1

    def test_ignores_placeholder_description(self, category_map):
        json_ld = {
            "@type": "Event",
            "name": "Test",
            "startDate": "2026-02-06T20:30:00.000000Z",
            "description": "The Adventures of Kira and Morrison is coming to Snickertown in a can't miss performance.",
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://www.cepacsilo-marseille.fr/evenement/test/",
            category_map,
        )
        assert event.description == ""

    def test_keeps_real_description(self, category_map):
        json_ld = {
            "@type": "Event",
            "name": "Test",
            "startDate": "2026-02-06T20:30:00.000000Z",
            "description": "Un spectacle magnifique à ne pas rater.",
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://www.cepacsilo-marseille.fr/evenement/test/",
            category_map,
        )
        assert event.description == "Un spectacle magnifique à ne pas rater."

    def test_parses_image(self, sample_json_ld_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_event,
            "https://www.cepacsilo-marseille.fr/evenement/djal-2/",
            category_map,
        )
        assert (
            event.image
            == "https://www.cepacsilo-marseille.fr/wp-content/uploads/djal.jpg"
        )

    def test_location_is_cepac_silo(self, sample_json_ld_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_event,
            "https://www.cepacsilo-marseille.fr/evenement/djal-2/",
            category_map,
        )
        assert "le-cepac-silo-marseille" in event.locations

    def test_extracts_performer_as_tag(self, sample_json_ld_event, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld_event,
            "https://www.cepacsilo-marseille.fr/evenement/djal-2/",
            category_map,
        )
        assert "d'jal" in event.tags

    def test_returns_none_for_missing_name(self, category_map):
        json_ld = {"@type": "Event", "startDate": "2026-02-06T20:30:00.000000Z"}
        event = _parse_event_from_json_ld(
            json_ld,
            "https://www.cepacsilo-marseille.fr/evenement/test/",
            category_map,
        )
        assert event is None

    def test_returns_none_for_missing_date(self, category_map):
        json_ld = {"@type": "Event", "name": "Test Event"}
        event = _parse_event_from_json_ld(
            json_ld,
            "https://www.cepacsilo-marseille.fr/evenement/test/",
            category_map,
        )
        assert event is None

    def test_truncates_long_description(self, category_map):
        json_ld = {
            "@type": "Event",
            "name": "Test",
            "startDate": "2026-02-06T20:30:00.000000Z",
            "description": "A" * 200,
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://www.cepacsilo-marseille.fr/evenement/test/",
            category_map,
        )
        assert len(event.description) <= 160

    def test_handles_no_image(self, category_map):
        json_ld = {
            "@type": "Event",
            "name": "Test",
            "startDate": "2026-02-06T20:30:00.000000Z",
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://www.cepacsilo-marseille.fr/evenement/test/",
            category_map,
        )
        assert event.image is None

    def test_handles_image_as_list(self, category_map):
        json_ld = {
            "@type": "Event",
            "name": "Test",
            "startDate": "2026-02-06T20:30:00.000000Z",
            "image": [
                "https://www.cepacsilo-marseille.fr/wp-content/uploads/img1.jpg",
                "https://www.cepacsilo-marseille.fr/wp-content/uploads/img2.jpg",
            ],
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://www.cepacsilo-marseille.fr/evenement/test/",
            category_map,
        )
        assert event.image == "https://www.cepacsilo-marseille.fr/wp-content/uploads/img1.jpg"

    def test_handles_image_as_dict(self, category_map):
        json_ld = {
            "@type": "Event",
            "name": "Test",
            "startDate": "2026-02-06T20:30:00.000000Z",
            "image": {
                "url": "https://www.cepacsilo-marseille.fr/wp-content/uploads/img.jpg",
            },
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://www.cepacsilo-marseille.fr/evenement/test/",
            category_map,
        )
        assert event.image == "https://www.cepacsilo-marseille.fr/wp-content/uploads/img.jpg"

    def test_handles_image_as_empty_list(self, category_map):
        json_ld = {
            "@type": "Event",
            "name": "Test",
            "startDate": "2026-02-06T20:30:00.000000Z",
            "image": [],
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://www.cepacsilo-marseille.fr/evenement/test/",
            category_map,
        )
        assert event.image is None

    def test_handles_multiple_performers(self, category_map):
        json_ld = {
            "@type": "Event",
            "name": "Festival",
            "startDate": "2026-02-06T20:30:00.000000Z",
            "performer": [
                {"@type": "Person", "name": "Artist A"},
                {"@type": "Person", "name": "Artist B"},
            ],
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://www.cepacsilo-marseille.fr/evenement/festival/",
            category_map,
        )
        assert "artist a" in event.tags
        assert "artist b" in event.tags


# ── Test _parse_iso_datetime ──────────────────────────────────────


class TestParseIsoDatetime:
    """Tests for ISO datetime parsing."""

    def test_parses_z_format(self):
        dt = _parse_iso_datetime("2026-02-06T20:30:00.000000Z")
        assert dt is not None
        assert dt.year == 2026
        assert dt.tzinfo == PARIS_TZ

    def test_parses_offset_format(self):
        dt = _parse_iso_datetime("2026-02-06T20:30:00+01:00")
        assert dt is not None
        assert dt.hour == 20

    def test_returns_none_for_invalid(self):
        dt = _parse_iso_datetime("not-a-date")
        assert dt is None

    def test_returns_none_for_empty(self):
        dt = _parse_iso_datetime("")
        assert dt is None


# ── Test _generate_source_id ──────────────────────────────────────


class TestGenerateSourceId:
    """Tests for source ID generation."""

    def test_generates_from_url(self):
        sid = _generate_source_id(
            "https://www.cepacsilo-marseille.fr/evenement/haroun/"
        )
        assert sid == "cepacsilo:haroun"

    def test_generates_from_url_with_suffix(self):
        sid = _generate_source_id(
            "https://www.cepacsilo-marseille.fr/evenement/djal-2/"
        )
        assert sid == "cepacsilo:djal-2"


# ── Test CepacSiloParser integration ─────────────────────────────


class TestCepacSiloParserIntegration:
    """Integration tests for CepacSiloParser with mocked HTTP."""

    @pytest.fixture
    def mock_config(self, category_map):
        return {
            "name": "Le Cepac Silo",
            "id": "cepacsilo",
            "url": "https://www.cepacsilo-marseille.fr/evenements/",
            "parser": "cepacsilo",
            "rate_limit": {"delay_between_pages": 0.0},
            "category_map": category_map,
        }

    @pytest.fixture
    def parser(self, mock_config):
        http_client = MagicMock()
        image_downloader = MagicMock()
        markdown_generator = MagicMock()
        return CepacSiloParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=image_downloader,
            markdown_generator=markdown_generator,
        )

    def test_source_name(self, parser):
        assert parser.source_name == "Le Cepac Silo"

    def test_parse_events_with_multi_date_event(
        self, parser, sample_listing_html, sample_detail_html
    ):
        """Test that multi-date events produce multiple Event objects."""
        # Mock fetch_page: page 2 returns empty (stop pagination),
        # then detail pages
        parser.http_client.get_text.side_effect = [
            "",  # Page 2 (empty, stops pagination)
            sample_detail_html,  # Detail: haroun
            sample_detail_html,  # Detail: djal-2
            sample_detail_html,  # Detail: ballet-national
        ]

        html_parser = HTMLParser(
            sample_listing_html,
            "https://www.cepacsilo-marseille.fr/evenements/",
        )
        events = parser.parse_events(html_parser)

        # Each detail page has 4 dates, but past dates are filtered out
        # All dates are in the future (2026-2027) so we expect events
        assert len(events) > 0
        assert all(isinstance(e, Event) for e in events)

    def test_parse_events_with_single_date(self, parser, sample_single_date_detail):
        """Test single-date event."""
        listing_html = """
        <html><body>
            <a href="/evenement/djal-2/">D'JAL</a>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [
            "",  # Page 2 (empty)
            sample_single_date_detail,  # Detail page
        ]

        html_parser = HTMLParser(
            listing_html,
            "https://www.cepacsilo-marseille.fr/evenements/",
        )
        events = parser.parse_events(html_parser)

        assert len(events) == 1
        assert events[0].name == "D'JAL"
        assert events[0].categories == ["theatre"]

    def test_parse_events_empty_listing(self, parser):
        """Test graceful handling of empty listing page."""
        # Mock fetch_page to return empty for pagination attempts
        parser.http_client.get_text.return_value = ""

        html_parser = HTMLParser(
            "<html><body></body></html>",
            "https://www.cepacsilo-marseille.fr/evenements/",
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_handles_detail_page_failure(self, parser):
        """Test graceful handling when detail page fails to load."""
        listing_html = """
        <html><body>
            <a href="/evenement/test/">Test</a>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [
            "",  # Page 2 (empty)
            "",  # Detail page fails
        ]

        html_parser = HTMLParser(
            listing_html,
            "https://www.cepacsilo-marseille.fr/evenements/",
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_handles_detail_page_without_json_ld(self, parser):
        """Test handling of detail page without JSON-LD."""
        listing_html = """
        <html><body>
            <a href="/evenement/test/">Test</a>
        </body></html>
        """
        detail_html = """
        <html>
        <head></head>
        <body><h1>Test Event</h1></body>
        </html>
        """
        parser.http_client.get_text.side_effect = [
            "",  # Page 2 (empty)
            detail_html,  # Detail without JSON-LD
        ]

        html_parser = HTMLParser(
            listing_html,
            "https://www.cepacsilo-marseille.fr/evenements/",
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_extracts_category_from_html(self, parser):
        """Test category extraction from .term element."""
        html = """
        <html><body>
            <div class="content-header">
                <span class="term">Concert</span>
            </div>
        </body></html>
        """
        category = parser._extract_category_from_html(html)
        assert category == "musique"

    def test_extracts_description_from_html(self, parser):
        """Test description extraction from .about element."""
        html = """
        <html><body>
            <div class="about">
                <p>Un spectacle incroyable avec des artistes exceptionnels dans un cadre unique.</p>
            </div>
        </body></html>
        """
        description = parser._extract_description_from_html(html)
        assert "spectacle incroyable" in description

    def test_source_id_includes_datetime_for_multi_date(
        self, parser, sample_detail_html
    ):
        """Test that multi-date events get datetime-suffixed source IDs."""
        listing_html = """
        <html><body>
            <a href="/evenement/haroun/">HAROUN</a>
        </body></html>
        """
        parser.http_client.get_text.side_effect = [
            "",  # Page 2 (empty)
            sample_detail_html,
        ]

        html_parser = HTMLParser(
            listing_html,
            "https://www.cepacsilo-marseille.fr/evenements/",
        )
        events = parser.parse_events(html_parser)

        # Each event should have a unique source_id with datetime suffix
        source_ids = [e.source_id for e in events]
        assert len(source_ids) == len(set(source_ids)), "Source IDs should be unique"
        for sid in source_ids:
            assert sid.startswith("cepacsilo:haroun:")
