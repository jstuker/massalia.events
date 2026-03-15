"""Parser for Théâtre Joliette events (theatrejoliette.fr)."""

import json
import re
from datetime import datetime

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import FRENCH_MONTHS, PARIS_TZ, parse_french_time
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

BASE_URL = "https://www.theatrejoliette.fr"


def _extract_event_urls(parser: HTMLParser) -> list[str]:
    """
    Extract event detail page URLs from the listing page.

    Only extracts URLs from the "Événements à venir" section,
    stopping before the "Déjà passé" section.

    Args:
        parser: HTMLParser with the listing page content

    Returns:
        List of unique event detail URLs
    """
    urls = set()

    for tile in parser.select(".tile_item.tile_simple"):
        link = tile.select_one("a[href]")
        if not link:
            continue

        href = link.get("href", "")
        if not href:
            continue

        if href.startswith("/"):
            href = f"{BASE_URL}{href}"

        if "/programmation/" in href and href != parser.base_url:
            urls.add(href)

    return sorted(urls)


def _extract_json_ld(html: str) -> dict | None:
    """
    Extract Event data from JSON-LD structured data.

    Théâtre Joliette embeds a direct Event object in JSON-LD.

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

            json_str = json_str.replace("\r\n", "\\n").replace("\r", "\\n")
            data = json.loads(json_str)

            if isinstance(data, dict):
                if data.get("@type") == "Event":
                    return data
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
        if "T" in date_str:
            date_str = date_str.split("T")[0]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=PARIS_TZ)
    except (ValueError, TypeError):
        return None


def _extract_showtimes(html: str) -> list[datetime]:
    """
    Extract individual showtimes from the detail page HTML.

    Théâtre Joliette lists showtimes as <li> elements after a "Séances"
    heading, e.g. "jeudi 19 mars 2026 à 19h".

    Args:
        html: HTML content

    Returns:
        List of datetime objects for each showtime
    """
    showtimes = []
    pattern = re.compile(
        r"(\d{1,2})\s+("
        + "|".join(FRENCH_MONTHS.keys())
        + r")\s+(\d{4})\s+[àa]\s*(\d{1,2})h(\d{2})?",
        re.IGNORECASE,
    )

    for match in pattern.finditer(html):
        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5)) if match.group(5) else 0

        month = FRENCH_MONTHS.get(month_name)
        if month:
            try:
                dt = datetime(year, month, day, hour, minute, tzinfo=PARIS_TZ)
                showtimes.append(dt)
            except ValueError:
                continue

    return showtimes


def _extract_category_from_html(html: str) -> str | None:
    """
    Extract event category from HTML.

    Théâtre Joliette uses .label_status elements for category labels.

    Args:
        html: HTML content

    Returns:
        Category text (lowercase) or None
    """
    parser = HTMLParser(html, "")

    for selector in [".label_status", ".tag"]:
        elem = parser.select_one(selector)
        if elem:
            text = elem.get_text().strip().lower()
            if text:
                return text

    return None


def _extract_description_from_html(html: str) -> str:
    """
    Extract event description from HTML.

    Args:
        html: HTML content

    Returns:
        Truncated description text
    """
    parser = HTMLParser(html, "")

    meta = parser.select_one('meta[name="description"]')
    if meta:
        content = meta.get("content", "").strip()
        if content and len(content) > 20:
            return HTMLParser.truncate(content, 160)

    for p in parser.select("p"):
        text = p.get_text().strip()
        if len(text) > 50:
            return HTMLParser.truncate(text, 160)

    return ""


def _generate_source_id(url: str) -> str:
    """Generate a unique source ID from an event URL."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path.strip("/")
    segments = path.split("/")
    event_slug = segments[-1] if segments else path
    return f"theatrejoliette:{event_slug}"


class TheatreJolietteParser(BaseCrawler):
    """
    Event parser for Théâtre Joliette (theatrejoliette.fr).

    Théâtre Joliette is a theatre in the Joliette district of Marseille,
    hosting theatre, dance, performance, and poetry events.

    This parser:
    1. Fetches the season programme listing page
    2. Extracts event detail URLs from .tile_item elements
    3. Visits each detail page to extract JSON-LD + HTML data
    4. Creates separate Event objects for each showtime of multi-day events
    """

    source_name = "Théâtre Joliette"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from Théâtre Joliette.

        Args:
            parser: HTMLParser with the listing page content

        Returns:
            List of Event objects
        """
        events = []

        event_urls = _extract_event_urls(parser)

        if not event_urls:
            logger.warning("No event URLs found on Théâtre Joliette")
            return events

        logger.info(
            f"Found {len(event_urls)} event URLs on Théâtre Joliette"
        )

        pages = self.fetch_pages(event_urls)

        for event_url in event_urls:
            html = pages.get(event_url, "")
            if not html:
                continue
            try:
                parsed_events = self._parse_detail_page(event_url, html)
                events.extend(parsed_events)
            except Exception as e:
                logger.warning(
                    f"Failed to parse event from {event_url}: {e}"
                )

        logger.info(
            f"Extracted {len(events)} events from Théâtre Joliette"
        )
        return events

    def _parse_detail_page(
        self, event_url: str, html: str | None = None
    ) -> list[Event]:
        """
        Parse an event detail page, returning one Event per showtime.

        Args:
            event_url: URL of the event detail page
            html: Pre-fetched HTML content

        Returns:
            List of Event objects (one per showtime)
        """
        if html is None:
            html = self.fetch_page(event_url)
        if not html:
            logger.warning(f"Failed to fetch detail page: {event_url}")
            return []

        json_ld = _extract_json_ld(html)
        if not json_ld:
            logger.debug(f"No Event JSON-LD found on: {event_url}")
            return []

        name = json_ld.get("name", "").strip()
        if not name:
            logger.debug(f"No name in JSON-LD: {event_url}")
            return []

        # Extract individual showtimes from HTML
        showtimes = _extract_showtimes(html)

        # Fallback to JSON-LD startDate if no showtimes found
        if not showtimes:
            start_date_str = json_ld.get("startDate", "")
            if not start_date_str:
                logger.debug(f"No dates found for: {name}")
                return []

            start_dt = _parse_iso_date(start_date_str)
            if not start_dt:
                logger.debug(f"Could not parse startDate: {start_date_str}")
                return []

            # Try to extract time from HTML
            time_tuple = parse_french_time(html)
            if time_tuple:
                start_dt = start_dt.replace(
                    hour=time_tuple[0], minute=time_tuple[1]
                )
            else:
                start_dt = start_dt.replace(hour=20, minute=0)

            showtimes = [start_dt]

        # Filter out past showtimes
        now = datetime.now(PARIS_TZ)
        future_showtimes = [dt for dt in showtimes if dt > now]

        if not future_showtimes:
            logger.debug(f"All showtimes are in the past for: {name}")
            return []

        # Extract shared fields
        description = json_ld.get("description", "").strip()
        if description:
            description = HTMLParser.truncate(description, 160)
        else:
            description = _extract_description_from_html(html)

        image = json_ld.get("image", "")
        if isinstance(image, list):
            image = image[0] if image else ""
        elif isinstance(image, dict):
            image = image.get("url", "")

        category = _extract_category_from_html(html)
        if category:
            category = self.map_category(category)
        else:
            category = "theatre"

        base_source_id = _generate_source_id(event_url)

        # Determine if multi-day event
        total_shows = len(future_showtimes)
        use_group = total_shows > 1
        group_id = base_source_id if use_group else None

        events = []
        for i, showtime in enumerate(future_showtimes, start=1):
            source_id = (
                f"{base_source_id}:{showtime.strftime('%Y%m%d')}"
                if use_group
                else base_source_id
            )
            day_of = (
                f"Jour {i} sur {total_shows}" if use_group else None
            )

            events.append(
                Event(
                    name=name,
                    event_url=event_url,
                    start_datetime=showtime,
                    description=description,
                    image=image if image else None,
                    categories=[category],
                    locations=["theatre-joliette"],
                    tags=[],
                    source_id=source_id,
                    event_group_id=group_id,
                    day_of=day_of,
                )
            )

        return events
