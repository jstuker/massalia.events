"""Tests for the sanitize_description utility."""

import pytest

from src.utils.sanitize import sanitize_description


class TestHTMLTagStripping:
    """Verify all HTML tags are removed."""

    def test_strips_script_tags(self):
        text = 'Hello<script>alert("xss")</script> world'
        result = sanitize_description(text)
        assert "<script>" not in result
        assert "Hello" in result
        assert "world" in result

    def test_strips_script_tag_with_content_removed(self):
        text = "Normal text<script>evil()</script> continues"
        result = sanitize_description(text)
        assert "<script>" not in result
        assert "</script>" not in result

    def test_strips_img_with_onerror(self):
        text = 'Before<img src="x" onerror="alert(1)">After'
        result = sanitize_description(text)
        assert "<img" not in result
        assert "Before" in result
        assert "After" in result

    def test_strips_anchor_tags(self):
        text = 'Click <a href="https://example.com">here</a> now'
        assert sanitize_description(text) == "Click here now"

    def test_strips_div_span_p_tags(self):
        text = "<div><p>Hello <span>world</span></p></div>"
        assert sanitize_description(text) == "Hello world"

    def test_strips_self_closing_tags(self):
        text = "Line one<br/>Line two<hr/>End"
        assert sanitize_description(text) == "Line one Line two End"


class TestHTMLEntityDecoding:
    """Verify all HTML entities are decoded to Unicode."""

    def test_decodes_named_entities(self):
        assert sanitize_description("&amp;") == "&"
        assert sanitize_description("&lt;") == "<"
        assert sanitize_description("&gt;") == ">"
        assert sanitize_description("&quot;") == '"'

    def test_decodes_nbsp(self):
        result = sanitize_description("hello&nbsp;world")
        # &nbsp; decodes to \xa0, then whitespace normalization collapses it
        assert result == "hello world"

    def test_decodes_numeric_entities(self):
        # &#8211; = en-dash, &#8217; = right single quote
        assert sanitize_description("&#8211;") == "\u2013"
        assert sanitize_description("&#8217;") == "\u2019"

    def test_decodes_rsquo(self):
        assert sanitize_description("l&rsquo;art") == "l\u2019art"

    def test_decodes_hex_entities(self):
        # &#x2014; = em-dash
        assert sanitize_description("&#x2014;") == "\u2014"

    def test_decodes_mixed_entities(self):
        text = "Caf&eacute; &#8211; Bar &amp; Grill"
        assert sanitize_description(text) == "Caf\u00e9 \u2013 Bar & Grill"


class TestXSSVectorRemoval:
    """Verify dangerous patterns are neutralized."""

    def test_strips_javascript_href(self):
        text = 'href="javascript:alert(1)" click'
        result = sanitize_description(text)
        assert "javascript:" not in result

    def test_strips_event_handlers(self):
        text = 'onerror=alert(1) onload=evil()'
        result = sanitize_description(text)
        assert "onerror=" not in result
        assert "onload=" not in result

    def test_full_xss_img_tag(self):
        text = 'See <img src=x onerror=alert(1)> this'
        result = sanitize_description(text)
        assert "<img" not in result
        assert "onerror=" not in result


class TestWhitespaceNormalization:
    """Verify whitespace is collapsed and trimmed."""

    def test_collapses_multiple_spaces(self):
        assert sanitize_description("hello    world") == "hello world"

    def test_collapses_newlines(self):
        assert sanitize_description("hello\n\nworld") == "hello world"

    def test_collapses_tabs(self):
        assert sanitize_description("hello\t\tworld") == "hello world"

    def test_strips_leading_trailing(self):
        assert sanitize_description("  hello  ") == "hello"

    def test_mixed_whitespace(self):
        assert sanitize_description(" \n hello \t world \n ") == "hello world"


class TestCleanTextPassthrough:
    """Verify clean text is not altered."""

    def test_plain_text_unchanged(self):
        text = "Un super concert de jazz à Marseille"
        assert sanitize_description(text) == text

    def test_unicode_preserved(self):
        text = "Théâtre de l'Œuvre — Danse contemporaine"
        assert sanitize_description(text) == text

    def test_emoji_preserved(self):
        text = "🎵 Concert gratuit 🎶"
        assert sanitize_description(text) == text

    def test_no_double_encoding(self):
        # Already-decoded text should not be re-encoded
        text = "Café & Bar"
        assert sanitize_description(text) == "Café & Bar"

    def test_ampersand_in_plain_text(self):
        # A literal & should stay as &
        text = "Rock & Roll"
        assert sanitize_description(text) == "Rock & Roll"


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_string(self):
        assert sanitize_description("") == ""

    def test_none_like_empty(self):
        assert sanitize_description("") == ""

    def test_only_html_tags(self):
        assert sanitize_description("<div><br/></div>") == ""

    def test_only_whitespace(self):
        assert sanitize_description("   \n\t  ") == ""

    def test_real_world_makeda_description(self):
        """Real example from Le Makeda with leaked entities."""
        text = "🤍Marcia 🤍 📅Jeudi 5 Mars &#8211; 20h 📍 Le Makeda"
        result = sanitize_description(text)
        assert "&#8211;" not in result
        assert "\u2013" in result  # en-dash

    def test_real_world_rsquo_description(self):
        """Real example with &rsquo; entity."""
        text = "Faire de la musique c&rsquo;est bien"
        result = sanitize_description(text)
        assert "&rsquo;" not in result
        assert "c\u2019est" in result
