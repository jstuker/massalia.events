"""Parser for La Friche Belle de Mai events."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

# Paris timezone for event dates
PARIS_TZ = ZoneInfo("Europe/Paris")


class LaFricheParser(BaseCrawler):
    """
    Event parser for La Friche Belle de Mai (https://lafriche.org).

    La Friche is a major cultural center in Marseille hosting concerts,
    exhibitions, performances, and community events.

    Note: This is a template parser. The actual CSS selectors and
    extraction logic should be updated based on the current website
    structure, which may change over time.
    """

    source_name = "La Friche"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from La Friche agenda page.

        Args:
            parser: HTMLParser with page content

        Returns:
            List of Event objects
        """
        events = []

        # NOTE: These selectors are examples and should be verified
        # against the actual website structure
        event_cards = parser.select(".event-card, .agenda-item, article.event")

        if not event_cards:
            # Try alternative selectors
            event_cards = parser.select("[class*='event'], [class*='agenda']")
            logger.debug(f"Using fallback selectors, found {len(event_cards)} items")

        for card in event_cards:
            try:
                event = self._parse_event_card(card, parser)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event card: {e}")

        return events

    def _parse_event_card(self, card, parser: HTMLParser) -> Event | None:
        """
        Parse a single event card element.

        Args:
            card: BeautifulSoup element for event card
            parser: Parent HTMLParser for utility methods

        Returns:
            Event object or None if parsing failed
        """
        # Extract event name
        name = parser.get_text(card, "h2, h3, .event-title, .title")
        if not name:
            logger.debug("Skipping card without name")
            return None

        # Extract event URL
        event_url = parser.get_link(card, "a")
        if not event_url:
            logger.debug(f"Skipping event without URL: {name}")
            return None

        # Extract date and time
        date_text = parser.get_text(card, ".date, .event-date, time")
        time_text = parser.get_text(card, ".time, .event-time, .hour")

        event_date = self._parse_date(date_text)
        if not event_date:
            logger.debug(f"Could not parse date for: {name} ({date_text})")
            return None

        event_time = parser.parse_time(time_text) or "20:00"
        hour, minute = map(int, event_time.split(":"))
        event_datetime = event_date.replace(
            hour=hour, minute=minute, tzinfo=PARIS_TZ
        )

        # Extract description
        description = parser.get_text(card, ".description, .excerpt, p")
        description = parser.truncate(description, 160)

        # Extract image
        image_url = parser.get_image(card, "img")

        # Extract category
        category_text = parser.get_text(card, ".category, .tag, .type")
        category = self.map_category(category_text) if category_text else "communaute"

        # Generate source ID
        source_id = self._generate_source_id(event_url)

        # Create event
        return Event(
            name=name,
            event_url=event_url,
            start_datetime=event_datetime,
            description=description,
            image=image_url if image_url else None,
            categories=[category],
            locations=["la-friche"],
            tags=self._extract_tags(card, parser),
            source_id=source_id,
        )

    def _parse_date(self, text: str) -> datetime | None:
        """
        Parse French date formats.

        Args:
            text: Date text to parse

        Returns:
            datetime object or None
        """
        if not text:
            return None

        # Clean text
        text = text.strip().lower()

        # French month names
        months = {
            "janvier": 1, "février": 2, "fevrier": 2, "mars": 3,
            "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
            "août": 8, "aout": 8, "septembre": 9, "octobre": 10,
            "novembre": 11, "décembre": 12, "decembre": 12,
        }

        # Try pattern: "26 janvier 2026" or "26 janvier"
        pattern = r"(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?"
        match = re.search(pattern, text)

        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            year = int(match.group(3)) if match.group(3) else datetime.now().year

            month = months.get(month_name)
            if month:
                try:
                    return datetime(year, month, day)
                except ValueError:
                    pass

        # Try pattern: "26/01/2026" or "26/01"
        pattern = r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?"
        match = re.search(pattern, text)

        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = match.group(3)
            if year:
                year = int(year)
                if year < 100:
                    year += 2000
            else:
                year = datetime.now().year

            try:
                return datetime(year, month, day)
            except ValueError:
                pass

        return None

    def _generate_source_id(self, url: str) -> str:
        """
        Generate unique source ID from URL.

        Args:
            url: Event URL

        Returns:
            Source ID string
        """
        # Extract path or ID from URL
        # Example: https://lafriche.org/event/concert-123 -> lafriche:concert-123
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = parsed.path.strip("/")

        # Use last path segment as ID
        segments = path.split("/")
        event_id = segments[-1] if segments else path

        return f"lafriche:{event_id}"

    def _extract_tags(self, card, parser: HTMLParser) -> list[str]:
        """
        Extract tags from event card.

        Args:
            card: Event card element
            parser: HTMLParser instance

        Returns:
            List of tag strings
        """
        tags = []

        # Look for tag elements
        tag_elements = card.select(".tag, .label, .keyword")
        for elem in tag_elements:
            tag_text = elem.get_text().strip()
            if tag_text and len(tag_text) < 50:
                tags.append(tag_text.lower())

        return tags[:5]  # Limit to 5 tags
