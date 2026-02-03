"""Tests for the Journal Zébuline (journalzebuline.fr) parser."""

import json
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.models.event import Event
from src.parsers.journalzebuline import (
    FRENCH_MONTHS,
    MARSEILLE_AREA_CITIES,
    MARSEILLE_VENUE_KEYWORDS,
    WP_API_BASE,
    WP_CATEGORY_IDS,
    WP_CATEGORY_MAP,
    WP_PER_PAGE,
    JournalZebulineParser,
    _clean_html,
    _extract_city,
    _extract_verse_blocks,
    _is_book_block,
    _is_marseille_area_event,
    _looks_like_date,
    _map_wp_categories_to_taxonomy,
    _map_wp_tags_to_category,
    _parse_all_french_dates,
    _parse_french_date,
)
from src.utils.http import FetchResult

PARIS_TZ = ZoneInfo("Europe/Paris")


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sample_verse_html_single_date():
    """Article HTML with a single date verse block."""
    return """
    <div class="entry-content">
        <p>A review of a wonderful concert in Marseille.</p>
        <pre class="wp-block-verse">C.L.<br>
<mark style="background-color:rgba(0, 0, 0, 0)"
      class="has-inline-color has-luminous-vivid-orange-color">30 janvier</mark><br>
<a href="https://www.theatre-oeuvre.com/">Théâtre de l'Oeuvre</a>, Marseille</pre>
    </div>
    """


@pytest.fixture
def sample_verse_html_date_range():
    """Article HTML with a date range verse block."""
    return """
    <div class="entry-content">
        <p>A preview of an upcoming show.</p>
        <pre class="wp-block-verse">AUTHOR NAME<br>
<mark style="background-color:rgba(0, 0, 0, 0)"
      class="has-inline-color has-luminous-vivid-orange-color">Du 3 au 5 février</mark><br>
<a href="https://www.lezef.org/">Le Zef</a>, scène nationale de Marseille</pre>
    </div>
    """


@pytest.fixture
def sample_verse_html_multi_days():
    """Article HTML with multiple days listed."""
    return """
    <div class="entry-content">
        <p>Performance over two days.</p>
        <pre class="wp-block-verse">A.F.<br>
<mark style="background-color:rgba(0, 0, 0, 0)"
      class="has-inline-color has-luminous-vivid-orange-color">23 et 24 janvier</mark><br>
<a href="https://www.lafriche.org/">La Friche</a>, Marseille</pre>
    </div>
    """


@pytest.fixture
def sample_verse_html_a_venir():
    """Article HTML with 'A venir' upcoming event block."""
    return """
    <div class="entry-content">
        <p>Review of a past event, plus upcoming.</p>
        <pre class="wp-block-verse">AUTHOR NAME<br><br>
Valentina a été donné les
<mark style="background-color:rgba(0, 0, 0, 0)"
      class="has-inline-color has-luminous-vivid-orange-color">20 et 21 janvier</mark>
à <a href="https://www.lagarance.com/">La Garance</a>,
scène nationale de Cavaillon.</pre>
        <pre class="wp-block-verse"><strong>
<mark style="background-color:rgba(0, 0, 0, 0)"
      class="has-inline-color has-luminous-vivid-orange-color">A venir<br></mark>
<mark style="background-color:rgba(0, 0, 0, 0)"
      class="has-inline-color has-black-color">L'Inouïe Nuit<br></mark></strong><br>
Description of the upcoming show.<br>
<mark style="background-color:rgba(0, 0, 0, 0)"
      class="has-inline-color has-luminous-vivid-orange-color">Du 28 au 31 janvier</mark><br><br>
<a href="https://www.lagarance.com/">La Garance</a>,
scène nationale de Cavaillon</pre>
    </div>
    """


@pytest.fixture
def sample_verse_html_book():
    """Article HTML with a book/publication verse block (should be skipped)."""
    return """
    <div class="entry-content">
        <p>Book review.</p>
        <pre class="wp-block-verse">La Librairie du vendredi - Tome 1
De Sawako Natori
Traduit du japonais par Jean-Baptiste Flamin
Le bruit du monde - 19,90 EUR</pre>
    </div>
    """


@pytest.fixture
def sample_verse_html_no_blocks():
    """Article HTML without any verse blocks."""
    return """
    <div class="entry-content">
        <p>This is just a regular article with no event details.</p>
    </div>
    """


@pytest.fixture
def sample_verse_html_venue_in_strong():
    """Article HTML with venue in <strong> tag instead of link."""
    return """
    <div class="entry-content">
        <p>A preview of an upcoming show.</p>
        <pre class="wp-block-verse">CHLOÉ MACAIRE<br>
<mark style="background-color:rgba(0, 0, 0, 0)"
      class="has-inline-color has-luminous-vivid-orange-color">Du 3 au 5 février </mark><br>
<strong>Le Zef</strong>, scène national de Marseille </pre>
    </div>
    """


@pytest.fixture
def sample_verse_html_bernardines():
    """Article HTML with Théâtre des Bernardines in <strong> tag (no link)."""
    return """
    <div class="entry-content">
        <p>A review of a show.</p>
        <pre class="wp-block-verse"><mark style="background-color:rgba(0, 0, 0, 0)"
      class="has-inline-color has-luminous-vivid-orange-color">Du 3 au 7 février</mark><br>
<strong>Théâtre des Bernardines, </strong>Marseille</pre>
    </div>
    """


@pytest.fixture
def sample_api_article():
    """Sample WordPress REST API article response."""
    return {
        "id": 134502,
        "date": "2026-01-28T12:47:31",
        "slug": "entre-tradition-et-modernite",
        "link": "https://journalzebuline.fr/entre-tradition-et-modernite/",
        "title": {"rendered": "Entre tradition et modernit&eacute;"},
        "content": {
            "rendered": """
            <p>A review of a concert in Marseille.</p>
            <pre class="wp-block-verse">A.F.<br>
<mark style="background-color:rgba(0, 0, 0, 0)"
      class="has-inline-color has-luminous-vivid-orange-color">30 janvier</mark><br>
<a href="https://www.mucem.org/">Mucem</a>, Marseille</pre>
            """
        },
        "excerpt": {"rendered": "<p>A great concert review.</p>"},
        "categories": [2877],  # Musiques
        "tags": [2927, 19082],
        "featured_media": 134503,
        "yoast_head_json": {
            "title": "Entre tradition et modernité - Journal Zébuline",
            "description": "Review of the concert at Mucem.",
            "og_image": [
                {
                    "url": "https://i0.wp.com/journalzebuline.fr/wp-content/uploads/test.jpg",
                    "width": 1000,
                    "height": 600,
                }
            ],
        },
        "_embedded": {
            "wp:term": [
                [
                    {"name": "Musiques", "taxonomy": "category"},
                    {"name": "Critiques", "taxonomy": "category"},
                ],
                [
                    {"name": "Marseille", "taxonomy": "post_tag"},
                    {"name": "Musiques", "taxonomy": "post_tag"},
                    {"name": "Festival", "taxonomy": "post_tag"},
                ],
            ],
            "wp:featuredmedia": [
                {
                    "source_url": "https://journalzebuline.fr/wp-content/uploads/test.jpg",
                    "media_details": {"width": 1000, "height": 600},
                }
            ],
        },
    }


@pytest.fixture
def category_map():
    """Standard category mapping from sources.yaml."""
    return {
        "Scenes": "theatre",
        "Musiques": "musique",
        "Arts visuels": "art",
        "Cinema": "art",
        "Cirque": "theatre",
        "Litterature": "communaute",
        "Danse": "danse",
        "Theatre": "theatre",
        "Festival": "communaute",
        "Exposition": "art",
    }


@pytest.fixture
def mock_config(category_map):
    """Parser configuration matching sources.yaml."""
    return {
        "name": "Journal Zébuline",
        "id": "journalzebuline",
        "url": "https://journalzebuline.fr/",
        "parser": "journalzebuline",
        "rate_limit": {
            "requests_per_second": 0.5,
            "delay_between_pages": 0.0,
        },
        "category_map": category_map,
    }


@pytest.fixture
def parser(mock_config):
    """Create a JournalZebulineParser with mocked dependencies."""
    http_client = MagicMock()
    image_downloader = MagicMock()
    markdown_generator = MagicMock()
    return JournalZebulineParser(
        config=mock_config,
        http_client=http_client,
        image_downloader=image_downloader,
        markdown_generator=markdown_generator,
    )


# ── Test _parse_french_date ────────────────────────────────────────


class TestParseFrenchDate:
    """Tests for parsing French dates from verse blocks."""

    def test_single_date(self):
        dt = _parse_french_date("30 janvier", reference_year=2026)
        assert dt is not None
        assert dt.day == 30
        assert dt.month == 1
        assert dt.year == 2026
        assert dt.hour == 20  # default time

    def test_single_date_with_year(self):
        dt = _parse_french_date("15 mars 2026")
        assert dt is not None
        assert dt.day == 15
        assert dt.month == 3
        assert dt.year == 2026

    def test_date_range(self):
        dt = _parse_french_date("Du 3 au 5 février", reference_year=2026)
        assert dt is not None
        assert dt.day == 3
        assert dt.month == 2
        assert dt.year == 2026

    def test_date_range_with_year(self):
        dt = _parse_french_date("Du 3 au 5 février 2026")
        assert dt is not None
        assert dt.day == 3
        assert dt.month == 2
        assert dt.year == 2026

    def test_multi_days(self):
        dt = _parse_french_date("23 et 24 janvier", reference_year=2026)
        assert dt is not None
        assert dt.day == 23
        assert dt.month == 1

    def test_jusquau(self):
        dt = _parse_french_date("Jusqu'au 31 janvier", reference_year=2026)
        assert dt is not None
        assert dt.day == 31
        assert dt.month == 1

    def test_a_venir_prefix(self):
        dt = _parse_french_date("A venir\n15 mars", reference_year=2026)
        assert dt is not None
        assert dt.day == 15
        assert dt.month == 3

    def test_all_months(self):
        """Verify all French month names are handled."""
        for month_name, month_num in FRENCH_MONTHS.items():
            dt = _parse_french_date(f"15 {month_name}", reference_year=2026)
            assert dt is not None, f"Failed to parse: 15 {month_name}"
            assert dt.month == month_num

    def test_empty_string(self):
        assert _parse_french_date("") is None

    def test_none_input(self):
        assert _parse_french_date(None) is None

    def test_no_month(self):
        assert _parse_french_date("15 xyz") is None

    def test_invalid_day(self):
        assert _parse_french_date("32 janvier", reference_year=2026) is None

    def test_timezone(self):
        dt = _parse_french_date("15 mars 2026")
        assert dt.tzinfo == PARIS_TZ


# ── Test _parse_all_french_dates ───────────────────────────────────


class TestParseAllFrenchDates:
    """Tests for parsing French dates returning all dates."""

    def test_single_date(self):
        dates = _parse_all_french_dates("30 janvier", reference_year=2026)
        assert len(dates) == 1
        assert dates[0].day == 30
        assert dates[0].month == 1

    def test_date_range_expands(self):
        """Date range 'Du 3 au 5 février' should return Feb 3, 4, and 5."""
        dates = _parse_all_french_dates("Du 3 au 5 février", reference_year=2026)
        assert len(dates) == 3
        assert [d.day for d in dates] == [3, 4, 5]
        assert all(d.month == 2 for d in dates)

    def test_two_days_with_et(self):
        """'23 et 24 janvier' should return both Jan 23 and 24."""
        dates = _parse_all_french_dates("23 et 24 janvier", reference_year=2026)
        assert len(dates) == 2
        assert [d.day for d in dates] == [23, 24]

    def test_list_with_commas_and_et(self):
        """'2, 3 et 5 février' should return Feb 2, 3, and 5."""
        dates = _parse_all_french_dates("2, 3 et 5 février", reference_year=2026)
        assert len(dates) == 3
        assert [d.day for d in dates] == [2, 3, 5]

    def test_jusquau(self):
        dates = _parse_all_french_dates("Jusqu'au 31 janvier", reference_year=2026)
        assert len(dates) == 1
        assert dates[0].day == 31

    def test_empty_string(self):
        assert _parse_all_french_dates("") == []

    def test_none_input(self):
        assert _parse_all_french_dates(None) == []

    def test_all_dates_have_timezone(self):
        dates = _parse_all_french_dates("Du 3 au 5 février", reference_year=2026)
        assert all(d.tzinfo == PARIS_TZ for d in dates)


# ── Test _extract_verse_blocks ─────────────────────────────────────


class TestExtractVerseBlocks:
    """Tests for extracting event data from wp-block-verse elements."""

    def test_single_date_block(self, sample_verse_html_single_date):
        blocks = _extract_verse_blocks(sample_verse_html_single_date)
        assert len(blocks) == 1
        assert "30 janvier" in blocks[0]["date_text"]
        assert "Théâtre de l'Oeuvre" in blocks[0]["venue_name"]
        assert "theatre-oeuvre" in blocks[0]["venue_url"]

    def test_date_range_block(self, sample_verse_html_date_range):
        blocks = _extract_verse_blocks(sample_verse_html_date_range)
        assert len(blocks) == 1
        assert "Du 3 au 5 février" in blocks[0]["date_text"]
        assert "Le Zef" in blocks[0]["venue_name"]

    def test_multi_days_block(self, sample_verse_html_multi_days):
        blocks = _extract_verse_blocks(sample_verse_html_multi_days)
        assert len(blocks) == 1
        assert "23 et 24 janvier" in blocks[0]["date_text"]

    def test_skips_book_blocks(self, sample_verse_html_book):
        blocks = _extract_verse_blocks(sample_verse_html_book)
        assert len(blocks) == 0

    def test_no_verse_blocks(self, sample_verse_html_no_blocks):
        blocks = _extract_verse_blocks(sample_verse_html_no_blocks)
        assert len(blocks) == 0

    def test_empty_html(self):
        blocks = _extract_verse_blocks("")
        assert blocks == []

    def test_city_extraction(self, sample_verse_html_single_date):
        blocks = _extract_verse_blocks(sample_verse_html_single_date)
        assert blocks[0]["city"].lower() == "marseille"

    def test_a_venir_block(self, sample_verse_html_a_venir):
        blocks = _extract_verse_blocks(sample_verse_html_a_venir)
        # Should have at least one block with a date
        assert len(blocks) >= 1
        # One block should have date from "20 et 21 janvier"
        dates = [b["date_text"] for b in blocks]
        assert any("20 et 21 janvier" in d for d in dates) or any(
            "28 au 31 janvier" in d for d in dates
        )

    def test_venue_in_strong_tag(self, sample_verse_html_venue_in_strong):
        """Venue in <strong> tag (no link) should be extracted."""
        blocks = _extract_verse_blocks(sample_verse_html_venue_in_strong)
        assert len(blocks) == 1
        assert "Le Zef" in blocks[0]["venue_name"]
        assert "Du 3 au 5 février" in blocks[0]["date_text"]

    def test_theatre_des_bernardines_in_strong(self, sample_verse_html_bernardines):
        """Théâtre des Bernardines in <strong> tag should be extracted."""
        blocks = _extract_verse_blocks(sample_verse_html_bernardines)
        assert len(blocks) == 1
        assert "Bernardines" in blocks[0]["venue_name"]
        assert "Du 3 au 7 février" in blocks[0]["date_text"]


# ── Test _is_book_block ────────────────────────────────────────────


class TestIsBookBlock:
    """Tests for book/publication block detection."""

    def test_detects_eur_price(self):
        assert _is_book_block("Le bruit du monde - 19,90 EUR")

    def test_detects_euro_symbol(self):
        assert _is_book_block("Prix: 15,00 €")

    def test_detects_traduit(self):
        assert _is_book_block("Traduit du japonais par Someone")

    def test_detects_editions(self):
        assert _is_book_block("Éditions Gallimard, 2026")

    def test_not_a_book(self):
        assert not _is_book_block("Concert at Mucem, Marseille")

    def test_empty_text(self):
        assert not _is_book_block("")


# ── Test _looks_like_date ──────────────────────────────────────────


class TestLooksLikeDate:
    """Tests for date text heuristic."""

    def test_single_date(self):
        assert _looks_like_date("30 janvier")

    def test_date_range(self):
        assert _looks_like_date("Du 3 au 5 février")

    def test_jusquau(self):
        assert _looks_like_date("Jusqu'au 31 mars")

    def test_non_date(self):
        assert not _looks_like_date("Concert de rock")

    def test_empty(self):
        assert not _looks_like_date("")


# ── Test _extract_city ────────────────────────────────────────────


class TestExtractCity:
    """Tests for city extraction from verse block text."""

    def test_marseille(self):
        city = _extract_city("Théâtre de l'Oeuvre|, Marseille")
        assert city.lower() == "marseille"

    def test_aix_en_provence(self):
        city = _extract_city("Grand Théâtre de Provence, Aix-en-Provence")
        assert "aix" in city.lower()

    def test_no_city(self):
        city = _extract_city("Some unknown venue")
        assert city == ""


# ── Test _is_marseille_area_event ─────────────────────────────────


class TestIsMarseilleAreaEvent:
    """Tests for Marseille area geographic filtering."""

    def test_city_marseille(self):
        assert _is_marseille_area_event({"city": "Marseille"})

    def test_city_aix(self):
        assert _is_marseille_area_event({"city": "Aix-en-Provence"})

    def test_venue_mucem(self):
        assert _is_marseille_area_event(
            {"venue_name": "Mucem", "city": "", "venue_url": "", "full_text": ""}
        )

    def test_venue_la_friche(self):
        assert _is_marseille_area_event(
            {"venue_name": "La Friche", "city": "", "venue_url": "", "full_text": ""}
        )

    def test_full_text_marseille(self):
        assert _is_marseille_area_event(
            {
                "venue_name": "",
                "city": "",
                "venue_url": "",
                "full_text": "Concert at Marseille",
            }
        )

    def test_non_marseille(self):
        assert not _is_marseille_area_event(
            {
                "venue_name": "La Garance",
                "city": "Cavaillon",
                "venue_url": "https://www.lagarance.com/",
                "full_text": "La Garance, Cavaillon",
            }
        )

    def test_empty_block(self):
        assert not _is_marseille_area_event(
            {"venue_name": "", "city": "", "venue_url": "", "full_text": ""}
        )


# ── Test _map_wp_categories_to_taxonomy ───────────────────────────


class TestMapWpCategoriesToTaxonomy:
    """Tests for mapping WordPress categories to standard taxonomy."""

    def test_musiques(self):
        assert _map_wp_categories_to_taxonomy([2877], {}) == "musique"

    def test_scenes(self):
        assert _map_wp_categories_to_taxonomy([2876], {}) == "theatre"

    def test_arts_visuels(self):
        assert _map_wp_categories_to_taxonomy([2884], {}) == "art"

    def test_cinema(self):
        assert _map_wp_categories_to_taxonomy([2878], {}) == "art"

    def test_cirque(self):
        assert _map_wp_categories_to_taxonomy([5659], {}) == "theatre"

    def test_unknown_category(self):
        assert _map_wp_categories_to_taxonomy([99999], {}) == "communaute"

    def test_empty_categories(self):
        assert _map_wp_categories_to_taxonomy([], {}) == "communaute"

    def test_first_match_wins(self):
        # If article has both musiques and scenes, musiques comes first
        result = _map_wp_categories_to_taxonomy([2877, 2876], {})
        assert result == "musique"


# ── Test _map_wp_tags_to_category ────────────────────────────────


class TestMapWpTagsToCategory:
    """Tests for category mapping from tag names."""

    def test_danse_tag(self):
        assert _map_wp_tags_to_category(["Danse"], {}) == "danse"

    def test_concert_tag(self):
        assert _map_wp_tags_to_category(["Concert"], {}) == "musique"

    def test_theatre_tag(self):
        assert _map_wp_tags_to_category(["Théâtre"], {}) == "theatre"

    def test_exposition_tag(self):
        assert _map_wp_tags_to_category(["Exposition"], {}) == "art"

    def test_unknown_tag(self):
        assert _map_wp_tags_to_category(["SomeRandomTag"], {}) is None

    def test_empty_tags(self):
        assert _map_wp_tags_to_category([], {}) is None

    def test_config_map_takes_precedence(self):
        config_map = {"Festival": "communaute"}
        result = _map_wp_tags_to_category(["Festival"], config_map)
        assert result == "communaute"


# ── Test _clean_html ────────────────────────────────────────────────


class TestCleanHtml:
    """Tests for HTML tag removal and entity decoding."""

    def test_removes_tags(self):
        assert _clean_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_decodes_entities(self):
        assert _clean_html("caf&eacute;") == "caf&eacute;"  # Only basic entities
        assert _clean_html("A &amp; B") == "A & B"

    def test_normalizes_whitespace(self):
        assert _clean_html("  Hello   world  ") == "Hello world"

    def test_empty_string(self):
        assert _clean_html("") == ""

    def test_none_input(self):
        assert _clean_html(None) == ""

    def test_decodes_smart_quotes(self):
        assert _clean_html("&#8220;hello&#8221;") == '"hello"'


# ── Test JournalZebulineParser integration ─────────────────────────


class TestJournalZebulineParserIntegration:
    """Integration tests for JournalZebulineParser."""

    def test_source_name(self, parser):
        assert parser.source_name == "Journal Zébuline"

    def test_source_id(self, parser):
        assert parser.source_id == "journalzebuline"

    def test_parse_events_returns_empty(self, parser):
        """parse_events() is unused; should return empty list."""
        from src.utils.parser import HTMLParser

        html_parser = HTMLParser("<html></html>", "https://journalzebuline.fr")
        assert parser.parse_events(html_parser) == []

    def test_parse_article_extracts_event(self, parser, sample_api_article):
        """Test parsing a single API article into events."""
        events = parser._parse_article(sample_api_article)
        assert len(events) >= 1
        event = events[0]
        assert isinstance(event, Event)
        assert "modernit" in event.name.lower() or "tradition" in event.name.lower()
        assert event.start_datetime.month == 1
        assert event.start_datetime.day == 30

    def test_parse_article_sets_source_id(self, parser, sample_api_article):
        events = parser._parse_article(sample_api_article)
        assert len(events) >= 1
        assert events[0].source_id.startswith("journalzebuline:134502")

    def test_parse_article_sets_category(self, parser, sample_api_article):
        events = parser._parse_article(sample_api_article)
        assert len(events) >= 1
        assert "musique" in events[0].categories

    def test_parse_article_sets_description(self, parser, sample_api_article):
        events = parser._parse_article(sample_api_article)
        assert len(events) >= 1
        assert events[0].description != ""

    def test_parse_article_sets_image(self, parser, sample_api_article):
        events = parser._parse_article(sample_api_article)
        assert len(events) >= 1
        assert events[0].image is not None
        assert "journalzebuline.fr" in events[0].image

    def test_parse_article_sets_url(self, parser, sample_api_article):
        events = parser._parse_article(sample_api_article)
        assert len(events) >= 1
        assert "journalzebuline.fr" in events[0].event_url

    def test_parse_article_extracts_tags(self, parser, sample_api_article):
        events = parser._parse_article(sample_api_article)
        assert len(events) >= 1
        tags = events[0].tags
        assert any("marseille" in t.lower() for t in tags)

    def test_parse_article_skips_non_marseille(self, parser):
        """Articles about non-Marseille events should be skipped."""
        article = {
            "id": 99999,
            "date": "2026-01-28T12:00:00",
            "link": "https://journalzebuline.fr/article/",
            "title": {"rendered": "Concert in Paris"},
            "content": {
                "rendered": """
                <pre class="wp-block-verse">
<mark style="background-color:rgba(0, 0, 0, 0)"
      class="has-inline-color has-luminous-vivid-orange-color">15 février</mark><br>
<a href="https://www.example.com/">La Villette</a>, Paris</pre>
                """
            },
            "excerpt": {"rendered": ""},
            "categories": [2876],
            "tags": [],
            "_embedded": {"wp:term": [], "wp:featuredmedia": []},
        }
        events = parser._parse_article(article)
        assert len(events) == 0

    def test_parse_article_empty_content(self, parser):
        article = {
            "id": 99998,
            "date": "2026-01-28T12:00:00",
            "link": "https://journalzebuline.fr/article/",
            "title": {"rendered": "Empty Article"},
            "content": {"rendered": ""},
            "excerpt": {"rendered": ""},
            "categories": [2876],
            "tags": [],
            "_embedded": {"wp:term": [], "wp:featuredmedia": []},
        }
        events = parser._parse_article(article)
        assert len(events) == 0

    def test_parse_article_no_verse_blocks(self, parser):
        article = {
            "id": 99997,
            "date": "2026-01-28T12:00:00",
            "link": "https://journalzebuline.fr/article/",
            "title": {"rendered": "Regular Article"},
            "content": {"rendered": "<p>Just a regular article.</p>"},
            "excerpt": {"rendered": ""},
            "categories": [2876],
            "tags": [],
            "_embedded": {"wp:term": [], "wp:featuredmedia": []},
        }
        events = parser._parse_article(article)
        assert len(events) == 0

    def test_extract_article_image_from_embedded(self, parser):
        article = {
            "_embedded": {
                "wp:featuredmedia": [{"source_url": "https://example.com/image.jpg"}]
            },
        }
        url = parser._extract_article_image(article)
        assert url == "https://example.com/image.jpg"

    def test_extract_article_image_from_yoast(self, parser):
        article = {
            "_embedded": {},
            "yoast_head_json": {
                "og_image": [{"url": "https://example.com/og-image.jpg"}]
            },
        }
        url = parser._extract_article_image(article)
        assert url == "https://example.com/og-image.jpg"

    def test_extract_article_image_none(self, parser):
        article = {"_embedded": {}}
        url = parser._extract_article_image(article)
        assert url is None

    def test_extract_tag_names(self, parser, sample_api_article):
        tags = parser._extract_tag_names(sample_api_article)
        assert "Marseille" in tags
        assert "Festival" in tags

    def test_extract_tag_names_empty(self, parser):
        article = {"_embedded": {"wp:term": []}}
        tags = parser._extract_tag_names(article)
        assert tags == []

    def test_extract_tag_names_skips_categories(self, parser):
        article = {
            "_embedded": {
                "wp:term": [
                    [
                        {"name": "Musiques", "taxonomy": "category"},
                        {"name": "MyTag", "taxonomy": "post_tag"},
                    ]
                ]
            }
        }
        tags = parser._extract_tag_names(article)
        assert "MyTag" in tags
        assert "Musiques" not in tags


# ── Test crawl() flow ──────────────────────────────────────────────


class TestCrawlFlow:
    """Tests for the full crawl() flow with mocked HTTP."""

    def _make_fetch_result(self, articles, total=None, total_pages=None):
        """Helper to create a FetchResult mimicking the WordPress API."""
        if total is None:
            total = len(articles)
        if total_pages is None:
            total_pages = 1
        return FetchResult(
            url="https://journalzebuline.fr/wp-json/wp/v2/posts",
            status_code=200,
            html=json.dumps(articles),
            headers={
                "X-WP-Total": str(total),
                "X-WP-TotalPages": str(total_pages),
            },
        )

    @pytest.fixture
    def parser_with_mock_http(self, mock_config, sample_api_article):
        http_client = MagicMock()
        http_client.fetch.return_value = self._make_fetch_result(
            [sample_api_article], total=1, total_pages=1
        )
        image_downloader = MagicMock()
        markdown_generator = MagicMock()
        markdown_generator.find_by_source_id.return_value = None
        p = JournalZebulineParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=image_downloader,
            markdown_generator=markdown_generator,
        )
        return p

    def test_crawl_returns_events(self, parser_with_mock_http):
        events = parser_with_mock_http.crawl()
        assert len(events) > 0

    def test_crawl_calls_api(self, parser_with_mock_http):
        parser_with_mock_http.crawl()
        parser_with_mock_http.http_client.fetch.assert_called_once()
        call_url = parser_with_mock_http.http_client.fetch.call_args[0][0]
        assert WP_API_BASE in call_url
        assert "_embed" in call_url
        assert "page=1" in call_url

    def test_crawl_empty_api_response(self, mock_config):
        http_client = MagicMock()
        http_client.fetch.return_value = self._make_fetch_result([])
        parser = JournalZebulineParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=MagicMock(),
            markdown_generator=MagicMock(),
        )
        events = parser.crawl()
        assert events == []

    def test_crawl_api_error(self, mock_config):
        http_client = MagicMock()
        http_client.fetch.side_effect = Exception("API error")
        parser = JournalZebulineParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=MagicMock(),
            markdown_generator=MagicMock(),
        )
        events = parser.crawl()
        assert events == []

    def test_crawl_api_http_error(self, mock_config):
        """Non-success HTTP status stops pagination."""
        http_client = MagicMock()
        http_client.fetch.return_value = FetchResult(
            url="https://journalzebuline.fr/wp-json/wp/v2/posts",
            status_code=500,
            html=None,
            headers={},
            error="Internal Server Error",
        )
        parser = JournalZebulineParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=MagicMock(),
            markdown_generator=MagicMock(),
        )
        events = parser.crawl()
        assert events == []

    def test_crawl_invalid_json(self, mock_config):
        http_client = MagicMock()
        http_client.fetch.return_value = FetchResult(
            url="https://journalzebuline.fr/wp-json/wp/v2/posts",
            status_code=200,
            html="not json",
            headers={"X-WP-Total": "1", "X-WP-TotalPages": "1"},
        )
        parser = JournalZebulineParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=MagicMock(),
            markdown_generator=MagicMock(),
        )
        events = parser.crawl()
        assert events == []

    def test_crawl_processes_events(self, parser_with_mock_http):
        parser_with_mock_http.crawl()
        # process_event should have been called, which calls markdown_generator
        assert parser_with_mock_http.markdown_generator.generate.called

    def test_crawl_paginates_multiple_pages(
        self, mock_config, sample_api_article
    ):
        """Crawler fetches all pages when total_pages > 1."""
        # Create a second article with different ID
        article_2 = dict(sample_api_article)
        article_2 = json.loads(json.dumps(sample_api_article))
        article_2["id"] = 999999
        article_2["slug"] = "second-article"

        http_client = MagicMock()
        # Page 1 returns first article, page 2 returns second
        http_client.fetch.side_effect = [
            self._make_fetch_result(
                [sample_api_article], total=2, total_pages=2
            ),
            self._make_fetch_result([article_2], total=2, total_pages=2),
        ]
        markdown_generator = MagicMock()
        markdown_generator.find_by_source_id.return_value = None

        parser = JournalZebulineParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=MagicMock(),
            markdown_generator=markdown_generator,
        )
        events = parser.crawl()

        # Should have called fetch twice (page 1 and page 2)
        assert http_client.fetch.call_count == 2

        # Verify page parameters in URLs
        call_urls = [call[0][0] for call in http_client.fetch.call_args_list]
        assert "page=1" in call_urls[0]
        assert "page=2" in call_urls[1]

    def test_crawl_stops_at_last_page(self, mock_config, sample_api_article):
        """Crawler stops when it reaches total_pages."""
        http_client = MagicMock()
        http_client.fetch.return_value = self._make_fetch_result(
            [sample_api_article], total=1, total_pages=1
        )
        markdown_generator = MagicMock()
        markdown_generator.find_by_source_id.return_value = None

        parser = JournalZebulineParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=MagicMock(),
            markdown_generator=markdown_generator,
        )
        parser.crawl()

        # Only one fetch call since total_pages=1
        assert http_client.fetch.call_count == 1

    def test_crawl_stops_on_400(self, mock_config, sample_api_article):
        """WordPress returns 400 when page exceeds total; crawler stops."""
        http_client = MagicMock()
        http_client.fetch.side_effect = [
            self._make_fetch_result(
                [sample_api_article], total=1, total_pages=2
            ),
            FetchResult(
                url="https://journalzebuline.fr/wp-json/wp/v2/posts",
                status_code=400,
                html=None,
                headers={},
            ),
        ]
        markdown_generator = MagicMock()
        markdown_generator.find_by_source_id.return_value = None

        parser = JournalZebulineParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=MagicMock(),
            markdown_generator=markdown_generator,
        )
        events = parser.crawl()

        assert http_client.fetch.call_count == 2
        # Should still have events from the first page
        assert len(events) > 0

    def test_crawl_deduplicates_articles(self, mock_config, sample_api_article):
        """Duplicate article IDs across pages are deduplicated."""
        http_client = MagicMock()
        # Both pages return the same article
        http_client.fetch.side_effect = [
            self._make_fetch_result(
                [sample_api_article], total=2, total_pages=2
            ),
            self._make_fetch_result(
                [sample_api_article], total=2, total_pages=2
            ),
        ]
        markdown_generator = MagicMock()
        markdown_generator.find_by_source_id.return_value = None

        parser = JournalZebulineParser(
            config=mock_config,
            http_client=http_client,
            image_downloader=MagicMock(),
            markdown_generator=markdown_generator,
        )
        events = parser.crawl()

        # Only one event despite same article on both pages
        assert len(events) == 1

    def test_crawl_passes_source_id_to_fetch(self, parser_with_mock_http):
        """Fetch calls include source_id for rate limiting."""
        parser_with_mock_http.crawl()
        call_kwargs = parser_with_mock_http.http_client.fetch.call_args
        assert call_kwargs[1]["source_id"] == "journalzebuline"


# ── Test WP constants ────────────────────────────────────────────


class TestGetHeaderInt:
    """Tests for _get_header_int static method."""

    def test_exact_case(self):
        headers = {"X-WP-TotalPages": "42"}
        assert JournalZebulineParser._get_header_int(headers, "X-WP-TotalPages", 1) == 42

    def test_lowercase_fallback(self):
        headers = {"x-wp-totalpages": "15"}
        assert JournalZebulineParser._get_header_int(headers, "X-WP-TotalPages", 1) == 15

    def test_missing_header(self):
        headers = {}
        assert JournalZebulineParser._get_header_int(headers, "X-WP-TotalPages", 1) == 1

    def test_non_integer_value(self):
        headers = {"X-WP-TotalPages": "abc"}
        assert JournalZebulineParser._get_header_int(headers, "X-WP-TotalPages", 1) == 1

    def test_default_value(self):
        headers = {}
        assert JournalZebulineParser._get_header_int(headers, "X-WP-Total", 0) == 0


class TestConstants:
    """Tests for parser constants."""

    def test_wp_per_page(self):
        assert WP_PER_PAGE == 100

    def test_wp_category_ids_defined(self):
        assert len(WP_CATEGORY_IDS) > 0
        assert all(isinstance(c, int) for c in WP_CATEGORY_IDS)

    def test_wp_category_map_covers_ids(self):
        for cat_id in WP_CATEGORY_IDS:
            assert cat_id in WP_CATEGORY_MAP

    def test_french_months_complete(self):
        assert len(FRENCH_MONTHS) >= 12
        # Check all months are covered (some have accent variants)
        months_covered = set(FRENCH_MONTHS.values())
        assert months_covered == set(range(1, 13))

    def test_marseille_cities_include_marseille(self):
        assert "marseille" in MARSEILLE_AREA_CITIES

    def test_venue_keywords_non_empty(self):
        assert len(MARSEILLE_VENUE_KEYWORDS) > 0
