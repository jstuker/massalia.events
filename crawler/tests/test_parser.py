"""Tests for HTML parser utilities."""

import pytest

from src.utils.parser import HTMLParser


class TestHTMLParser:
    """Tests for HTMLParser class."""

    @pytest.fixture
    def sample_html(self):
        """Sample HTML for testing."""
        return """
        <html>
        <body>
            <div class="event-card" id="event1">
                <h2 class="title">Concert de Jazz</h2>
                <a href="/events/jazz-concert">Détails</a>
                <img src="/images/jazz.jpg" alt="Jazz">
                <span class="date">26 janvier 2026</span>
                <span class="time">20h30</span>
                <p class="description">Un concert exceptionnel.</p>
                <span class="category">Musique</span>
            </div>
            <div class="event-card" id="event2">
                <h2 class="title">Exposition Art</h2>
                <a href="/events/art-expo">Détails</a>
                <img data-src="/images/art.jpg" alt="Art">
                <span class="date">27/01/2026</span>
                <span class="time">14:00</span>
            </div>
        </body>
        </html>
        """

    @pytest.fixture
    def parser(self, sample_html):
        """Create parser with sample HTML."""
        return HTMLParser(sample_html, base_url="https://example.com")

    def test_select(self, parser):
        """Test CSS selector."""
        events = parser.select(".event-card")
        assert len(events) == 2

    def test_select_one(self, parser):
        """Test single element selection."""
        title = parser.select_one(".title")
        assert title is not None
        assert "Concert" in title.get_text()

    def test_get_text(self, parser):
        """Test text extraction."""
        card = parser.select_one("#event1")
        title = parser.get_text(card, ".title")
        assert title == "Concert de Jazz"

    def test_get_text_strip(self, parser):
        """Test whitespace stripping."""
        card = parser.select_one("#event1")
        text = parser.get_text(card, ".description")
        assert text == "Un concert exceptionnel."

    def test_get_attr(self, parser):
        """Test attribute extraction."""
        card = parser.select_one("#event1")
        href = parser.get_attr(card, "href", "a")
        assert href == "/events/jazz-concert"

    def test_get_link_with_base_url(self, parser):
        """Test link resolution with base URL."""
        card = parser.select_one("#event1")
        link = parser.get_link(card, "a")
        assert link == "https://example.com/events/jazz-concert"

    def test_get_image_src(self, parser):
        """Test image src extraction."""
        card = parser.select_one("#event1")
        img = parser.get_image(card, "img")
        assert img == "https://example.com/images/jazz.jpg"

    def test_get_image_data_src(self, parser):
        """Test lazy-loaded image extraction."""
        card = parser.select_one("#event2")
        img = parser.get_image(card, "img")
        assert img == "https://example.com/images/art.jpg"


class TestDateParsing:
    """Tests for date parsing."""

    def test_parse_french_date(self):
        """Test parsing French date format."""
        result = HTMLParser.parse_date("26 janvier 2026")
        assert result is not None
        assert result.day == 26
        assert result.month == 1
        assert result.year == 2026

    def test_parse_slash_date(self):
        """Test parsing slash date format."""
        result = HTMLParser.parse_date("26/01/2026")
        assert result is not None
        assert result.day == 26
        assert result.month == 1
        assert result.year == 2026

    def test_parse_short_year(self):
        """Test parsing short year format."""
        result = HTMLParser.parse_date("26/01/26")
        assert result is not None
        assert result.year == 2026

    def test_parse_invalid_date(self):
        """Test invalid date returns None."""
        result = HTMLParser.parse_date("invalid date")
        assert result is None


class TestTimeParsing:
    """Tests for time parsing."""

    def test_parse_time_h_format(self):
        """Test 19h30 format."""
        result = HTMLParser.parse_time("19h30")
        assert result == "19:30"

    def test_parse_time_colon_format(self):
        """Test 19:30 format."""
        result = HTMLParser.parse_time("20:00")
        assert result == "20:00"

    def test_parse_time_hour_only(self):
        """Test hour only format."""
        result = HTMLParser.parse_time("19h")
        assert result == "19:00"

    def test_parse_time_with_space(self):
        """Test with space."""
        result = HTMLParser.parse_time("19 h")
        assert result == "19:00"

    def test_parse_time_in_text(self):
        """Test extracting time from text."""
        result = HTMLParser.parse_time("Début à 20h30")
        assert result == "20:30"


class TestTextUtilities:
    """Tests for text utility functions."""

    def test_clean_text(self):
        """Test whitespace cleaning."""
        result = HTMLParser.clean_text("  Hello   World  \n\t ")
        assert result == "Hello World"

    def test_truncate_short(self):
        """Test truncation of short text."""
        result = HTMLParser.truncate("Hello", 100)
        assert result == "Hello"

    def test_truncate_long(self):
        """Test truncation of long text."""
        text = "This is a very long description that should be truncated."
        result = HTMLParser.truncate(text, 30)
        assert len(result) <= 30
        assert result.endswith("...")

    def test_truncate_at_word_boundary(self):
        """Test truncation at word boundary."""
        text = "Hello wonderful world of events"
        result = HTMLParser.truncate(text, 20)
        # Should not cut in middle of word
        assert not result.endswith("worl...")
