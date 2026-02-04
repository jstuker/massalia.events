"""Tests for the Videodrome 2 parser."""

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.videodrome2 import (
    Videodrome2Parser,
    _extract_event_urls_from_html,
    _extract_json_ld,
    _generate_source_id,
    _parse_french_datetime_from_text,
)
from src.utils.parser import HTMLParser

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_listing_html():
    """Sample Videodrome 2 listing page HTML."""
    return """
    <html lang="fr">
    <body>
        <div class="event_item">
            <div class="event_thumbnail_wrap">
                <a href="https://www.videodrome2.fr/cine-club-lsf-les-sourds-en-colere/">
                    <img class="wp-post-image"
                         src="https://www.videodrome2.fr/wp-content/uploads/lsec-mea-300x218.png">
                </a>
            </div>
            <div class="event_data">
                <div class="event_date" style="display:none"></div>
                <h5><a href="https://www.videodrome2.fr/cine-club-lsf-les-sourds-en-colere/">
                    Cine-club LSF | Les Sourds en colere
                </a></h5>
            </div>
        </div>
        <div class="event_item">
            <div class="event_thumbnail_wrap">
                <a href="https://www.videodrome2.fr/des-films-en-commun-amours-chimiques/">
                    <img class="wp-post-image"
                         src="https://www.videodrome2.fr/wp-content/uploads/amours-mea-300x218.jpg">
                </a>
            </div>
            <div class="event_data">
                <div class="event_date" style="display:none"></div>
                <h5><a href="https://www.videodrome2.fr/des-films-en-commun-amours-chimiques/">
                    Des films en commun | Amours Chimiques
                </a></h5>
            </div>
        </div>
        <div class="event_item">
            <div class="event_thumbnail_wrap">
                <a href="https://www.videodrome2.fr/meme-pas-peur-10-the-substance/">
                    <img class="wp-post-image"
                         src="https://www.videodrome2.fr/wp-content/uploads/substance-300x218.jpg">
                </a>
            </div>
            <div class="event_data">
                <div class="event_date" style="display:none"></div>
                <h5><a href="https://www.videodrome2.fr/meme-pas-peur-10-the-substance/">
                    Meme Pas Peur! #10 | The Substance
                </a></h5>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_html():
    """Sample Videodrome 2 event detail page HTML."""
    return """
    <html lang="fr">
    <head>
        <meta property="og:description"
              content="Dans le cadre du cine-club LSF, projection du film Les Sourds en colere.">
        <meta property="og:image"
              content="https://www.videodrome2.fr/wp-content/uploads/lsec-mea.png">
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Article",
                    "headline": "Cine-club LSF | Les Sourds en colere de Jacques Sangla",
                    "datePublished": "2026-01-23T16:44:28+00:00",
                    "keywords": ["cine-club-lsf", "promo-social", "promo-teaser"],
                    "articleSection": ["Les seances de cinema", "LSF"],
                    "inLanguage": "fr-FR"
                },
                {
                    "@type": "event",
                    "name": "Cine-club LSF | Les Sourds en colere de Jacques Sangla",
                    "startDate": "2026-03-03T08:30:00+01:00",
                    "endDate": "2026-03-03T09:15:00+01:00",
                    "eventStatus": "EventScheduled",
                    "eventAttendanceMode": "OfflineEventAttendanceMode"
                }
            ]
        }
        </script>
    </head>
    <body>
        <h1>Cine-club LSF | Les Sourds en colere de Jacques Sangla</h1>
        <div class="entry-content">
            <p>mardi 3 mars 2026 de 20h30 a 21h15</p>
            <p>Les Sourds en colere de Jacques Sangla | 2022 | France | 52 min</p>
            <p>Dans le cadre des 20 ans du programme PiSourd, le cine-club LSF
               propose la projection du film Les Sourds en colere suivi d'un
               debat avec le realisateur et des acteurs sourds engages.</p>
            <p>Prix libre sans adhesion</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def detail_html_no_time():
    """Detail page HTML without explicit time."""
    return """
    <html lang="fr">
    <head>
        <meta property="og:description" content="Seance jeune public au Videodrome 2.">
        <meta property="og:image"
              content="https://www.videodrome2.fr/wp-content/uploads/jeune-public.jpg">
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Article",
                    "headline": "Atelier Jeune Public",
                    "articleSection": ["Les cycles Jeune Public"],
                    "keywords": ["jeune-public"]
                },
                {
                    "@type": "event",
                    "name": "Atelier Jeune Public",
                    "startDate": "2026-03-15T02:00:00+01:00",
                    "endDate": "2026-03-15T03:30:00+01:00",
                    "eventStatus": "EventScheduled"
                }
            ]
        }
        </script>
    </head>
    <body>
        <h1>Atelier Jeune Public</h1>
        <div class="entry-content">
            <p>samedi 15 mars 2026</p>
            <p>Un atelier dedie aux enfants pour decouvrir le cinema d'animation
               a travers des exercices pratiques et ludiques.</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def detail_html_with_dot_time():
    """Detail page with dot separator for time."""
    return """
    <html lang="fr">
    <head>
        <meta property="og:description"
              content="Projection du cycle Marseille sans soleil.">
        <meta property="og:image"
              content="https://www.videodrome2.fr/wp-content/uploads/mss.jpg">
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Article",
                    "headline": "Cycle Marseille sans soleil",
                    "articleSection": ["Les seances de cinema"],
                    "keywords": ["marseille-sans-soleil"]
                },
                {
                    "@type": "event",
                    "name": "Cycle Marseille sans soleil",
                    "startDate": "2026-02-06T08:30:00+01:00",
                    "endDate": "2026-02-06T10:15:00+01:00",
                    "eventStatus": "EventScheduled"
                }
            ]
        }
        </script>
    </head>
    <body>
        <h1>Cycle Marseille sans soleil</h1>
        <div class="entry-content">
            <p>Vendredi 6 fevrier 2026 · 20h30</p>
            <p>Marseille sans soleil est un cycle de films explorant la ville
               de Marseille a travers des documentaires independants et des
               films d'auteur.</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def detail_html_no_json_ld():
    """Detail page without JSON-LD data."""
    return """
    <html lang="fr">
    <head>
        <meta property="og:description" content="Soiree films fanzines.">
        <meta property="og:image"
              content="https://www.videodrome2.fr/wp-content/uploads/fanzine.jpg">
    </head>
    <body>
        <h1>Soiree Films Fanzines</h1>
        <div class="entry-content">
            <p>samedi 22 mars 2026 de 19h00 a 23h00</p>
            <p>Cine-concerts et courts-metrages avec des artistes locaux
               pour une soiree unique au Videodrome 2.</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_config():
    """Standard config for the parser."""
    return {
        "name": "Videodrome 2",
        "id": "videodrome2",
        "url": "https://www.videodrome2.fr/accueil/cinema-marseille/",
        "parser": "videodrome2",
        "rate_limit": {
            "requests_per_second": 0.5,
            "delay_between_pages": 0.0,
        },
        "category_map": {
            "Les séances de cinéma": "art",
            "Les seances de cinema": "art",
            "Les cycles Jeune Public": "art",
            "LSF": "art",
            "Cinéma": "art",
            "Projection": "art",
            "Ciné-concert": "musique",
            "Atelier": "communaute",
        },
    }


@pytest.fixture
def parser(mock_config):
    """Create a Videodrome2Parser instance with mocked dependencies."""
    http_client = MagicMock()
    image_downloader = MagicMock()
    markdown_generator = MagicMock()
    return Videodrome2Parser(
        config=mock_config,
        http_client=http_client,
        image_downloader=image_downloader,
        markdown_generator=markdown_generator,
    )


# ── Test _extract_event_urls_from_html ──────────────────────────────


class TestExtractEventUrls:
    """Tests for extracting event URLs from listing page."""

    def test_finds_event_urls(self, sample_listing_html):
        urls = _extract_event_urls_from_html(
            sample_listing_html,
            "https://www.videodrome2.fr/accueil/cinema-marseille/",
        )
        assert len(urls) == 3

    def test_returns_sorted_urls(self, sample_listing_html):
        urls = _extract_event_urls_from_html(
            sample_listing_html,
            "https://www.videodrome2.fr/accueil/cinema-marseille/",
        )
        assert urls == sorted(urls)

    def test_deduplicates_urls(self):
        html = """
        <html><body>
            <div class="event_item">
                <a href="https://www.videodrome2.fr/test-event/">Test</a>
                <a href="https://www.videodrome2.fr/test-event/">Test again</a>
            </div>
        </body></html>
        """
        urls = _extract_event_urls_from_html(
            html, "https://www.videodrome2.fr/"
        )
        assert len(urls) == 1

    def test_handles_empty_page(self):
        urls = _extract_event_urls_from_html(
            "<html><body></body></html>",
            "https://www.videodrome2.fr/",
        )
        assert urls == []

    def test_skips_home_page_links(self):
        html = """
        <html><body>
            <div class="event_item">
                <a href="https://www.videodrome2.fr/">Home</a>
            </div>
        </body></html>
        """
        urls = _extract_event_urls_from_html(
            html, "https://www.videodrome2.fr/"
        )
        assert len(urls) == 0

    def test_skips_category_page_links(self):
        html = """
        <html><body>
            <div class="event_item">
                <a href="https://www.videodrome2.fr/cinema-13006/">Category</a>
            </div>
        </body></html>
        """
        urls = _extract_event_urls_from_html(
            html, "https://www.videodrome2.fr/"
        )
        assert len(urls) == 0

    def test_resolves_relative_urls(self):
        html = """
        <html><body>
            <div class="event_item">
                <a href="/test-event/">Test</a>
            </div>
        </body></html>
        """
        urls = _extract_event_urls_from_html(
            html, "https://www.videodrome2.fr/"
        )
        assert len(urls) == 1
        assert urls[0].startswith("https://")

    def test_only_includes_videodrome2_urls(self):
        html = """
        <html><body>
            <div class="event_item">
                <a href="https://other-site.com/event/">External</a>
                <a href="https://www.videodrome2.fr/test-event/">Local</a>
            </div>
        </body></html>
        """
        urls = _extract_event_urls_from_html(
            html, "https://www.videodrome2.fr/"
        )
        assert len(urls) == 1
        assert "videodrome2.fr" in urls[0]


# ── Test _extract_json_ld ─────────────────────────────────────────


class TestExtractJsonLd:
    """Tests for JSON-LD extraction."""

    def test_extracts_graph_items(self, sample_detail_html):
        results = _extract_json_ld(sample_detail_html)
        assert len(results) == 2
        types = {item.get("@type") for item in results}
        assert "Article" in types
        assert "event" in types

    def test_handles_no_json_ld(self):
        results = _extract_json_ld("<html><body></body></html>")
        assert results == []

    def test_handles_invalid_json(self):
        html = """
        <html><body>
            <script type="application/ld+json">not valid json</script>
        </body></html>
        """
        results = _extract_json_ld(html)
        assert results == []

    def test_handles_single_object(self):
        html = """
        <html><body>
            <script type="application/ld+json">
            {"@type": "Event", "name": "Test"}
            </script>
        </body></html>
        """
        results = _extract_json_ld(html)
        assert len(results) == 1
        assert results[0]["@type"] == "Event"

    def test_handles_list(self):
        html = """
        <html><body>
            <script type="application/ld+json">
            [{"@type": "Event", "name": "Test1"}, {"@type": "Event", "name": "Test2"}]
            </script>
        </body></html>
        """
        results = _extract_json_ld(html)
        assert len(results) == 2


# ── Test _parse_french_datetime_from_text ───────────────────────────


class TestParseFrenchDatetime:
    """Tests for French date/time parsing."""

    def test_parses_full_datetime_with_de(self):
        result = _parse_french_datetime_from_text(
            "mardi 3 mars 2026 de 20h30 a 21h15"
        )
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 3
        assert result.hour == 20
        assert result.minute == 30

    def test_parses_datetime_with_dot_separator(self):
        result = _parse_french_datetime_from_text(
            "Vendredi 6 fevrier 2026 · 20h30"
        )
        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 6
        assert result.hour == 20
        assert result.minute == 30

    def test_parses_datetime_with_accent(self):
        result = _parse_french_datetime_from_text(
            "mercredi 12 février 2026 · 15h00"
        )
        assert result is not None
        assert result.month == 2
        assert result.day == 12
        assert result.hour == 15
        assert result.minute == 0

    def test_defaults_to_20h_when_no_time(self):
        result = _parse_french_datetime_from_text(
            "samedi 15 mars 2026"
        )
        assert result is not None
        assert result.hour == 20
        assert result.minute == 0

    def test_returns_none_for_no_date(self):
        result = _parse_french_datetime_from_text("just some text")
        assert result is None

    def test_returns_none_for_invalid_month(self):
        result = _parse_french_datetime_from_text("15 notamonth 2026")
        assert result is None

    def test_returns_none_for_empty_string(self):
        result = _parse_french_datetime_from_text("")
        assert result is None

    def test_parses_december(self):
        result = _parse_french_datetime_from_text(
            "25 decembre 2026 · 19h00"
        )
        assert result is not None
        assert result.month == 12
        assert result.day == 25
        assert result.hour == 19

    def test_parses_time_without_minutes(self):
        result = _parse_french_datetime_from_text(
            "5 mars 2026 de 19h"
        )
        assert result is not None
        assert result.hour == 19
        assert result.minute == 0

    def test_has_paris_timezone(self):
        result = _parse_french_datetime_from_text(
            "3 mars 2026 · 20h30"
        )
        assert result is not None
        assert result.tzinfo == PARIS_TZ


# ── Test _generate_source_id ──────────────────────────────────────


class TestGenerateSourceId:
    """Tests for source ID generation."""

    def test_generates_from_url(self):
        result = _generate_source_id(
            "https://www.videodrome2.fr/cine-club-lsf-les-sourds/"
        )
        assert result == "videodrome2:cine-club-lsf-les-sourds"

    def test_handles_trailing_slash(self):
        result = _generate_source_id(
            "https://www.videodrome2.fr/test-event/"
        )
        assert result == "videodrome2:test-event"

    def test_handles_no_trailing_slash(self):
        result = _generate_source_id(
            "https://www.videodrome2.fr/test-event"
        )
        assert result == "videodrome2:test-event"

    def test_handles_encoded_characters(self):
        result = _generate_source_id(
            "https://www.videodrome2.fr/cine-club-lsf-x-pisourd%c2%b7e/"
        )
        assert result.startswith("videodrome2:")
        assert len(result) > len("videodrome2:")

    def test_truncates_long_slugs(self):
        long_slug = "a" * 100
        result = _generate_source_id(
            f"https://www.videodrome2.fr/{long_slug}/"
        )
        # Source ID should be truncated
        assert len(result) <= len("videodrome2:") + 80


# ── Test _parse_detail_page ─────────────────────────────────────────


class TestParseDetailPage:
    """Tests for parsing event detail pages."""

    def test_parses_complete_event(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/cine-club-lsf-les-sourds-en-colere/"
        )
        assert event is not None
        assert "Sourds en colere" in event.name
        assert isinstance(event.start_datetime, datetime)

    def test_uses_body_time_not_json_ld(self, parser, sample_detail_html):
        """Verify we use the French text time (20h30) not JSON-LD (08:30)."""
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/cine-club-lsf-les-sourds-en-colere/"
        )
        assert event is not None
        assert event.start_datetime.hour == 20
        assert event.start_datetime.minute == 30

    def test_extracts_description(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/cine-club-lsf-les-sourds-en-colere/"
        )
        assert event is not None
        assert len(event.description) > 0

    def test_extracts_image(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/cine-club-lsf-les-sourds-en-colere/"
        )
        assert event is not None
        assert event.image is not None
        assert "lsec-mea" in event.image

    def test_extracts_category(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/cine-club-lsf-les-sourds-en-colere/"
        )
        assert event is not None
        assert "art" in event.categories

    def test_sets_location_to_videodrome2(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/cine-club-lsf-les-sourds-en-colere/"
        )
        assert event is not None
        assert "videodrome-2" in event.locations

    def test_generates_source_id(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/cine-club-lsf-les-sourds-en-colere/"
        )
        assert event is not None
        assert event.source_id == "videodrome2:cine-club-lsf-les-sourds-en-colere"

    def test_extracts_tags_without_promo(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/cine-club-lsf-les-sourds-en-colere/"
        )
        assert event is not None
        assert "cine-club-lsf" in event.tags
        # Promo tags should be filtered
        assert "promo-social" not in event.tags
        assert "promo-teaser" not in event.tags

    def test_defaults_time_to_20h(self, parser, detail_html_no_time):
        parser.http_client.get_text.return_value = detail_html_no_time
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/atelier-jeune-public/"
        )
        assert event is not None
        assert event.start_datetime.hour == 20
        assert event.start_datetime.minute == 0

    def test_parses_dot_separator_time(self, parser, detail_html_with_dot_time):
        parser.http_client.get_text.return_value = detail_html_with_dot_time
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/cycle-marseille-sans-soleil/"
        )
        assert event is not None
        assert event.start_datetime.hour == 20
        assert event.start_datetime.minute == 30

    def test_parses_without_json_ld(self, parser, detail_html_no_json_ld):
        parser.http_client.get_text.return_value = detail_html_no_json_ld
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/soiree-films-fanzines/"
        )
        assert event is not None
        assert event.name == "Soiree Films Fanzines"
        assert event.start_datetime.hour == 19
        assert event.start_datetime.minute == 0

    def test_returns_none_on_fetch_failure(self, parser):
        parser.http_client.get_text.side_effect = Exception("Network error")
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/test/"
        )
        assert event is None

    def test_returns_none_without_name(self, parser):
        html = """
        <html><body>
            <p>mardi 3 mars 2026 de 20h30</p>
        </body></html>
        """
        parser.http_client.get_text.return_value = html
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/no-name/"
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
            "https://www.videodrome2.fr/no-date/"
        )
        assert event is None


# ── Test category extraction ─────────────────────────────────────────


class TestCategoryExtraction:
    """Tests for category extraction from JSON-LD."""

    def test_maps_cinema_category(self, parser):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@graph": [
            {"@type": "Article", "articleSection": ["Les seances de cinema"]}
        ]}
        </script>
        </head><body><h1>Test</h1>
        <p>3 mars 2026 · 20h00</p></body></html>
        """
        parser.http_client.get_text.return_value = html
        event = parser._parse_detail_page("https://www.videodrome2.fr/test/")
        assert event is not None
        assert "art" in event.categories

    def test_maps_jeune_public_category(self, parser):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@graph": [
            {"@type": "Article", "articleSection": ["Les cycles Jeune Public"]}
        ]}
        </script>
        </head><body><h1>Test</h1>
        <p>3 mars 2026 · 14h00</p></body></html>
        """
        parser.http_client.get_text.return_value = html
        event = parser._parse_detail_page("https://www.videodrome2.fr/test/")
        assert event is not None
        assert "art" in event.categories

    def test_defaults_to_art_when_no_category(self, parser):
        html = """
        <html><head></head><body>
            <h1>Test Event</h1>
            <p>3 mars 2026 · 20h00</p>
        </body></html>
        """
        parser.http_client.get_text.return_value = html
        event = parser._parse_detail_page("https://www.videodrome2.fr/test/")
        assert event is not None
        assert "art" in event.categories


# ── Test image extraction ────────────────────────────────────────────


class TestImageExtraction:
    """Tests for image extraction."""

    def test_extracts_og_image(self, parser, sample_detail_html):
        parser.http_client.get_text.return_value = sample_detail_html
        event = parser._parse_detail_page(
            "https://www.videodrome2.fr/cine-club-lsf-les-sourds-en-colere/"
        )
        assert event is not None
        assert "lsec-mea.png" in event.image

    def test_extracts_wp_post_image(self, parser):
        html = """
        <html><head></head><body>
            <h1>Test</h1>
            <p>3 mars 2026 · 20h30</p>
            <img class="wp-post-image"
                 src="https://www.videodrome2.fr/wp-content/uploads/test-300x218.jpg">
        </body></html>
        """
        parser.http_client.get_text.return_value = html
        event = parser._parse_detail_page("https://www.videodrome2.fr/test/")
        assert event is not None
        assert event.image is not None
        # Should strip the size suffix to get full image
        assert "test.jpg" in event.image
        assert "300x218" not in event.image

    def test_handles_no_image(self, parser):
        html = """
        <html><head></head><body>
            <h1>Test</h1>
            <p>3 mars 2026 · 20h30</p>
        </body></html>
        """
        parser.http_client.get_text.return_value = html
        event = parser._parse_detail_page("https://www.videodrome2.fr/test/")
        assert event is not None
        assert event.image is None


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
            "https://www.videodrome2.fr/accueil/cinema-marseille/",
        )
        events = parser.parse_events(html_parser)

        assert len(events) > 0
        assert all(isinstance(e, Event) for e in events)

    def test_parse_events_handles_fetch_failure(self, parser, sample_listing_html):
        parser.http_client.get_text.side_effect = Exception("Network error")

        html_parser = HTMLParser(
            sample_listing_html,
            "https://www.videodrome2.fr/accueil/cinema-marseille/",
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_parse_events_empty_listing(self, parser):
        html_parser = HTMLParser(
            "<html><body></body></html>",
            "https://www.videodrome2.fr/accueil/cinema-marseille/",
        )
        events = parser.parse_events(html_parser)
        assert events == []

    def test_source_name(self, parser):
        assert parser.source_name == "Videodrome 2"

    def test_all_events_have_videodrome_location(
        self, parser, sample_listing_html, sample_detail_html
    ):
        """All events should be at Videodrome 2."""
        parser.http_client.get_text.return_value = sample_detail_html

        html_parser = HTMLParser(
            sample_listing_html,
            "https://www.videodrome2.fr/accueil/cinema-marseille/",
        )
        events = parser.parse_events(html_parser)

        for event in events:
            assert "videodrome-2" in event.locations

    def test_all_events_have_source_id(
        self, parser, sample_listing_html, sample_detail_html
    ):
        """All events should have a source ID."""
        parser.http_client.get_text.return_value = sample_detail_html

        html_parser = HTMLParser(
            sample_listing_html,
            "https://www.videodrome2.fr/accueil/cinema-marseille/",
        )
        events = parser.parse_events(html_parser)

        for event in events:
            assert event.source_id is not None
            assert event.source_id.startswith("videodrome2:")
