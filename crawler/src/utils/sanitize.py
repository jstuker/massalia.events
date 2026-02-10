"""Sanitize text content from scraped HTML for safe use in YAML front matter."""

import html
import re

# Pattern to match HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Pattern to match dangerous URL schemes in href/src attributes
_DANGEROUS_ATTR_RE = re.compile(
    r"""(?:href|src|action)\s*=\s*["']?\s*javascript:""",
    re.IGNORECASE,
)

# Pattern to match inline event handlers (onclick, onerror, onload, etc.)
_EVENT_HANDLER_RE = re.compile(r"\bon\w+\s*=", re.IGNORECASE)

# Pattern to collapse whitespace
_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_description(text: str) -> str:
    """Sanitize a scraped description for safe inclusion in YAML front matter.

    Processing steps:
    1. Strip all HTML tags
    2. Decode HTML entities to Unicode equivalents
    3. Remove residual dangerous patterns (event handlers, javascript: URIs)
    4. Normalize whitespace
    5. Strip leading/trailing whitespace

    Args:
        text: Raw description text, potentially containing HTML tags and entities.

    Returns:
        Clean, YAML-safe plain text string.
    """
    if not text:
        return ""

    # 1. Strip HTML tags (replace with space to preserve word boundaries)
    clean = _HTML_TAG_RE.sub(" ", text)

    # 2. Decode HTML entities (handles all named & numeric entities)
    clean = html.unescape(clean)

    # 3. Remove residual dangerous patterns that survived tag stripping
    clean = _DANGEROUS_ATTR_RE.sub("", clean)
    clean = _EVENT_HANDLER_RE.sub("", clean)

    # 4. Normalize whitespace (collapse runs of spaces/newlines/tabs)
    clean = _WHITESPACE_RE.sub(" ", clean)

    # 5. Strip leading/trailing whitespace
    clean = clean.strip()

    return clean
