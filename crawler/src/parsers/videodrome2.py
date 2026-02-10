"""Parser for Videodrome 2 events (videodrome2.fr)."""

import json
import re
from datetime import datetime
from urllib.parse import urljoin

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import FRENCH_MONTHS, PARIS_TZ
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

BASE_URL = "https://www.videodrome2.fr"


def _extract_event_urls_from_html(html: str, base_url: str = "") -> list[str]:
    """
    Extract event detail page URLs from the listing page.

    Videodrome 2 uses .event_item containers with links
    pointing to individual event pages.

    Args:
        html: HTML content of the listing page
        base_url: Base URL for resolving relative links

    Returns:
        List of unique event detail URLs
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    urls = set()

    # Event items contain links with event detail URLs
    for event_item in soup.select(".event_item"):
        # Find links within the event item
        for link in event_item.select("a[href]"):
            href = link.get("href", "")
            if not href:
                continue

            # Resolve relative URLs
            if href.startswith("/"):
                href = urljoin(base_url or BASE_URL, href)

            # Skip non-event pages (home, category pages, etc.)
            if href.rstrip("/") == (base_url or BASE_URL).rstrip("/"):
                continue
            if "/accueil/" in href or "/cinema-13006/" in href:
                continue

            # Must be on videodrome2.fr
            if "videodrome2.fr" in href:
                urls.add(href)

    return sorted(urls)


def _extract_json_ld(html: str) -> list[dict]:
    """
    Extract JSON-LD structured data from HTML.

    Args:
        html: HTML content

    Returns:
        List of parsed JSON-LD objects
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                # Handle @graph pattern (Yoast SEO)
                if "@graph" in data:
                    results.extend(data["@graph"])
                else:
                    results.append(data)
            elif isinstance(data, list):
                results.extend(data)
        except (json.JSONDecodeError, TypeError):
            continue

    return results


def _parse_french_datetime_from_text(text: str) -> datetime | None:
    """
    Parse French date and time from body text.

    Videodrome 2 displays dates like:
    - "mardi 3 février 2026 de 20h30 à 21h15"
    - "Vendredi 6 février 2026 · 20h30"
    - "mercredi 12 février 2026 · 15h00"

    Note: The JSON-LD startDate on this site stores AM times instead of PM
    (e.g., 08:30 instead of 20:30), so we parse the French text instead.

    Args:
        text: Full page text to search for date/time patterns

    Returns:
        datetime in Paris timezone, or None on failure
    """
    # Pattern: "DD month YYYY" with optional time "de HHhMM" or "· HHhMM"
    date_pattern = re.compile(
        r"(\d{1,2})\s+(\w+)\s+(\d{4})"
        r"(?:\s*(?:de|·|à|,)\s*(\d{1,2})[hH](\d{2})?)?"
        r"(?:\s*à\s*(\d{1,2})[hH](\d{2})?)?",
        re.IGNORECASE,
    )

    match = date_pattern.search(text)
    if not match:
        return None

    day = int(match.group(1))
    month_name = match.group(2).lower()
    year = int(match.group(3))

    month = FRENCH_MONTHS.get(month_name)
    if not month:
        return None

    # Extract time (default to 20h00 for evening cinema)
    hour = int(match.group(4)) if match.group(4) else 20
    minute = int(match.group(5)) if match.group(5) else 0

    try:
        return datetime(year, month, day, hour, minute, tzinfo=PARIS_TZ)
    except ValueError:
        return None


def _generate_source_id(url: str) -> str:
    """Generate a unique source ID from an event URL."""
    from urllib.parse import unquote, urlparse

    parsed = urlparse(url)
    path = unquote(parsed.path).strip("/")
    segments = path.split("/")
    event_slug = segments[-1] if segments else path
    # Truncate very long slugs
    if len(event_slug) > 80:
        event_slug = event_slug[:80]
    return f"videodrome2:{event_slug}"


class Videodrome2Parser(BaseCrawler):
    """
    Event parser for Videodrome 2 (videodrome2.fr).

    Videodrome 2 is an independent cinema in the 6th arrondissement
    of Marseille, hosting film screenings, ciné-clubs, ciné-concerts,
    youth programming, and special events.

    This parser:
    1. Fetches the listing page with all upcoming events
    2. Extracts event detail URLs from .event_item containers
    3. Visits each detail page to extract event data
    4. Uses French body text for dates (JSON-LD times are unreliable)
    5. Uses JSON-LD for event name and keywords
    """

    source_name = "Videodrome 2"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from the Videodrome 2 listing page.

        Args:
            parser: HTMLParser with the listing page content

        Returns:
            List of Event objects
        """
        events = []

        event_urls = _extract_event_urls_from_html(
            str(parser.soup), self.base_url
        )

        if not event_urls:
            logger.warning("No event URLs found on Videodrome 2")
            return events

        logger.info(f"Found {len(event_urls)} event URLs on Videodrome 2")

        # Batch-fetch all detail pages concurrently
        pages = self.fetch_pages(event_urls)

        for event_url in event_urls:
            html = pages.get(event_url, "")
            if not html:
                continue
            try:
                event = self._parse_detail_page(event_url, html=html)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event from {event_url}: {e}")

        logger.info(f"Extracted {len(events)} events from Videodrome 2")
        return events

    def _parse_detail_page(
        self, event_url: str, html: str | None = None
    ) -> Event | None:
        """
        Parse an event detail page.

        Args:
            event_url: URL of the event detail page
            html: Pre-fetched HTML content (fetched if not provided)

        Returns:
            Event object or None if parsing failed
        """
        if html is None:
            html = self.fetch_page(event_url)
        if not html:
            logger.warning(f"Failed to fetch detail page: {event_url}")
            return None

        detail_parser = HTMLParser(html, event_url)

        # Extract event name
        name = self._extract_name(detail_parser, html)
        if not name:
            logger.debug(f"Could not find event name on: {event_url}")
            return None

        # Extract date/time from body text (JSON-LD times are unreliable)
        event_datetime = self._extract_datetime(detail_parser)
        if not event_datetime:
            logger.debug(f"Could not parse date for: {name} on {event_url}")
            return None

        # Skip past events
        now = datetime.now(PARIS_TZ)
        if event_datetime < now:
            logger.debug(f"Skipping past event: {name}")
            return None

        # Extract other fields
        description = self._extract_description(detail_parser, html)
        image_url = self._extract_image(detail_parser)
        category = self._extract_category(html)
        tags = self._extract_tags(html)
        source_id = _generate_source_id(event_url)

        return Event(
            name=name,
            event_url=event_url,
            start_datetime=event_datetime,
            description=description,
            image=image_url,
            categories=[category],
            locations=["videodrome-2"],
            tags=tags,
            source_id=source_id,
        )

    def _extract_name(self, parser: HTMLParser, html: str) -> str:
        """
        Extract event name from detail page.

        Tries JSON-LD event name first, then falls back to HTML headings.
        """
        # Try JSON-LD event name (most reliable for title)
        json_ld_list = _extract_json_ld(html)
        for item in json_ld_list:
            if item.get("@type", "").lower() == "event":
                name = item.get("name", "").strip()
                if name:
                    return name

        # Try Article headline from JSON-LD
        for item in json_ld_list:
            if item.get("@type") == "Article":
                headline = item.get("headline", "").strip()
                if headline:
                    return headline

        # Fall back to HTML h1
        h1 = parser.select_one("h1")
        if h1:
            text = h1.get_text().strip()
            if text:
                return text

        # Try entry-title
        title = parser.select_one(".entry-title")
        if title:
            text = title.get_text().strip()
            if text:
                return text

        return ""

    def _extract_datetime(self, parser: HTMLParser) -> datetime | None:
        """
        Extract event date and time from the page body text.

        The JSON-LD startDate on Videodrome 2 uses incorrect times
        (stores PM times as AM, e.g., 08:30 instead of 20:30).
        We parse the French date text from the body instead.
        """
        # Search all text content for French date patterns
        body_text = parser.soup.get_text()
        return _parse_french_datetime_from_text(body_text)

    def _extract_description(self, parser: HTMLParser, html: str) -> str:
        """Extract event description from detail page."""
        # Try og:description meta tag first
        og_desc = parser.select_one('meta[property="og:description"]')
        if og_desc:
            content = og_desc.get("content", "")
            if content and len(str(content)) > 20:
                return HTMLParser.truncate(str(content).strip(), 160)

        # Try JSON-LD Article description
        json_ld_list = _extract_json_ld(html)
        for item in json_ld_list:
            if item.get("@type") == "Article":
                desc = item.get("description", "").strip()
                if desc and len(desc) > 20:
                    # Strip HTML tags from description
                    clean = re.sub(r"<[^>]+>", "", desc)
                    return HTMLParser.truncate(clean.strip(), 160)

        # Try entry-content paragraphs
        for selector in [".entry-content p", "article p", "p"]:
            for p in parser.select(selector):
                text = p.get_text().strip()
                if len(text) > 50:
                    return HTMLParser.truncate(text, 160)

        return ""

    def _extract_image(self, parser: HTMLParser) -> str | None:
        """Extract main image from detail page."""
        # Try og:image meta tag
        og_image = parser.select_one('meta[property="og:image"]')
        if og_image:
            content = og_image.get("content", "")
            if content:
                return str(content)

        # Try wp-post-image in content
        img = parser.select_one("img.wp-post-image")
        if img:
            src = img.get("src", "") or img.get("data-src", "")
            if src and not str(src).startswith("data:"):
                # Get full-size image if thumbnail
                full_src = re.sub(r"-\d+x\d+\.", ".", str(src))
                return urljoin(BASE_URL, full_src)

        # Try any content image
        for selector in [".entry-content img", "article img"]:
            img = parser.select_one(selector)
            if img:
                src = img.get("src", "") or img.get("data-src", "")
                if src and not str(src).startswith("data:"):
                    return urljoin(BASE_URL, str(src))

        return None

    def _extract_category(self, html: str) -> str:
        """
        Extract and map category from JSON-LD articleSection.

        Videodrome 2 uses articleSection in JSON-LD with values like
        "Les séances de cinéma", "LSF", etc.
        """
        json_ld_list = _extract_json_ld(html)
        for item in json_ld_list:
            if item.get("@type") == "Article":
                sections = item.get("articleSection", [])
                if isinstance(sections, str):
                    sections = [sections]
                for section in sections:
                    mapped = self.map_category(section.strip())
                    if mapped != "communaute":
                        return mapped

        # Default for cinema venue
        return "art"

    def _extract_tags(self, html: str) -> list[str]:
        """
        Extract tags from JSON-LD keywords.

        Filters out promotional tags (promo-social, promo-teaser).
        """
        tags = []
        json_ld_list = _extract_json_ld(html)
        for item in json_ld_list:
            if item.get("@type") == "Article":
                keywords = item.get("keywords", [])
                if isinstance(keywords, str):
                    keywords = [k.strip() for k in keywords.split(",")]
                for kw in keywords:
                    kw_clean = kw.strip().lower()
                    # Filter out promotional tags
                    if kw_clean and not kw_clean.startswith("promo-"):
                        tags.append(kw_clean)

        return tags[:5]
