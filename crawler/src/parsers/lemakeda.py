"""Parser for Le Makeda (lemakeda.com) events.

Le Makeda is a concert venue and performance space located at
103 rue Ferrari, 13005 Marseille. It hosts concerts, DJ sets,
dance performances, festivals, and other cultural events.

The site runs on WordPress with The Events Calendar (Tribe)
plugin, which exposes a full REST API at:
  https://www.lemakeda.com/wp-json/tribe/events/v1/events

Strategy:
1. Fetch upcoming events from the Tribe Events REST API with pagination.
2. Parse structured JSON responses (no HTML scraping needed).
3. Extract title, dates, description, image, categories, and tags.
4. Map Tribe event categories to our standard taxonomy.
"""

import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

PARIS_TZ = ZoneInfo("Europe/Paris")

# Tribe Events REST API endpoint
TRIBE_API_BASE = "https://www.lemakeda.com/wp-json/tribe/events/v1"

# Maximum events per API request (Tribe default max is 50)
TRIBE_PER_PAGE = 50


class LeMakedaParser(BaseCrawler):
    """
    Event parser for Le Makeda (https://www.lemakeda.com).

    Le Makeda is a concert and performance venue in Marseille's 5th
    arrondissement. Programming includes concerts, DJ sets, dance
    performances, drag shows, festivals, and open-air events.

    This parser uses The Events Calendar (Tribe) REST API to fetch
    structured event data as JSON, avoiding the need for HTML parsing.
    """

    source_name = "Le Makeda"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from Le Makeda using the Tribe Events REST API.

        The HTMLParser argument from the base class crawl() method is
        ignored since we fetch structured JSON from the API directly.

        Args:
            parser: HTMLParser (unused, required by base class interface)

        Returns:
            List of Event objects
        """
        events = []
        api_events = self._fetch_api_events()

        if not api_events:
            logger.warning("No events found from Le Makeda API")
            return events

        logger.info(f"Fetched {len(api_events)} events from Le Makeda API")

        for event_data in api_events:
            try:
                event = self._parse_event(event_data)
                if event:
                    events.append(event)
            except Exception as e:
                title = event_data.get("title", "unknown")
                logger.warning(f"Failed to parse Le Makeda event '{title}': {e}")

        logger.info(f"Parsed {len(events)} valid events from Le Makeda")
        return events

    def _fetch_api_events(self) -> list[dict]:
        """
        Fetch all upcoming events from the Tribe Events REST API.

        Paginates through all pages using the API's total_pages field.

        Returns:
            List of event dicts from the API
        """
        all_events = []
        page = 1
        total_pages = None

        while True:
            url = (
                f"{TRIBE_API_BASE}/events"
                f"?per_page={TRIBE_PER_PAGE}"
                f"&page={page}"
                f"&start_date=now"
                f"&status=publish"
            )

            try:
                result = self.http_client.fetch(url, source_id=self.source_id)
            except Exception as e:
                logger.error(f"Failed to fetch Le Makeda API page {page}: {e}")
                break

            if not result.success:
                if result.status_code == 404 or result.status_code == 400:
                    logger.debug(f"Reached end of Le Makeda pagination at page {page}")
                    break
                logger.error(
                    f"Le Makeda API error on page {page}: HTTP {result.status_code}"
                )
                break

            try:
                data = json.loads(result.html)
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse Le Makeda API response: {e}")
                break

            events = data.get("events", [])
            if not events:
                break

            all_events.extend(events)

            # Read pagination info
            if total_pages is None:
                total_pages = data.get("total_pages", 1)
                total_events = data.get("total", len(events))
                logger.info(
                    f"Le Makeda API: {total_events} events across {total_pages} pages"
                )

            page += 1
            if total_pages and page > total_pages:
                break

        return all_events

    def _parse_event(self, data: dict) -> Event | None:
        """
        Parse a single event from Tribe Events API data.

        Args:
            data: Event dict from the API response

        Returns:
            Event object or None if essential fields are missing
        """
        # Extract title
        name = self._extract_name(data)
        if not name:
            logger.debug("Skipping event without title")
            return None

        # Extract datetime
        start_datetime = self._extract_datetime(data)
        if not start_datetime:
            logger.debug(f"Skipping event without valid date: {name}")
            return None

        # Extract URL
        event_url = data.get("url", "")
        if not event_url:
            logger.debug(f"Skipping event without URL: {name}")
            return None

        # Extract optional fields
        description = self._extract_description(data)
        image_url = self._extract_image(data)
        categories = self._extract_categories(data)
        tags = self._extract_tags(data)
        source_id = self._generate_source_id(data)

        return Event(
            name=name,
            event_url=event_url,
            start_datetime=start_datetime,
            description=description,
            image=image_url,
            categories=categories,
            locations=["le-makeda"],
            tags=tags,
            source_id=source_id,
        )

    def _extract_name(self, data: dict) -> str:
        """Extract event title from API data."""
        title = data.get("title", "")
        if isinstance(title, str):
            return _strip_html(title).strip()
        return ""

    def _extract_datetime(self, data: dict) -> datetime | None:
        """
        Extract start datetime from API data.

        The Tribe API returns dates in format "2026-01-08 20:00:00".
        """
        start_date_str = data.get("start_date", "")
        if not start_date_str:
            return None

        try:
            dt = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=PARIS_TZ)
        except ValueError:
            logger.debug(f"Could not parse date: {start_date_str}")
            return None

    def _extract_description(self, data: dict) -> str:
        """Extract and clean event description from API data."""
        description = data.get("description", "")
        if not description:
            # Fallback to excerpt
            excerpt = data.get("excerpt", "")
            if excerpt:
                description = excerpt

        if description:
            clean = _strip_html(description).strip()
            # Truncate to 160 chars for consistency
            if len(clean) > 160:
                clean = clean[:157] + "..."
            return clean

        return ""

    def _extract_image(self, data: dict) -> str | None:
        """Extract event image URL from API data."""
        image = data.get("image", {})
        if isinstance(image, dict):
            url = image.get("url", "")
            if url:
                return url
        return None

    def _extract_categories(self, data: dict) -> list[str]:
        """Extract and map event categories from API data."""
        categories = data.get("categories", [])
        mapped = set()

        for cat in categories:
            if isinstance(cat, dict):
                cat_name = cat.get("name", "")
                if cat_name:
                    mapped_cat = self.map_category(cat_name)
                    mapped.add(mapped_cat)

        if not mapped:
            # Default category for a music venue
            return ["musique"]

        return list(mapped)

    def _extract_tags(self, data: dict) -> list[str]:
        """Extract event tags from API data."""
        tags = []
        api_tags = data.get("tags", [])

        for tag in api_tags:
            if isinstance(tag, dict):
                name = tag.get("name", "").strip().lower()
                if name and name not in tags:
                    tags.append(name)

        return tags[:5]

    def _generate_source_id(self, data: dict) -> str:
        """Generate unique source ID from event data."""
        event_id = data.get("id", "")
        if event_id:
            return f"lemakeda:{event_id}"

        # Fallback: use slug
        slug = data.get("slug", "")
        if slug:
            return f"lemakeda:{slug}"

        return ""


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    clean = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    clean = clean.replace("&amp;", "&")
    clean = clean.replace("&lt;", "<")
    clean = clean.replace("&gt;", ">")
    clean = clean.replace("&quot;", '"')
    clean = clean.replace("&#8217;", "'")
    clean = clean.replace("&#8216;", "'")
    clean = clean.replace("&#8220;", '"')
    clean = clean.replace("&#8221;", '"')
    clean = clean.replace("&#038;", "&")
    clean = clean.replace("&nbsp;", " ")
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean)
    return clean
