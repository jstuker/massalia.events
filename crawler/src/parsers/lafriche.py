"""Parser for La Friche Belle de Mai events."""

import re
from datetime import datetime

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import FRENCH_MONTHS, PARIS_TZ
from ..utils.parser import HTMLParser
from .base import ConfigurableEventParser

logger = get_logger(__name__)


class LaFricheParser(BaseCrawler):
    """
    Event parser for La Friche Belle de Mai (https://lafriche.org).

    La Friche is a major cultural center in Marseille hosting concerts,
    exhibitions, performances, and community events.

    This parser extracts event links from the agenda page and visits
    each event's detail page to extract complete information including
    accurate dates and times.
    """

    source_name = "La Friche"

    def __init__(self, *args, **kwargs):
        """Initialize La Friche parser with configurable selectors."""
        super().__init__(*args, **kwargs)

        # Create configurable parser with our config
        self._configurable_parser = ConfigurableEventParser(
            config=self.config,
            base_url=self.base_url,
            source_id=self.source_id,
            category_map=self.category_map,
        )

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from La Friche by visiting detail pages.

        This method:
        1. Extracts all event URLs from the agenda page
        2. Visits each event's detail page
        3. Extracts complete event information from the detail page

        Args:
            parser: HTMLParser with agenda page content

        Returns:
            List of Event objects
        """
        events = []

        # Find all event links on the agenda page
        event_urls = self._find_event_urls(parser)

        if not event_urls:
            logger.warning("No event URLs found on La Friche agenda page")
            return events

        logger.info(f"Found {len(event_urls)} event URLs on La Friche agenda")

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

        return events

    def _find_event_urls(self, parser: HTMLParser) -> list[str]:
        """
        Find all event detail page URLs from the agenda page.

        Args:
            parser: HTMLParser with agenda page content

        Returns:
            List of unique event URLs (under /evenements/*)
        """
        urls = set()

        # Find all links that point to event detail pages
        for link in parser.select("a[href*='/evenements/']"):
            href = link.get("href", "")
            if href:
                # Make sure it's an absolute URL
                if href.startswith("/"):
                    href = f"https://www.lafriche.org{href}"
                # Only include URLs that match the event detail pattern
                if "/evenements/" in href and href not in urls:
                    urls.add(href)

        return list(urls)

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

        # Extract event name from h1
        name = self._extract_name(detail_parser)
        if not name:
            logger.debug(f"Could not find event name on: {event_url}")
            return None

        # Extract date and time from the detail page
        event_datetime = self._extract_datetime(detail_parser)
        if not event_datetime:
            logger.debug(f"Could not parse date for: {name} on {event_url}")
            return None

        # Extract description
        description = self._extract_description(detail_parser)

        # Extract image
        image_url = self._extract_image(detail_parser)

        # Extract category from breadcrumbs or tags
        category = self._extract_category(detail_parser)

        # Generate source ID
        source_id = self._generate_source_id(event_url)

        # Extract tags
        tags = self._extract_tags_from_detail(detail_parser)

        # Create event
        return Event(
            name=name,
            event_url=event_url,
            start_datetime=event_datetime,
            description=description,
            image=image_url,
            categories=[category],
            locations=["la-friche"],
            tags=tags,
            source_id=source_id,
        )

    def _extract_name(self, parser: HTMLParser) -> str:
        """Extract event name from detail page."""
        # Try h1 first (main title)
        h1 = parser.select_one("h1")
        if h1:
            return h1.get_text().strip()

        # Fallback to other title selectors
        for selector in ["h2.event-title", ".event-title", "h2"]:
            elem = parser.select_one(selector)
            if elem:
                return elem.get_text().strip()

        return ""

    def _extract_datetime(self, parser: HTMLParser) -> datetime | None:
        """
        Extract event date and time from detail page.

        La Friche displays dates in h2 elements like:
        "Mardi 27 janvier 2026 à 19h"
        "Du 29 janvier au 7 février 2026"
        """
        # Look for date in h2 elements (common pattern on La Friche)
        for h2 in parser.select("h2"):
            text = h2.get_text().strip()
            result = self._parse_french_date_time(text)
            if result:
                return result

        # Also check for date patterns in other elements
        for selector in [".date", ".event-date", "time", "p"]:
            for elem in parser.select(selector):
                text = elem.get_text().strip()
                result = self._parse_french_date_time(text)
                if result:
                    return result

        return None

    def _parse_french_date_time(self, text: str) -> datetime | None:
        """
        Parse French date/time string.

        Handles formats like:
        - "Mardi 27 janvier 2026 à 19h"
        - "Mardi 27 janvier 2026 à 19h30"
        - "Du 29 janvier au 7 février 2026" (returns start date)
        - "27 janvier 2026"
        """
        if not text:
            return None

        text_lower = text.lower()

        # Pattern for single date with optional time: "27 janvier 2026 à 19h30"
        single_date_pattern = (
            r"(\d{1,2})\s+(\w+)\s+(\d{4})(?:\s+[àa]\s*(\d{1,2})h(\d{2})?)?"
        )
        match = re.search(single_date_pattern, text_lower)

        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            year = int(match.group(3))
            hour = int(match.group(4)) if match.group(4) else 20
            minute = int(match.group(5)) if match.group(5) else 0

            month = FRENCH_MONTHS.get(month_name)
            if month:
                try:
                    return datetime(year, month, day, hour, minute, tzinfo=PARIS_TZ)
                except ValueError:
                    pass

        # Pattern for date range: "Du 29 janvier au 7 février 2026"
        range_pattern = r"du\s+(\d{1,2})\s+(\w+)(?:\s+au\s+\d{1,2}\s+\w+)?\s+(\d{4})"
        match = re.search(range_pattern, text_lower)

        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            year = int(match.group(3))

            month = FRENCH_MONTHS.get(month_name)
            if month:
                try:
                    return datetime(year, month, day, 20, 0, tzinfo=PARIS_TZ)
                except ValueError:
                    pass

        return None

    def _extract_description(self, parser: HTMLParser) -> str:
        """Extract event description from detail page."""
        # Try common description selectors
        for selector in [
            ".event-description",
            ".description",
            "article p",
            ".content p",
        ]:
            elem = parser.select_one(selector)
            if elem:
                text = elem.get_text().strip()
                if len(text) > 20:  # Ignore very short text
                    return HTMLParser.truncate(text, 160)

        # Try to get first substantial paragraph
        for p in parser.select("p"):
            text = p.get_text().strip()
            if len(text) > 50:  # Ignore very short paragraphs
                return HTMLParser.truncate(text, 160)

        return ""

    def _extract_image(self, parser: HTMLParser) -> str | None:
        """Extract main image from detail page."""
        # Try og:image meta tag first (usually the best quality)
        og_image = parser.select_one('meta[property="og:image"]')
        if og_image:
            content = og_image.get("content", "")
            if content:
                return str(content)

        # Try main content images
        for selector in [".event-image img", "article img", ".main-image img", "img"]:
            img = parser.select_one(selector)
            if img:
                src = img.get("src", "") or img.get("data-src", "")
                if src and not src.startswith("data:"):
                    if src.startswith("/"):
                        src = f"https://www.lafriche.org{src}"
                    return str(src)

        return None

    def _extract_category(self, parser: HTMLParser) -> str:
        """Extract and map category from detail page."""
        # Try to find category links (breadcrumbs or tags)
        for link in parser.select("a[href*='categorie=']"):
            category_text = link.get_text().strip()
            if category_text:
                return self.map_category(category_text)

        # Try generic category selectors
        for selector in [".category", ".tag", ".type"]:
            elem = parser.select_one(selector)
            if elem:
                category_text = elem.get_text().strip()
                if category_text:
                    return self.map_category(category_text)

        return "communaute"

    def _extract_tags_from_detail(self, parser: HTMLParser) -> list[str]:
        """Extract tags from detail page."""
        tags = []

        # Look for tag elements
        for selector in [".tag", ".label", "a[href*='categorie=']"]:
            for elem in parser.select(selector):
                tag_text = elem.get_text().strip().lower()
                if tag_text and len(tag_text) < 50 and tag_text not in tags:
                    tags.append(tag_text)

        return tags[:5]  # Limit to 5 tags

    def _generate_source_id(self, url: str) -> str:
        """
        Generate unique source ID from URL.

        Args:
            url: Event URL

        Returns:
            Source ID string
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = parsed.path.strip("/")

        # Use last path segment as ID
        segments = path.split("/")
        event_id = segments[-1] if segments else path

        return f"lafriche:{event_id}"
