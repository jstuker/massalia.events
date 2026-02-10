"""Parser for Le Zef - Scene nationale de Marseille events (lezef.org)."""

import json
from datetime import datetime
from urllib.parse import urljoin

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import PARIS_TZ, parse_french_time
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

# AJAX endpoint for fetching event listings
AJAX_URL = "https://www.lezef.org/fr/saison_ajax"


def _extract_event_urls_from_ajax_html(html: str, base_url: str = "") -> list[str]:
    """
    Extract event detail page URLs from the AJAX listing response.

    Le Zef returns HTML with article.item-event elements containing links
    to event detail pages.

    Args:
        html: HTML content from the AJAX response
        base_url: Base URL for resolving relative links

    Returns:
        List of unique event detail URLs
    """
    parser = HTMLParser(html, base_url)
    urls = set()

    # Event detail links are in article.item-event > figure > a
    for article in parser.select("article.item-event"):
        link = article.select_one("figure a[href]")
        if link:
            href = link.get("href", "")
            if not href:
                continue

            # Resolve relative URLs
            if href.startswith("/"):
                href = urljoin(base_url, href)

            # Only include saison event pages
            if "/saison/" in href:
                urls.add(href)

    return sorted(urls)


def _extract_json_ld(html: str) -> dict | None:
    """
    Extract the mainEntity Event from JSON-LD structured data.

    Le Zef embeds Event data in the mainEntity property of WebPage JSON-LD.
    The JSON often contains CRLF line breaks inside string values that need
    to be escaped properly for JSON parsing.

    Args:
        html: HTML content

    Returns:
        Event JSON-LD dict or None if not found
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            json_str = script.string
            if not json_str:
                continue

            # Le Zef's JSON-LD has unescaped line breaks inside string values.
            # We need to escape them for valid JSON parsing.
            # Replace \r\n and \r with escaped newlines in string contexts.
            # This is a common issue with server-generated JSON.
            json_str = json_str.replace("\r\n", "\\n").replace("\r", "\\n")

            data = json.loads(json_str)
            if isinstance(data, dict):
                # Check for Event type directly
                if data.get("@type") == "Event":
                    return data
                # Check for mainEntity containing Event
                main_entity = data.get("mainEntity")
                if main_entity and main_entity.get("@type") == "Event":
                    return main_entity
        except (json.JSONDecodeError, TypeError):
            continue

    return None


def _parse_iso_date(date_str: str) -> datetime | None:
    """
    Parse an ISO date string (YYYY-MM-DD) to a datetime at midnight Paris TZ.

    Args:
        date_str: ISO format date string

    Returns:
        datetime in Paris timezone, or None on failure
    """
    try:
        # Handle full ISO datetime
        if "T" in date_str:
            date_str = date_str.split("T")[0]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=PARIS_TZ)
    except (ValueError, TypeError):
        return None


def _extract_time_from_html(html: str) -> tuple[int, int] | None:
    """
    Extract event time from HTML date display.

    Le Zef shows times like "à 19h", "à 20h30", etc.
    Delegates to shared parse_french_time utility.

    Args:
        html: HTML content of detail page

    Returns:
        Tuple of (hour, minute) or None if not found
    """
    return parse_french_time(html)


def _generate_source_id(url: str) -> str:
    """Generate a unique source ID from an event URL."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path.strip("/")
    segments = path.split("/")
    event_slug = segments[-1] if segments else path
    return f"lezef:{event_slug}"


def _extract_category_from_html(html: str) -> str | None:
    """
    Extract event category from HTML.

    Le Zef uses <a class="danse">DANSE</a> style category links.

    Args:
        html: HTML content

    Returns:
        Category text (lowercase) or None
    """
    parser = HTMLParser(html, "")

    # Try category links in .category element
    for selector in ["p.category a", ".category a"]:
        cat_elem = parser.select_one(selector)
        if cat_elem:
            return cat_elem.get_text().strip().lower()

    return None


def _extract_description_from_html(html: str) -> str:
    """
    Extract event description from HTML.

    Le Zef has description in the #presentation section.

    Args:
        html: HTML content

    Returns:
        Truncated description text
    """
    parser = HTMLParser(html, "")

    # Try meta description first
    meta = parser.select_one('meta[name="description"]')
    if meta:
        content = meta.get("content", "").strip()
        if content and len(content) > 20:
            return HTMLParser.truncate(content, 160)

    # Try presentation section
    for selector in ["#presentation p", ".presentation p", "article p"]:
        elem = parser.select_one(selector)
        if elem:
            text = elem.get_text().strip()
            if len(text) > 20:
                return HTMLParser.truncate(text, 160)

    return ""


def _extract_performer_from_html(html: str) -> list[str]:
    """
    Extract performer/artist names from HTML.

    Le Zef shows performers in p.artiste and p.compagnie elements.

    Args:
        html: HTML content

    Returns:
        List of performer names (lowercase, for tags)
    """
    parser = HTMLParser(html, "")
    performers = []

    for selector in ["p.artiste", "p.compagnie", ".artiste", ".compagnie"]:
        elems = parser.select(selector)
        for elem in elems:
            text = elem.get_text().strip()
            if text and text.lower() not in performers:
                performers.append(text.lower())

    return performers[:5]


class LeZefParser(BaseCrawler):
    """
    Event parser for Le Zef - Scene nationale de Marseille.

    Le Zef (formerly Theatre du Merlan) is a major cultural venue in
    Marseille's 14th arrondissement, hosting theatre, dance, music,
    circus, exhibitions, and culinary events.

    This parser:
    1. Posts to AJAX endpoint to get season event listings
    2. Extracts event detail URLs from article.item-event elements
    3. Visits each detail page to extract JSON-LD + HTML data
    4. Handles date ranges (exhibitions) by creating a single event
       with the start date
    """

    source_name = "Le Zef"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from Le Zef.

        Note: The main URL is just for reference; actual events are
        fetched via AJAX POST.

        Args:
            parser: HTMLParser with the main page content (not used directly)

        Returns:
            List of Event objects
        """
        events = []

        # Fetch events via AJAX endpoint
        ajax_html = self._fetch_ajax_events()
        if not ajax_html:
            logger.warning("Failed to fetch Le Zef AJAX events")
            return events

        # Extract event URLs
        event_urls = _extract_event_urls_from_ajax_html(
            ajax_html, "https://www.lezef.org"
        )

        if not event_urls:
            logger.warning("No event URLs found on Le Zef")
            return events

        logger.info(f"Found {len(event_urls)} event URLs on Le Zef")

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

        logger.info(f"Extracted {len(events)} events from Le Zef")
        return events

    def _fetch_ajax_events(self) -> str | None:
        """
        Fetch events from the AJAX endpoint.

        Returns:
            HTML content or None on failure
        """
        import requests

        try:
            # Extract season from base_url (e.g., "25-26" from ".../saison/25-26")
            season = "25-26"
            if "/saison/" in self.base_url:
                season = self.base_url.split("/saison/")[-1].strip("/")

            response = requests.post(
                AJAX_URL,
                data={"saisonAddr": season},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.warning(f"AJAX request failed: {e}")
            return None

    def _parse_detail_page(
        self, event_url: str, html: str | None = None
    ) -> Event | None:
        """
        Parse an event detail page.

        Args:
            event_url: URL of the event detail page
            html: Pre-fetched HTML content (fetched if not provided)

        Returns:
            Event object or None if parsing fails
        """
        if html is None:
            html = self.fetch_page(event_url)
        if not html:
            logger.warning(f"Failed to fetch detail page: {event_url}")
            return None

        # Extract JSON-LD for base event info
        json_ld = _extract_json_ld(html)
        if not json_ld:
            logger.debug(f"No Event JSON-LD found on: {event_url}")
            return None

        # Extract event name
        name = json_ld.get("name", "").strip()
        if not name:
            logger.debug(f"No name in JSON-LD: {event_url}")
            return None

        # Parse start date
        start_date_str = json_ld.get("startDate", "")
        if not start_date_str:
            logger.debug(f"No startDate in JSON-LD: {event_url}")
            return None

        start_datetime = _parse_iso_date(start_date_str)
        if not start_datetime:
            logger.debug(f"Could not parse startDate: {start_date_str}")
            return None

        # Try to extract time from HTML and update datetime
        time_tuple = _extract_time_from_html(html)
        if time_tuple:
            start_datetime = start_datetime.replace(
                hour=time_tuple[0], minute=time_tuple[1]
            )
        else:
            # Default to 20:00 if no time found (common showtime)
            start_datetime = start_datetime.replace(hour=20, minute=0)

        # Handle past events - check if it's an ongoing exhibition
        now = datetime.now(PARIS_TZ)
        is_ongoing_exhibition = False
        if start_datetime < now:
            # Check if there's an endDate in the future (ongoing exhibition)
            end_date_str = json_ld.get("endDate", "")
            if end_date_str:
                end_datetime = _parse_iso_date(end_date_str)
                if end_datetime and end_datetime > now:
                    # Ongoing exhibition - use today as the event date
                    logger.debug(
                        f"Ongoing exhibition: {name} "
                        f"({start_date_str} to {end_date_str})"
                    )
                    start_datetime = now.replace(
                        hour=10, minute=0, second=0, microsecond=0
                    )
                    is_ongoing_exhibition = True

            if not is_ongoing_exhibition:
                logger.debug(f"Skipping past event: {name} ({start_datetime})")
                return None

        # Extract description (prefer JSON-LD, fallback to HTML)
        description = json_ld.get("description", "").strip()
        if description:
            description = HTMLParser.truncate(description, 160)
        else:
            description = _extract_description_from_html(html)

        # Extract image
        image = json_ld.get("image", "")
        if isinstance(image, list):
            image = image[0] if image else ""
        elif isinstance(image, dict):
            image = image.get("url", "")

        # Extract category from HTML (more reliable)
        category = _extract_category_from_html(html)
        if category:
            category = self.map_category(category)
        else:
            category = "theatre"  # Default for Le Zef

        # Generate source ID
        source_id = _generate_source_id(event_url)

        # Extract performers as tags
        tags = _extract_performer_from_html(html)

        # Also add performers from JSON-LD
        performer = json_ld.get("performer", [])
        if isinstance(performer, dict):
            performer = [performer]
        for p in performer:
            if isinstance(p, dict):
                perf_name = p.get("name", "").strip().lower()
                if perf_name and perf_name not in tags and perf_name != name.lower():
                    tags.append(perf_name)

        # Location is always Le Zef
        locations = ["le-zef-theatre-du-merlan"]

        return Event(
            name=name,
            event_url=event_url,
            start_datetime=start_datetime,
            description=description,
            image=image if image else None,
            categories=[category],
            locations=locations,
            tags=tags[:5],
            source_id=source_id,
        )
