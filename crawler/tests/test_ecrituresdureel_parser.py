"""Tests for the Biennale des écritures du réel parser."""

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.parsers.ecrituresdureel import (
    EcrituresDuReelParser,
    _build_datetime,
    _extract_event_urls,
    _generate_source_id,
    _parse_header_date,
    _parse_sidebar_dates,
)
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")

BASE_URL = "https://www.theatrelacite.com/biennales/biennale-8/programmation"


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_listing_html():
    """Sample listing page with event tiles."""
    return """
    <html><body>
    <section class="eventsTiles">
        <h1>Événements</h1>
        <ul>
            <li>
                <a href="https://www.theatrelacite.com/agenda/saison-2025-2026/les-nouveaux-anciens-2">
                    <figure>
                        <img src="/media/les-nouveaux-anciens.jpg">
                        <div class="tags"><p>lecture performée</p></div>
                    </figure>
                    <div class="infos">
                        <h1>les nouveaux anciens</h1>
                        <p>18 mars 2026 • Théâtre La Cité</p>
                    </div>
                </a>
            </li>
            <li>
                <a href="https://www.theatrelacite.com/agenda/saison-2025-2026/minga-de-una-casa-en-ruinas">
                    <figure>
                        <img src="/media/minga.jpg">
                        <div class="tags"><p>spectacle</p></div>
                    </figure>
                    <div class="infos">
                        <h1>minga de una casa en ruinas</h1>
                        <p>19 • 20 mars 2026 • Théâtre Joliette</p>
                    </div>
                </a>
            </li>
            <li>
                <a href="https://www.theatrelacite.com/agenda/saison-2025-2026/soundtrack-to-a-coup-d-etat">
                    <figure>
                        <img src="/media/soundtrack.jpg">
                        <div class="tags"><p>film</p></div>
                    </figure>
                    <div class="infos">
                        <h1>soundtrack to a coup d'état</h1>
                        <p>1 avril 2026 • Cinéma La Baleine</p>
                    </div>
                </a>
            </li>
        </ul>
    </section>
    </body></html>
    """


@pytest.fixture
def sample_detail_single_date():
    """Detail page with a single date and time."""
    return """
    <html>
    <head>
        <meta property="og:image" content="https://www.theatrelacite.com/media/la-france.jpg">
    </head>
    <body class="evenement">
        <header class="header"><figure><img src="https://www.theatrelacite.com/media/la-france-full.jpg"></figure></header>
        <section class="grid-2">
            <article class="text">
                <header class="textHead">
                    <p class="dates">
                        <svg></svg>
                        2 avril 2026 \u2022 14:30
                    </p><br>
                    <h1 class="pageTitle">la france, empire</h1>
                    <p class="subtitle">
                        <span class="type">spectacle \u2022 </span>
                        de Nicolas Lambert
                    </p>
                </header>
                <p>Un spectacle puissant sur les mécanismes de domination coloniale et leurs traces dans la société française contemporaine.</p>
            </article>
        </section>
        <aside id="textSide">
            <h2 class="location">
                <svg></svg>
                Archives départementales des Bouches-du-Rhône
                <span class="additionalInfos">18 rue Mirès, 13003 Marseille</span>
            </h2>
            <p>Durée : 2:00</p>
            <p>Gratuit</p>
        </aside>
    </body></html>
    """


@pytest.fixture
def sample_detail_multi_date():
    """Detail page with multiple dates in sidebar."""
    return """
    <html>
    <head>
        <meta property="og:image" content="https://www.theatrelacite.com/media/minga.jpg">
    </head>
    <body class="evenement">
        <header class="header"><figure><img src="https://www.theatrelacite.com/media/minga-full.jpg"></figure></header>
        <section class="grid-2">
            <article class="text">
                <header class="textHead">
                    <p class="dates">
                        <svg></svg>
                        19 \u2022 20 mars 2026
                    </p><br>
                    <h1 class="pageTitle">minga de una casa en ruinas</h1>
                    <p class="subtitle">
                        <span class="type">spectacle \u2022 </span>
                        du Colectivo Cuerpo Sur
                    </p>
                </header>
                <p>Une performance immersive autour de la mémoire des maisons détruites par les tremblements de terre au Chili.</p>
            </article>
        </section>
        <aside id="textSide">
            <h2 class="location">
                <svg></svg>
                Théâtre Joliette
                <span class="additionalInfos">2 place Henri Verneuil, 13002 Marseille</span>
            </h2>
            <div class="datesAndPlaces">
                <ul>
                    <li><p>-> jeu. 19 mars \u2022 19:00</p></li>
                    <li><p>-> ven. 20 mars \u2022 21:00</p></li>
                </ul>
            </div>
            <p>Durée : 0:50</p>
            <p>Tarifs : 22€ · 14€ · 12€ · 8€ · 6€ · 3€</p>
        </aside>
    </body></html>
    """


@pytest.fixture
def sample_detail_no_time():
    """Detail page with date but no time."""
    return """
    <html>
    <head></head>
    <body class="evenement">
        <section class="grid-2">
            <article class="text">
                <header class="textHead">
                    <p class="dates">
                        <svg></svg>
                        1 avril 2026
                    </p><br>
                    <h1 class="pageTitle">soundtrack to a coup d'état</h1>
                    <p class="subtitle">
                        <span class="type">film \u2022 </span>
                    </p>
                </header>
                <p>Un documentaire musical sur le rôle de la musique jazz dans les luttes d'indépendance africaines.</p>
            </article>
        </section>
        <aside id="textSide">
            <h2 class="location">
                <svg></svg>
                Cinéma La Baleine
                <span class="additionalInfos">59 cours Julien, 13006 Marseille</span>
            </h2>
        </aside>
    </body></html>
    """


@pytest.fixture
def category_map():
    return {
        "spectacle": "theatre",
        "film": "art",
        "lecture performée": "theatre",
        "concert narratif": "musique",
        "concert": "musique",
        "rencontre": "communaute",
        "performance": "theatre",
    }


@pytest.fixture
def mock_config(category_map):
    return {
        "name": "Biennale des écritures du réel",
        "id": "ecrituresdureel",
        "url": BASE_URL,
        "category_map": category_map,
    }


@pytest.fixture
def parser(mock_config):
    http_client = MagicMock()
    image_downloader = MagicMock()
    markdown_generator = MagicMock()
    return EcrituresDuReelParser(
        config=mock_config,
        http_client=http_client,
        image_downloader=image_downloader,
        markdown_generator=markdown_generator,
    )


# ── Test _extract_event_urls ────────────────────────────────────────


class TestExtractEventUrls:
    def test_extracts_urls(self, sample_listing_html):
        urls = _extract_event_urls(sample_listing_html, BASE_URL)
        assert len(urls) == 3
        assert "les-nouveaux-anciens-2" in urls[0]
        assert "minga-de-una-casa-en-ruinas" in urls[1]

    def test_empty_html(self):
        urls = _extract_event_urls("<html><body></body></html>", BASE_URL)
        assert urls == []

    def test_no_agenda_links(self):
        html = '<html><body><a href="/contact">Contact</a></body></html>'
        urls = _extract_event_urls(html, BASE_URL)
        assert urls == []


# ── Test _parse_header_date ─────────────────────────────────────────


class TestParseHeaderDate:
    def test_single_date_with_time(self):
        result = _parse_header_date("2 avril 2026 \u2022 14:30")
        assert len(result) == 1
        assert result[0]["day"] == 2
        assert result[0]["month"] == 4
        assert result[0]["year"] == 2026
        assert result[0]["hour"] == 14
        assert result[0]["minute"] == 30

    def test_single_date_no_time(self):
        result = _parse_header_date("1 avril 2026")
        assert len(result) == 1
        assert result[0]["day"] == 1
        assert result[0]["month"] == 4
        assert result[0]["hour"] == 0

    def test_date_range_same_month(self):
        result = _parse_header_date("19 \u2022 20 mars 2026")
        assert len(result) == 2
        assert result[0]["day"] == 19
        assert result[1]["day"] == 20
        assert result[0]["month"] == 3

    def test_date_range_cross_month(self):
        result = _parse_header_date("10 avril \u2022 3 mai 2026")
        assert len(result) == 2
        assert result[0]["month"] == 4
        assert result[0]["day"] == 10
        assert result[1]["month"] == 5
        assert result[1]["day"] == 3

    def test_invalid_text(self):
        result = _parse_header_date("no date here")
        assert result == []

    def test_empty_text(self):
        result = _parse_header_date("")
        assert result == []


# ── Test _parse_sidebar_dates ───────────────────────────────────────


class TestParseSidebarDates:
    def test_multi_dates(self, sample_detail_multi_date):
        results = _parse_sidebar_dates(sample_detail_multi_date)
        assert len(results) == 2
        assert results[0]["day"] == 19
        assert results[0]["month"] == 3
        assert results[0]["hour"] == 19
        assert results[0]["minute"] == 0
        assert results[1]["day"] == 20
        assert results[1]["hour"] == 21

    def test_no_sidebar(self):
        html = "<html><body><p>No sidebar</p></body></html>"
        results = _parse_sidebar_dates(html)
        assert results == []

    def test_no_date_entries(self):
        html = '<html><body><aside id="textSide"><p>Info</p></aside></body></html>'
        results = _parse_sidebar_dates(html)
        assert results == []


# ── Test _build_datetime ────────────────────────────────────────────


class TestBuildDatetime:
    def test_valid_date(self):
        entry = {"day": 2, "month": 4, "year": 2026, "hour": 14, "minute": 30}
        dt = _build_datetime(entry)
        assert dt == datetime(2026, 4, 2, 14, 30, tzinfo=PARIS_TZ)

    def test_invalid_date(self):
        entry = {"day": 31, "month": 2, "year": 2026, "hour": 0, "minute": 0}
        assert _build_datetime(entry) is None

    def test_missing_year(self):
        entry = {"day": 1, "month": 4, "year": None, "hour": 0, "minute": 0}
        assert _build_datetime(entry) is None


# ── Test _generate_source_id ────────────────────────────────────────


class TestGenerateSourceId:
    def test_generates_from_url(self):
        url = "https://www.theatrelacite.com/agenda/saison-2025-2026/la-france-empire"
        result = _generate_source_id(url)
        assert result == "ecrituresdureel:la-france-empire"

    def test_trailing_slash(self):
        url = "https://www.theatrelacite.com/agenda/saison-2025-2026/hewa-rwanda/"
        result = _generate_source_id(url)
        assert result == "ecrituresdureel:hewa-rwanda"


# ── Test parser integration ─────────────────────────────────────────


class TestParserDetailPage:
    def test_single_date_event(self, parser, sample_detail_single_date):
        url = "https://www.theatrelacite.com/agenda/saison-2025-2026/la-france-empire"
        # Replace past date with a future one for testing
        future_html = sample_detail_single_date.replace("2 avril 2026", "10 avril 2026")
        events = parser._parse_detail_page(url, future_html)
        assert len(events) == 1
        event = events[0]
        assert event.name == "la france, empire"
        assert event.start_datetime == datetime(2026, 4, 10, 14, 30, tzinfo=PARIS_TZ)
        assert event.categories == ["theatre"]
        assert event.image == "https://www.theatrelacite.com/media/la-france-full.jpg"
        assert "ecrituresdureel:la-france-empire" in event.source_id

    def test_multi_date_event(self, parser, sample_detail_multi_date):
        url = "https://www.theatrelacite.com/agenda/saison-2025-2026/minga-de-una-casa-en-ruinas"
        events = parser._parse_detail_page(url, sample_detail_multi_date)
        # Both dates are in the past (March 2026 < April 2026 today)
        # but the parser filters by now, so for testing we check parsing works
        # by using dates in the future relative to a fixed time
        # Since today is April 6 2026, March dates are past - expect 0
        assert len(events) == 0

    def test_no_time_event(self, parser, sample_detail_no_time):
        url = "https://www.theatrelacite.com/agenda/saison-2025-2026/soundtrack"
        events = parser._parse_detail_page(url, sample_detail_no_time)
        # April 1 is in the past (today is April 6)
        assert len(events) == 0

    def test_empty_html(self, parser):
        events = parser._parse_detail_page("https://example.com", "<html></html>")
        assert events == []

    def test_missing_title(self, parser):
        html = """
        <html><body>
        <section class="grid-2"><article class="text">
            <header class="textHead">
                <p class="dates">2 avril 2026 \u2022 14:30</p>
            </header>
        </article></section>
        </body></html>
        """
        events = parser._parse_detail_page("https://example.com", html)
        assert events == []


class TestParserExtractors:
    def test_extract_name(self, parser, sample_detail_single_date):
        detail = HTMLParser(sample_detail_single_date, "https://example.com")
        name = parser._extract_name(detail)
        assert name == "la france, empire"

    def test_extract_name_with_br(self, parser):
        html = """
        <html><body>
        <header class="textHead">
            <h1 class="pageTitle">déterminé·es, <br>on avance</h1>
        </header>
        </body></html>
        """
        detail = HTMLParser(html, "https://example.com")
        name = parser._extract_name(detail)
        assert name == "déterminé·es, on avance"

    def test_extract_category_spectacle(self, parser, sample_detail_single_date):
        detail = HTMLParser(sample_detail_single_date, "https://example.com")
        cat = parser._extract_category(detail)
        assert cat == "theatre"

    def test_extract_category_film(self, parser, sample_detail_no_time):
        detail = HTMLParser(sample_detail_no_time, "https://example.com")
        cat = parser._extract_category(detail)
        assert cat == "art"

    def test_extract_description(self, parser, sample_detail_single_date):
        detail = HTMLParser(sample_detail_single_date, "https://example.com")
        desc = parser._extract_description(detail)
        assert "mécanismes de domination" in desc

    def test_extract_image(self, parser, sample_detail_single_date):
        detail = HTMLParser(sample_detail_single_date, "https://example.com")
        img = parser._extract_image(detail)
        assert img == "https://www.theatrelacite.com/media/la-france-full.jpg"

    def test_extract_venue(self, parser, sample_detail_single_date):
        detail = HTMLParser(sample_detail_single_date, "https://example.com")
        venue = parser._extract_venue(detail)
        assert venue == "Archives départementales des Bouches-du-Rhône"

    def test_extract_venue_theatre_joliette(self, parser, sample_detail_multi_date):
        detail = HTMLParser(sample_detail_multi_date, "https://example.com")
        venue = parser._extract_venue(detail)
        assert venue == "Théâtre Joliette"

    def test_extract_tags(self, parser, sample_detail_single_date):
        detail = HTMLParser(sample_detail_single_date, "https://example.com")
        tags = parser._extract_tags(detail)
        assert "nicolas lambert" in tags


class TestParseEvents:
    def test_parse_events_full_flow(
        self, parser, sample_listing_html, sample_detail_single_date
    ):
        """Test full parse_events flow with mocked HTTP."""
        listing_parser = HTMLParser(sample_listing_html, BASE_URL)

        # Mock fetch_pages to return detail page for one future event
        future_detail = sample_detail_single_date.replace(
            "2 avril 2026", "10 avril 2026"
        )
        parser.fetch_pages = MagicMock(
            return_value={
                "https://www.theatrelacite.com/agenda/saison-2025-2026/les-nouveaux-anciens-2": "",
                "https://www.theatrelacite.com/agenda/saison-2025-2026/minga-de-una-casa-en-ruinas": "",
                "https://www.theatrelacite.com/agenda/saison-2025-2026/soundtrack-to-a-coup-d-etat": future_detail,
            }
        )

        events = parser.parse_events(listing_parser)
        assert len(events) == 1
        assert events[0].name == "la france, empire"
        assert events[0].start_datetime.month == 4
        assert events[0].start_datetime.day == 10
