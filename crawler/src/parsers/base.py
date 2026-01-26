"""Base parser classes for configurable event extraction."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from ..logger import get_logger
from ..models.event import Event
from ..utils.parser import HTMLParser

if TYPE_CHECKING:
    from bs4 import Tag

logger = get_logger(__name__)

# Paris timezone for event dates
PARIS_TZ = ZoneInfo("Europe/Paris")


@dataclass
class ParsedEvent:
    """
    Intermediate representation of a parsed event.

    This dataclass holds the raw extracted data before conversion
    to the final Event model. It preserves the original strings
    for debugging while also holding parsed values.
    """

    name: str
    source_url: str
    date: datetime | None = None
    start_time: str | None = None
    end_time: str | None = None
    location: str | None = None
    description: str | None = None
    category: str | None = None
    image_url: str | None = None
    tags: list[str] = field(default_factory=list)
    raw_date: str = ""  # Original date string for debugging
    raw_time: str = ""  # Original time string for debugging


@dataclass
class SelectorConfig:
    """Configuration for CSS selectors used in event parsing."""

    # Container selectors
    event_list: str = ""  # Container for all events
    event_item: str = ""  # Individual event item

    # Field selectors (relative to event_item)
    name: str = "h2, h3, .title, .event-title"
    date: str = ".date, .event-date, time"
    time: str = ".time, .event-time, .hour"
    location: str = ".location, .venue, .event-venue"
    description: str = ".description, .excerpt, p"
    category: str = ".category, .tag, .type"
    image: str = "img"
    link: str = "a"
    tags: str = ".tag, .label, .keyword"

    @classmethod
    def from_dict(cls, data: dict) -> "SelectorConfig":
        """Create SelectorConfig from dictionary."""
        return cls(
            event_list=data.get("event_list", ""),
            event_item=data.get("event_item", ""),
            name=data.get("name", cls.name),
            date=data.get("date", cls.date),
            time=data.get("time", cls.time),
            location=data.get("location", cls.location),
            description=data.get("description", cls.description),
            category=data.get("category", cls.category),
            image=data.get("image", cls.image),
            link=data.get("link", cls.link),
            tags=data.get("tags", cls.tags),
        )


class ConfigurableEventParser:
    """
    Configurable event parser using CSS selectors from config.

    This parser extracts events from HTML using selectors defined in
    the source configuration YAML file. It provides a flexible way
    to parse different websites without writing custom code.

    For sites with complex structures, extend this class and override
    specific methods.
    """

    def __init__(
        self,
        config: dict,
        base_url: str,
        source_id: str = "unknown",
        category_map: dict[str, str] | None = None,
    ):
        """
        Initialize configurable parser.

        Args:
            config: Source configuration dictionary
            base_url: Base URL for resolving relative links
            source_id: Unique identifier for this source
            category_map: Mapping from source categories to standard taxonomy
        """
        self.config = config
        self.base_url = base_url
        self.source_id = source_id
        self.category_map = category_map or {}

        # Load selectors from config
        selectors_dict = config.get("selectors", {})
        self.selectors = SelectorConfig.from_dict(selectors_dict)

        # Default fallback selectors for event containers
        self.fallback_item_selectors = [
            ".event-card",
            ".event-item",
            ".event",
            "article.event",
            "[class*='event']",
            ".agenda-item",
            "[class*='agenda']",
        ]

    def parse(self, html: str) -> list[ParsedEvent]:
        """
        Parse HTML and return list of parsed events.

        Args:
            html: HTML content to parse

        Returns:
            List of ParsedEvent objects
        """
        parser = HTMLParser(html, self.base_url)
        events = []

        # Find event containers
        event_items = self._find_event_items(parser)
        logger.debug(f"Found {len(event_items)} event items")

        for item in event_items:
            try:
                event = self._parse_event_item(item, parser)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event item: {e}")

        return events

    def _find_event_items(self, parser: HTMLParser) -> list["Tag"]:
        """
        Find all event item elements on the page.

        Args:
            parser: HTMLParser instance

        Returns:
            List of event item elements
        """
        # Try configured event list container first
        if self.selectors.event_list:
            container = parser.select_one(self.selectors.event_list)
            if container:
                if self.selectors.event_item:
                    return container.select(self.selectors.event_item)

        # Try configured event item selector directly
        if self.selectors.event_item:
            items = parser.select(self.selectors.event_item)
            if items:
                return items

        # Try fallback selectors
        for selector in self.fallback_item_selectors:
            items = parser.select(selector)
            if items:
                logger.debug(f"Using fallback selector: {selector}")
                return items

        logger.warning("No event items found with any selector")
        return []

    def _parse_event_item(
        self, item: "Tag", parser: HTMLParser
    ) -> ParsedEvent | None:
        """
        Parse a single event item element.

        Args:
            item: BeautifulSoup element for event
            parser: HTMLParser instance for utility methods

        Returns:
            ParsedEvent or None if parsing failed
        """
        # Extract name (required)
        name = parser.get_text(item, self.selectors.name)
        if not name:
            logger.debug("Skipping item without name")
            return None

        # Extract URL (required for deduplication)
        event_url = parser.get_link(item, self.selectors.link)
        if not event_url:
            logger.debug(f"Skipping event without URL: {name}")
            return None

        # Extract date
        raw_date = parser.get_text(item, self.selectors.date)
        event_date = parser.parse_date(raw_date) if raw_date else None

        # Extract time
        raw_time = parser.get_text(item, self.selectors.time)
        event_time = parser.parse_time(raw_time) if raw_time else None

        # Extract other fields
        location = parser.get_text(item, self.selectors.location)
        description = parser.get_text(item, self.selectors.description)
        if description:
            description = parser.truncate(description, 160)

        category = parser.get_text(item, self.selectors.category)
        image_url = parser.get_image(item, self.selectors.image)
        tags = self._extract_tags(item, parser)

        return ParsedEvent(
            name=name,
            source_url=event_url,
            date=event_date,
            start_time=event_time,
            location=location,
            description=description,
            category=category,
            image_url=image_url,
            tags=tags,
            raw_date=raw_date,
            raw_time=raw_time,
        )

    def _extract_tags(self, item: "Tag", parser: HTMLParser) -> list[str]:
        """
        Extract tags from event item.

        Args:
            item: Event item element
            parser: HTMLParser instance

        Returns:
            List of tag strings
        """
        tags = []
        tag_elements = item.select(self.selectors.tags)

        for elem in tag_elements:
            tag_text = elem.get_text().strip()
            if tag_text and len(tag_text) < 50:
                tags.append(tag_text.lower())

        return tags[:5]  # Limit to 5 tags

    def to_event(self, parsed: ParsedEvent, default_time: str = "20:00") -> Event:
        """
        Convert ParsedEvent to Event model.

        Args:
            parsed: ParsedEvent to convert
            default_time: Default time if none parsed

        Returns:
            Event model instance
        """
        # Build datetime with timezone
        event_datetime = None
        if parsed.date:
            time_str = parsed.start_time or default_time
            try:
                hour, minute = map(int, time_str.split(":"))
                event_datetime = parsed.date.replace(
                    hour=hour, minute=minute, tzinfo=PARIS_TZ
                )
            except (ValueError, AttributeError):
                event_datetime = parsed.date.replace(tzinfo=PARIS_TZ)

        # Map category
        category = self._map_category(parsed.category)

        # Generate source ID
        source_id = self._generate_source_id(parsed.source_url)

        # Build locations list
        locations = []
        if parsed.location:
            locations.append(parsed.location)

        return Event(
            name=parsed.name,
            event_url=parsed.source_url,
            start_datetime=event_datetime,
            description=parsed.description,
            image=parsed.image_url,
            categories=[category] if category else [],
            locations=locations,
            tags=parsed.tags,
            source_id=source_id,
        )

    def _map_category(self, raw_category: str | None) -> str:
        """
        Map source category to standard taxonomy.

        Args:
            raw_category: Category from source

        Returns:
            Standard category slug
        """
        if not raw_category:
            return "communaute"

        raw_lower = raw_category.lower()

        # Check explicit category map
        for source_cat, target_cat in self.category_map.items():
            if source_cat.lower() in raw_lower:
                return target_cat

        # Default mappings
        defaults = {
            "danse": "danse",
            "dance": "danse",
            "ballet": "danse",
            "musique": "musique",
            "music": "musique",
            "concert": "musique",
            "dj": "musique",
            "theatre": "theatre",
            "théâtre": "theatre",
            "spectacle": "theatre",
            "humour": "theatre",
            "art": "art",
            "expo": "art",
            "exposition": "art",
            "vernissage": "art",
            "cinéma": "art",
            "projection": "art",
        }

        for key, value in defaults.items():
            if key in raw_lower:
                return value

        return "communaute"

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

        return f"{self.source_id}:{event_id}"

    def parse_and_convert(
        self, html: str, default_time: str = "20:00"
    ) -> list[Event]:
        """
        Parse HTML and return list of Event models.

        Convenience method that combines parse() and to_event().

        Args:
            html: HTML content to parse
            default_time: Default time for events without time

        Returns:
            List of Event objects
        """
        parsed_events = self.parse(html)
        events = []

        for parsed in parsed_events:
            try:
                event = self.to_event(parsed, default_time)
                events.append(event)
            except Exception as e:
                logger.warning(f"Failed to convert event '{parsed.name}': {e}")

        return events
