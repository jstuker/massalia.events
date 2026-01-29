"""Tests for the Agenda Culturel (13.agendaculturel.fr) parser."""

import json
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.agendaculturel import (
    CATEGORY_LISTING_URLS,
    AgendaCulturelParser,
    _extract_events_from_listing,
    _extract_json_ld,
    _is_marseille_area,
    _map_category,
    _parse_event_from_json_ld,
    _parse_event_from_microdata,
)
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_listing_html():
    """Sample Agenda Culturel listing page HTML with event cards."""
    return """
    <html lang="fr">
    <body>
        <div class="card cat-profil concert-profil hover-scale y-card"
             itemscope="" itemtype="https://schema.org/MusicEvent">
            <div class="row g-0">
                <div class="col-4 col-sm-3 col-md-12">
                    <div class="card-image position-relative">
                        <img alt="Randjess" height="230" loading="lazy"
                             src="https://13.agendaculturel.fr/media/storage/randjess.jpg/fit=cover,w=365,h=230"
                             width="365"/>
                        <meta content="https://13.agendaculturel.fr/media/storage/randjess.jpg/f=auto"
                              itemprop="image"/>
                    </div>
                </div>
                <div class="col-8 col-sm-9 col-md-12">
                    <div class="card-body px-md-4 text-md-center">
                        <p class="mb-md-0 position-relative">
                            <span class="badge card-main-badge">
                                <time datetime="2026-01-29T00:00:00+01:00">
                                    29 janv. 2026
                                </time>
                            </span>
                        </p>
                        <div class="h5 card-title">
                            <a class="stretched-link"
                               href="/concert/marseille/randjess.html"
                               itemprop="url">
                                <span itemprop="name">Randjess</span>
                                à Marseille
                            </a>
                        </div>
                        <div class="text-truncate" itemprop="location"
                             itemscope="" itemtype="https://schema.org/Place">
                            <span itemprop="name">Le Makeda</span>
                        </div>
                        <div class="d-none d-md-wb clamp clamp-3"
                             itemprop="description">
                            Randjess livre une pop rap intime.
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="card cat-profil theatre-profil hover-scale y-card"
             itemscope="" itemtype="https://schema.org/TheaterEvent">
            <div class="row g-0">
                <div class="col-4 col-sm-3 col-md-12">
                    <div class="card-image position-relative">
                        <img alt="Un chti à Marseille" height="230" loading="lazy"
                             src="https://13.agendaculturel.fr/media/storage/chti.jpg/fit=cover"
                             width="365"/>
                        <meta content="https://13.agendaculturel.fr/media/storage/chti.jpg/f=auto"
                              itemprop="image"/>
                    </div>
                </div>
                <div class="col-8 col-sm-9 col-md-12">
                    <div class="card-body px-md-4 text-md-center">
                        <p class="mb-md-0 position-relative">
                            <span class="badge card-main-badge">
                                Du
                                <time datetime="2026-02-04T00:00:00+01:00">4</time>
                                au
                                <time datetime="2026-02-25T00:00:00+01:00">25 févr. 2026</time>
                            </span>
                        </p>
                        <div class="h5 card-title">
                            <a class="stretched-link"
                               href="/theatre/marseille/un-chti-a-marseille-1.html"
                               itemprop="url">
                                <span itemprop="name">Un chti à Marseille</span>
                                à Marseille
                            </a>
                        </div>
                        <div class="text-truncate" itemprop="location"
                             itemscope="" itemtype="https://schema.org/Place">
                            <span itemprop="name">
                                La Comédie de Marseille Le Quai du Rire
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="card cat-profil concert-profil hover-scale y-card"
             itemscope="" itemtype="https://schema.org/MusicEvent">
            <div class="row g-0">
                <div class="col-8 col-sm-9 col-md-12">
                    <div class="card-body px-md-4 text-md-center">
                        <p class="mb-md-0 position-relative">
                            <span class="badge card-main-badge">
                                <time datetime="2026-01-30T00:00:00+01:00">
                                    30 janv. 2026
                                </time>
                            </span>
                        </p>
                        <div class="h5 card-title">
                            <a class="stretched-link"
                               href="/concert/aix-en-provence/violons-de-prague.html"
                               itemprop="url">
                                <span itemprop="name">Violons de Prague</span>
                                à Aix-en-Provence
                            </a>
                        </div>
                        <div class="text-truncate" itemprop="location"
                             itemscope="" itemtype="https://schema.org/Place">
                            <span itemprop="name">Eglise Saint-Jean De Malte</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="card cat-profil theatre-profil hover-scale x-card"
             itemscope="" itemtype="https://schema.org/TheaterEvent">
            <div class="row g-0">
                <div class="col-8 col-sm-9 col-md-12">
                    <div class="card-body px-md-4 text-md-center">
                        <p class="mb-md-0 position-relative">
                            <span class="badge card-main-badge">
                                <time datetime="2026-02-10T00:00:00+01:00">
                                    10 févr. 2026
                                </time>
                            </span>
                        </p>
                        <div class="h5 card-title">
                            <a class="stretched-link"
                               href="/theatre/marseille/pierre-emmanuel-barre-come-back.html"
                               itemprop="url">
                                <span itemprop="name">Pierre Emmanuel Barré Come Back</span>
                                à Marseille
                            </a>
                        </div>
                        <div class="text-truncate" itemprop="location"
                             itemscope="" itemtype="https://schema.org/Place">
                            <span itemprop="name">Le Dôme</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_html():
    """Sample event detail page HTML with JSON-LD."""
    json_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "MusicEvent",
            "name": "Randjess",
            "startDate": "2026-01-29T00:00:00+01:00",
            "endDate": "2026-01-29T00:00:00+01:00",
            "url": "https://13.agendaculturel.fr/concert/marseille/randjess.html",
            "image": "https://13.agendaculturel.fr/media/storage/randjess.jpg/f=auto",
            "description": "Randjess livre une pop rap intime et générationnelle.",
            "location": {
                "@type": "Place",
                "name": "Le Makeda",
                "url": "https://13.agendaculturel.fr/le-makeda",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "Marseille",
                    "streetAddress": "103, Rue Ferrari",
                    "postalCode": "13005",
                    "addressCountry": "FR",
                },
            },
            "offers": {
                "@type": "Offer",
                "priceCurrency": "EUR",
                "price": 18,
            },
        }
    )
    return f"""
    <html lang="fr">
    <head>
        <title>Concert Randjess à Marseille le 29 janvier 2026</title>
        <meta property="og:description"
              content="Randjess livre une pop rap intime et générationnelle.">
        <meta property="og:image"
              content="https://13.agendaculturel.fr/media/storage/randjess.jpg/f=auto">
        <script type="application/ld+json">{json_ld}</script>
    </head>
    <body>
        <h1>Concert Randjess à Marseille le 29 janvier 2026</h1>
        <time datetime="2026-01-29T00:00:00+01:00">jeudi 29 janvier 2026</time>
        <div itemprop="location" itemscope="" itemtype="https://schema.org/Place">
            <span itemprop="name">Le Makeda</span>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_json_ld():
    """A complete MusicEvent JSON-LD object from agendaculturel."""
    return {
        "@context": "https://schema.org",
        "@type": "MusicEvent",
        "name": "Randjess",
        "startDate": "2026-01-29T00:00:00+01:00",
        "endDate": "2026-01-29T00:00:00+01:00",
        "url": "https://13.agendaculturel.fr/concert/marseille/randjess.html",
        "image": "https://13.agendaculturel.fr/media/storage/randjess.jpg/f=auto",
        "description": "Randjess livre une pop rap intime et générationnelle.",
        "location": {
            "@type": "Place",
            "name": "Le Makeda",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "Marseille",
                "streetAddress": "103, Rue Ferrari",
                "postalCode": "13005",
                "addressCountry": "FR",
            },
        },
    }


@pytest.fixture
def category_map():
    """Standard category mapping from sources.yaml."""
    return {
        "MusicEvent": "musique",
        "TheaterEvent": "theatre",
        "DanceEvent": "danse",
        "VisualArtsEvent": "art",
        "Festival": "communaute",
        "ChildrensEvent": "theatre",
        "concert": "musique",
        "theatre": "theatre",
        "danse": "danse",
        "exposition": "art",
        "festival": "communaute",
    }


# ── Test _extract_events_from_listing ───────────────────────────────


class TestExtractEventsFromListing:
    """Tests for extracting events from listing page microdata."""

    def test_extracts_all_events(self, sample_listing_html):
        events = _extract_events_from_listing(sample_listing_html)
        assert len(events) == 4

    def test_extracts_event_names(self, sample_listing_html):
        events = _extract_events_from_listing(sample_listing_html)
        names = [e["name"] for e in events]
        assert "Randjess" in names
        assert "Un chti à Marseille" in names
        assert "Violons de Prague" in names

    def test_extracts_event_urls(self, sample_listing_html):
        events = _extract_events_from_listing(sample_listing_html)
        urls = [e["url"] for e in events]
        assert any("randjess.html" in u for u in urls)
        assert any("un-chti-a-marseille" in u for u in urls)

    def test_resolves_relative_urls(self, sample_listing_html):
        events = _extract_events_from_listing(sample_listing_html)
        for event in events:
            assert event["url"].startswith("https://13.agendaculturel.fr/")

    def test_extracts_dates(self, sample_listing_html):
        events = _extract_events_from_listing(sample_listing_html)
        randjess = next(e for e in events if e["name"] == "Randjess")
        assert "2026-01-29" in randjess["date"]

    def test_extracts_locations(self, sample_listing_html):
        events = _extract_events_from_listing(sample_listing_html)
        randjess = next(e for e in events if e["name"] == "Randjess")
        assert randjess["location"] == "Le Makeda"

    def test_extracts_images(self, sample_listing_html):
        events = _extract_events_from_listing(sample_listing_html)
        randjess = next(e for e in events if e["name"] == "Randjess")
        assert "randjess.jpg" in randjess["image"]

    def test_extracts_schema_types(self, sample_listing_html):
        events = _extract_events_from_listing(sample_listing_html)
        randjess = next(e for e in events if e["name"] == "Randjess")
        assert randjess["schema_type"] == "MusicEvent"
        chti = next(e for e in events if "chti" in e["name"])
        assert chti["schema_type"] == "TheaterEvent"

    def test_extracts_x_card_events(self, sample_listing_html):
        events = _extract_events_from_listing(sample_listing_html)
        names = [e["name"] for e in events]
        assert "Pierre Emmanuel Barré Come Back" in names

    def test_x_card_has_correct_schema_type(self, sample_listing_html):
        events = _extract_events_from_listing(sample_listing_html)
        peb = next(e for e in events if "Barré" in e["name"])
        assert peb["schema_type"] == "TheaterEvent"

    def test_x_card_has_correct_url(self, sample_listing_html):
        events = _extract_events_from_listing(sample_listing_html)
        peb = next(e for e in events if "Barré" in e["name"])
        assert "pierre-emmanuel-barre-come-back.html" in peb["url"]

    def test_only_x_card_html(self):
        html = """
        <html><body>
            <div class="x-card" itemscope="" itemtype="https://schema.org/MusicEvent">
                <a itemprop="url" href="/concert/marseille/test.html">
                    <span itemprop="name">X-Card Only Event</span>
                </a>
                <time datetime="2026-03-01T00:00:00+01:00">1 mars</time>
            </div>
        </body></html>
        """
        events = _extract_events_from_listing(html)
        assert len(events) == 1
        assert events[0]["name"] == "X-Card Only Event"

    def test_handles_empty_html(self):
        events = _extract_events_from_listing("<html><body></body></html>")
        assert events == []

    def test_skips_cards_without_name(self):
        html = """
        <html><body>
            <div class="y-card" itemscope="" itemtype="https://schema.org/MusicEvent">
                <a itemprop="url" href="/concert/marseille/test.html"></a>
            </div>
        </body></html>
        """
        events = _extract_events_from_listing(html)
        assert events == []

    def test_skips_cards_without_url(self):
        html = """
        <html><body>
            <div class="y-card" itemscope="" itemtype="https://schema.org/MusicEvent">
                <span itemprop="name">Test Event</span>
            </div>
        </body></html>
        """
        events = _extract_events_from_listing(html)
        assert events == []


# ── Test _extract_json_ld ────────────────────────────────────────────


class TestExtractJsonLd:
    """Tests for extracting JSON-LD data from HTML."""

    def test_extracts_json_ld(self, sample_detail_html):
        results = _extract_json_ld(sample_detail_html)
        assert len(results) == 1

    def test_parses_music_event(self, sample_detail_html):
        results = _extract_json_ld(sample_detail_html)
        assert results[0]["@type"] == "MusicEvent"
        assert results[0]["name"] == "Randjess"

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

    def test_parses_basic_event(self, sample_json_ld, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld,
            "https://13.agendaculturel.fr/concert/marseille/randjess.html",
            category_map,
        )
        assert event is not None
        assert event.name == "Randjess"
        assert (
            event.event_url
            == "https://13.agendaculturel.fr/concert/marseille/randjess.html"
        )

    def test_parses_start_datetime(self, sample_json_ld, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld,
            "https://13.agendaculturel.fr/concert/marseille/randjess.html",
            category_map,
        )
        assert event.start_datetime.year == 2026
        assert event.start_datetime.month == 1
        assert event.start_datetime.day == 29
        # Midnight gets defaulted to 20:00
        assert event.start_datetime.hour == 20

    def test_defaults_midnight_to_20h(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T00:00:00+01:00",
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://13.agendaculturel.fr/concert/marseille/test.html",
            category_map,
        )
        assert event.start_datetime.hour == 20

    def test_preserves_non_midnight_time(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T19:30:00+01:00",
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://13.agendaculturel.fr/concert/marseille/test.html",
            category_map,
        )
        assert event.start_datetime.hour == 19
        assert event.start_datetime.minute == 30

    def test_parses_description(self, sample_json_ld, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld,
            "https://13.agendaculturel.fr/concert/marseille/randjess.html",
            category_map,
        )
        assert "pop rap" in event.description

    def test_truncates_long_description(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T20:00:00+01:00",
            "description": "A" * 200,
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://13.agendaculturel.fr/concert/marseille/test.html",
            category_map,
        )
        assert len(event.description) <= 160

    def test_image_is_none_due_to_cloudflare(self, sample_json_ld, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld,
            "https://13.agendaculturel.fr/concert/marseille/randjess.html",
            category_map,
        )
        assert event.image is None

    def test_parses_location(self, sample_json_ld, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld,
            "https://13.agendaculturel.fr/concert/marseille/randjess.html",
            category_map,
        )
        assert len(event.locations) > 0

    def test_music_event_category(self, sample_json_ld, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld,
            "https://13.agendaculturel.fr/concert/marseille/randjess.html",
            category_map,
        )
        assert "musique" in event.categories

    def test_theater_event_category(self, category_map):
        json_ld = {
            "@type": "TheaterEvent",
            "name": "Test Theatre",
            "startDate": "2026-01-28T20:00:00+01:00",
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://13.agendaculturel.fr/theatre/marseille/test.html",
            category_map,
        )
        assert "theatre" in event.categories

    def test_source_id_from_url(self, sample_json_ld, category_map):
        event = _parse_event_from_json_ld(
            sample_json_ld,
            "https://13.agendaculturel.fr/concert/marseille/randjess.html",
            category_map,
        )
        assert event.source_id == "agendaculturel:concert/marseille/randjess"

    def test_returns_none_for_missing_name(self, category_map):
        json_ld = {"@type": "MusicEvent", "startDate": "2026-01-28T00:00:00+01:00"}
        event = _parse_event_from_json_ld(json_ld, "https://example.com", category_map)
        assert event is None

    def test_returns_none_for_missing_date(self, category_map):
        json_ld = {"@type": "MusicEvent", "name": "Test Event"}
        event = _parse_event_from_json_ld(json_ld, "https://example.com", category_map)
        assert event is None

    def test_handles_missing_location(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T20:00:00+01:00",
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://13.agendaculturel.fr/concert/marseille/test.html",
            category_map,
        )
        assert event.locations == []

    def test_handles_naive_datetime(self, category_map):
        json_ld = {
            "@type": "MusicEvent",
            "name": "Test",
            "startDate": "2026-01-28T19:00:00",
        }
        event = _parse_event_from_json_ld(
            json_ld,
            "https://13.agendaculturel.fr/concert/marseille/test.html",
            category_map,
        )
        assert event is not None
        assert event.start_datetime.tzinfo is not None


# ── Test _parse_event_from_microdata ─────────────────────────────────


class TestParseEventFromMicrodata:
    """Tests for creating events from listing page microdata."""

    def test_creates_event_from_microdata(self, category_map):
        data = {
            "name": "Test Event",
            "url": "https://13.agendaculturel.fr/concert/marseille/test.html",
            "date": "2026-01-29T00:00:00+01:00",
            "location": "Le Makeda",
            "image": "https://example.com/image.jpg",
            "description": "A test event.",
            "schema_type": "MusicEvent",
        }
        event = _parse_event_from_microdata(data, category_map)
        assert event is not None
        assert event.name == "Test Event"
        assert event.start_datetime.hour == 20  # Midnight -> 20:00

    def test_returns_none_without_name(self, category_map):
        data = {
            "name": "",
            "url": "https://example.com/test.html",
            "date": "2026-01-29T00:00:00+01:00",
        }
        assert _parse_event_from_microdata(data, category_map) is None

    def test_returns_none_without_url(self, category_map):
        data = {
            "name": "Test",
            "url": "",
            "date": "2026-01-29T00:00:00+01:00",
        }
        assert _parse_event_from_microdata(data, category_map) is None

    def test_returns_none_without_date(self, category_map):
        data = {
            "name": "Test",
            "url": "https://example.com/test.html",
            "date": "",
        }
        assert _parse_event_from_microdata(data, category_map) is None


# ── Test _map_category ───────────────────────────────────────────────


class TestMapCategory:
    """Tests for category mapping from schema type and URL."""

    def test_maps_music_event(self, category_map):
        result = _map_category(
            "MusicEvent",
            "https://13.agendaculturel.fr/concert/marseille/test.html",
            category_map,
        )
        assert result == "musique"

    def test_maps_theater_event(self, category_map):
        result = _map_category(
            "TheaterEvent",
            "https://13.agendaculturel.fr/theatre/marseille/test.html",
            category_map,
        )
        assert result == "theatre"

    def test_maps_dance_event(self, category_map):
        result = _map_category(
            "DanceEvent",
            "https://13.agendaculturel.fr/danse/marseille/test.html",
            category_map,
        )
        assert result == "danse"

    def test_maps_from_url_path(self, category_map):
        result = _map_category(
            "",
            "https://13.agendaculturel.fr/exposition/marseille/test.html",
            category_map,
        )
        assert result == "art"

    def test_maps_festival_from_url(self, category_map):
        result = _map_category(
            "",
            "https://13.agendaculturel.fr/festival/test.html",
            category_map,
        )
        assert result == "communaute"

    def test_unknown_defaults_to_communaute(self, category_map):
        result = _map_category(
            "UnknownType",
            "https://example.com/unknown/test.html",
            category_map,
        )
        assert result == "communaute"

    def test_category_map_takes_precedence(self):
        custom_map = {"MusicEvent": "custom_category"}
        result = _map_category(
            "MusicEvent",
            "https://example.com/concert/test.html",
            custom_map,
        )
        assert result == "custom_category"


# ── Test _is_marseille_area ──────────────────────────────────────────


class TestIsMarseilleArea:
    """Tests for Marseille area geographic filtering."""

    def test_marseille_url(self):
        assert _is_marseille_area(
            "https://13.agendaculturel.fr/concert/marseille/test.html"
        )

    def test_aix_en_provence_url(self):
        assert _is_marseille_area(
            "https://13.agendaculturel.fr/concert/aix-en-provence/test.html"
        )

    def test_aubagne_url(self):
        assert _is_marseille_area(
            "https://13.agendaculturel.fr/concert/aubagne/test.html"
        )

    def test_cassis_url(self):
        assert _is_marseille_area(
            "https://13.agendaculturel.fr/concert/cassis/test.html"
        )

    def test_excluded_city(self):
        assert not _is_marseille_area(
            "https://13.agendaculturel.fr/concert/paris/test.html"
        )

    def test_excluded_arles(self):
        assert not _is_marseille_area(
            "https://13.agendaculturel.fr/concert/arles/test.html"
        )

    def test_festival_without_city(self):
        # URLs like /festival/slug.html have no city, include them
        assert _is_marseille_area("https://13.agendaculturel.fr/festival/test.html")

    def test_city_from_location_data(self):
        assert _is_marseille_area(
            "https://13.agendaculturel.fr/unknown/path/test.html",
            city="Marseille",
        )

    def test_city_mismatch(self):
        assert not _is_marseille_area(
            "https://13.agendaculturel.fr/concert/lyon/test.html",
            city="Lyon",
        )


# ── Test AgendaCulturelParser integration ────────────────────────────


class TestAgendaCulturelParserIntegration:
    """Integration tests for AgendaCulturelParser with mocked Playwright."""

    @pytest.fixture
    def mock_config(self):
        return {
            "name": "Agenda Culturel",
            "id": "agendaculturel",
            "url": "https://13.agendaculturel.fr/",
            "parser": "agendaculturel",
            "rate_limit": {"delay_between_pages": 0.0},
            "category_map": {
                "MusicEvent": "musique",
                "TheaterEvent": "theatre",
                "DanceEvent": "danse",
                "concert": "musique",
                "theatre": "theatre",
            },
        }

    @pytest.fixture
    def parser(self, mock_config):
        http_client = MagicMock()
        image_downloader = MagicMock()
        markdown_generator = MagicMock()
        return AgendaCulturelParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=image_downloader,
            markdown_generator=markdown_generator,
        )

    def test_source_name(self, parser):
        assert parser.source_name == "Agenda Culturel"

    @patch("src.parsers.agendaculturel._run_playwright_in_thread")
    def test_fetch_page_uses_playwright(self, mock_pw, parser):
        mock_pw.return_value = "<html>OK</html>"
        result = parser.fetch_page("https://13.agendaculturel.fr/")
        assert result == "<html>OK</html>"
        mock_pw.assert_called_once()

    @patch("src.parsers.agendaculturel._run_playwright_in_thread")
    def test_fetch_page_returns_empty_on_failure(self, mock_pw, parser):
        mock_pw.return_value = None
        result = parser.fetch_page("https://13.agendaculturel.fr/")
        assert result == ""

    @patch("src.parsers.agendaculturel._run_playwright_in_thread")
    def test_fetch_page_detects_cloudflare_challenge(self, mock_pw, parser):
        mock_pw.return_value = "<html>Verify you are human</html>"
        result = parser.fetch_page("https://13.agendaculturel.fr/")
        assert result == ""

    @patch("src.parsers.agendaculturel._run_playwright_in_thread")
    def test_parse_events_with_json_ld(
        self, mock_pw, parser, sample_listing_html, sample_detail_html
    ):
        """Test full flow: listing page -> detail pages -> events."""
        mock_pw.return_value = sample_detail_html

        html_parser = HTMLParser(sample_listing_html, "https://13.agendaculturel.fr")
        events = parser.parse_events(html_parser)

        # Should have events from Marseille + Aix (3 events, all in area)
        assert len(events) > 0
        assert all(isinstance(e, Event) for e in events)

    @patch("src.parsers.agendaculturel._run_playwright_in_thread")
    def test_parse_events_handles_detail_failure(
        self, mock_pw, parser, sample_listing_html
    ):
        """Test fallback to microdata when detail pages fail."""
        mock_pw.return_value = None

        html_parser = HTMLParser(sample_listing_html, "https://13.agendaculturel.fr")
        events = parser.parse_events(html_parser)

        # Should still get events from microdata fallback
        assert len(events) > 0

    def test_parse_events_with_empty_listing(self, parser):
        html_parser = HTMLParser(
            "<html><body></body></html>", "https://13.agendaculturel.fr"
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_category_listing_urls_defined(self):
        assert len(CATEGORY_LISTING_URLS) == 5
        assert all(
            url.startswith("https://13.agendaculturel.fr/")
            for url in CATEGORY_LISTING_URLS
        )

    @patch("src.parsers.agendaculturel._run_playwright_in_thread")
    def test_crawl_iterates_category_pages(
        self, mock_pw, parser, sample_listing_html, sample_detail_html
    ):
        """Test that crawl() fetches all category listing pages."""
        mock_pw.return_value = sample_detail_html
        # Mock fetch_page to return listing HTML for category pages
        # and detail HTML for event pages
        category_urls = set(CATEGORY_LISTING_URLS)

        def mock_fetch(url):
            if url in category_urls:
                return sample_listing_html
            return sample_detail_html

        with patch.object(parser, "fetch_page", side_effect=mock_fetch):
            with patch.object(parser, "process_event", side_effect=lambda e: e):
                events = parser.crawl()

        assert len(events) > 0

    @patch("src.parsers.agendaculturel._run_playwright_in_thread")
    def test_crawl_deduplicates_across_pages(self, mock_pw, parser, sample_detail_html):
        """Test that events appearing in multiple categories are deduplicated."""
        # Same listing HTML returned for all category pages — same events
        listing_html = """
        <html><body>
            <div class="y-card" itemscope="" itemtype="https://schema.org/MusicEvent">
                <a itemprop="url" href="/concert/marseille/test.html">
                    <span itemprop="name">Shared Event</span>
                </a>
                <time datetime="2026-02-01T00:00:00+01:00">1 févr.</time>
            </div>
        </body></html>
        """
        category_urls = set(CATEGORY_LISTING_URLS)

        def mock_fetch(url):
            if url in category_urls:
                return listing_html
            return sample_detail_html

        with patch.object(parser, "fetch_page", side_effect=mock_fetch):
            with patch.object(parser, "process_event", side_effect=lambda e: e):
                events = parser.crawl()

        # Should only have 1 event despite being on all 5 category pages
        assert len(events) == 1


# ── Test HTML fallback parsing ────────────────────────────────────────


class TestHtmlFallbackParsing:
    """Tests for the HTML fallback when JSON-LD is unavailable."""

    @pytest.fixture
    def parser(self):
        config = {
            "name": "Agenda Culturel",
            "id": "agendaculturel",
            "url": "https://13.agendaculturel.fr/",
            "parser": "agendaculturel",
            "rate_limit": {"delay_between_pages": 0.0},
            "category_map": {},
        }
        return AgendaCulturelParser(
            config=config,
            http_client=MagicMock(),
            image_downloader=MagicMock(),
            markdown_generator=MagicMock(),
        )

    def test_parses_from_html_elements(self, parser):
        html = """
        <html>
        <head>
            <meta property="og:description" content="Un concert génial.">
            <meta property="og:image" content="https://example.com/image.jpg">
        </head>
        <body>
            <h1>Concert Test Event à Marseille le 29 janvier 2026</h1>
            <time datetime="2026-01-29T00:00:00+01:00">jeudi 29 janvier</time>
            <div itemprop="location" itemscope="">
                <span itemprop="name">Le Makeda</span>
            </div>
        </body>
        </html>
        """
        event = parser._parse_from_html(
            html, "https://13.agendaculturel.fr/concert/marseille/test.html"
        )
        assert event is not None
        assert "Test Event" in event.name
        assert event.start_datetime.month == 1
        assert event.start_datetime.day == 29

    def test_returns_none_without_h1(self, parser):
        html = """
        <html><body>
            <time datetime="2026-01-29T00:00:00+01:00">29 janv</time>
        </body></html>
        """
        event = parser._parse_from_html(html, "https://example.com/test.html")
        assert event is None

    def test_returns_none_without_date(self, parser):
        html = """
        <html><body>
            <h1>Test Event</h1>
        </body></html>
        """
        event = parser._parse_from_html(html, "https://example.com/test.html")
        assert event is None

    def test_image_is_none_due_to_cloudflare(self, parser):
        html = """
        <html>
        <head>
            <meta property="og:image" content="https://example.com/img.jpg">
        </head>
        <body>
            <h1>Test</h1>
            <time datetime="2026-03-15T00:00:00+01:00">15 mars</time>
        </body>
        </html>
        """
        event = parser._parse_from_html(html, "https://example.com/test.html")
        assert event is not None
        assert event.image is None
