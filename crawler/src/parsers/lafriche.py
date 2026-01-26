"""Parser for La Friche Belle de Mai events."""

from datetime import datetime
from zoneinfo import ZoneInfo

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.parser import HTMLParser
from .base import ConfigurableEventParser

logger = get_logger(__name__)

# Paris timezone for event dates
PARIS_TZ = ZoneInfo("Europe/Paris")


class LaFricheParser(BaseCrawler):
    """
    Event parser for La Friche Belle de Mai (https://lafriche.org).

    La Friche is a major cultural center in Marseille hosting concerts,
    exhibitions, performances, and community events.

    This parser uses the ConfigurableEventParser for selector-based
    extraction and extends it with La Friche-specific logic.
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
        Parse events from La Friche agenda page.

        Args:
            parser: HTMLParser with page content

        Returns:
            List of Event objects
        """
        events = []

        # Try to use configurable parser first
        event_cards = self._find_event_cards(parser)

        if not event_cards:
            logger.warning("No event cards found on La Friche page")
            return events

        for card in event_cards:
            try:
                event = self._parse_event_card(card, parser)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event card: {e}")

        return events

    def _find_event_cards(self, parser: HTMLParser):
        """Find event cards using configured or fallback selectors."""
        selectors = self._configurable_parser.selectors

        # Try configured selectors
        if selectors.event_list and selectors.event_item:
            container = parser.select_one(selectors.event_list)
            if container:
                cards = container.select(selectors.event_item)
                if cards:
                    return cards

        if selectors.event_item:
            cards = parser.select(selectors.event_item)
            if cards:
                return cards

        # Try common La Friche selectors
        fallback_selectors = [
            ".event-card",
            ".agenda-item",
            "article.event",
            ".event",
            "[class*='event']",
            "[class*='agenda']",
        ]

        for selector in fallback_selectors:
            cards = parser.select(selector)
            if cards:
                logger.debug(f"Using fallback selector: {selector}")
                return cards

        return []

    def _parse_event_card(self, card, parser: HTMLParser) -> Event | None:
        """
        Parse a single event card element.

        Args:
            card: BeautifulSoup element for event card
            parser: Parent HTMLParser for utility methods

        Returns:
            Event object or None if parsing failed
        """
        selectors = self._configurable_parser.selectors

        # Extract event name
        name = parser.get_text(card, selectors.name)
        if not name:
            logger.debug("Skipping card without name")
            return None

        # Extract event URL
        event_url = parser.get_link(card, selectors.link)
        if not event_url:
            logger.debug(f"Skipping event without URL: {name}")
            return None

        # Extract date and time
        date_text = parser.get_text(card, selectors.date)
        time_text = parser.get_text(card, selectors.time)

        event_date = parser.parse_date(date_text)
        if not event_date:
            # Try to parse date from the name or description
            event_date = self._try_parse_date_from_text(name, parser)
            if not event_date:
                logger.debug(f"Could not parse date for: {name} ({date_text})")
                return None

        event_time = parser.parse_time(time_text) or "20:00"
        hour, minute = map(int, event_time.split(":"))
        event_datetime = event_date.replace(
            hour=hour, minute=minute, tzinfo=PARIS_TZ
        )

        # Extract description
        description = parser.get_text(card, selectors.description)
        description = parser.truncate(description, 160) if description else ""

        # Extract image
        image_url = parser.get_image(card, selectors.image)

        # Extract category
        category_text = parser.get_text(card, selectors.category)
        category = self.map_category(category_text) if category_text else "communaute"

        # Generate source ID
        source_id = self._generate_source_id(event_url)

        # Extract tags
        tags = self._extract_tags(card, parser)

        # Create event
        return Event(
            name=name,
            event_url=event_url,
            start_datetime=event_datetime,
            description=description,
            image=image_url if image_url else None,
            categories=[category],
            locations=["la-friche"],
            tags=tags,
            source_id=source_id,
        )

    def _try_parse_date_from_text(self, text: str, parser: HTMLParser) -> datetime | None:
        """
        Try to extract date from text content.

        Args:
            text: Text that might contain a date
            parser: HTMLParser for parsing

        Returns:
            datetime or None
        """
        return parser.parse_date(text)

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
        selectors = self._configurable_parser.selectors

        tag_elements = card.select(selectors.tags)
        for elem in tag_elements:
            tag_text = elem.get_text().strip()
            if tag_text and len(tag_text) < 50:
                tags.append(tag_text.lower())

        return tags[:5]  # Limit to 5 tags
