"""Event data model matching Hugo front matter schema."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from slugify import slugify as _slugify


def slugify(text: str) -> str:
    """Convert text to URL-friendly ASCII slug.

    Uses python-slugify to transliterate all Unicode characters to ASCII,
    producing human-readable URLs without percent-encoded characters.
    """
    return _slugify(text)


def format_french_date(dt: datetime) -> str:
    """Format date as French taxonomy slug: 'jour-DD-mois'."""
    days = {
        0: "lundi",
        1: "mardi",
        2: "mercredi",
        3: "jeudi",
        4: "vendredi",
        5: "samedi",
        6: "dimanche",
    }
    months = {
        1: "janvier",
        2: "fevrier",
        3: "mars",
        4: "avril",
        5: "mai",
        6: "juin",
        7: "juillet",
        8: "aout",
        9: "septembre",
        10: "octobre",
        11: "novembre",
        12: "decembre",
    }
    day_name = days[dt.weekday()]
    month_name = months[dt.month]
    return f"{day_name}-{dt.day:02d}-{month_name}"


@dataclass
class Event:
    """
    Event data model matching Hugo front matter schema.

    This model represents a cultural event for the Massalia Events calendar.
    All fields align with the archetypes/events.md Hugo template.
    """

    # Required fields
    name: str
    event_url: str
    start_datetime: datetime  # Combined date and time

    # Optional fields with defaults
    description: str = ""
    image: str | None = None
    categories: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # Multi-day event support
    event_group_id: str | None = None
    day_of: str | None = None  # e.g., "Jour 1 sur 3"

    # Tracking fields
    source_id: str | None = None
    draft: bool = False

    def __post_init__(self):
        """Validate and normalize fields after initialization."""
        if not self.name:
            raise ValueError("Event name is required")
        if not self.event_url:
            raise ValueError("Event URL is required")
        if not self.start_datetime:
            raise ValueError("Start datetime is required")

        # Normalize categories to lowercase
        self.categories = [c.lower() for c in self.categories]
        # Normalize locations to slugs
        self.locations = [slugify(loc) for loc in self.locations]

    @property
    def title(self) -> str:
        """Generate page title (used for URLs and SEO)."""
        if self.day_of:
            return f"{self.name} - {self.day_of}"
        return self.name

    @property
    def slug(self) -> str:
        """Generate URL-friendly slug from title."""
        return slugify(self.title)

    @property
    def date(self) -> datetime:
        """Publication date (event start date/time)."""
        return self.start_datetime

    @property
    def start_time(self) -> str:
        """Event start time in 24h format."""
        return self.start_datetime.strftime("%H:%M")

    @property
    def expiry_date(self) -> datetime:
        """When to stop showing event (midnight after event)."""
        next_day = self.start_datetime.date() + timedelta(days=1)
        return datetime.combine(
            next_day,
            datetime.min.time(),
            tzinfo=self.start_datetime.tzinfo,
        )

    @property
    def dates_taxonomy(self) -> list[str]:
        """Generate dates taxonomy terms in French format."""
        return [format_french_date(self.start_datetime)]

    @property
    def file_path(self) -> str:
        """
        Generate Hugo content file path.

        Format: YYYY/MM/DD/slug.fr.md
        """
        dt = self.start_datetime
        return f"{dt.year}/{dt.month:02d}/{dt.day:02d}/{self.slug}.fr.md"

    def to_front_matter(self) -> dict:
        """
        Convert to Hugo front matter dictionary.

        Returns a dict ready for YAML serialization.
        """

        # Format datetime with timezone for Hugo
        def format_datetime(dt: datetime) -> str:
            if dt.tzinfo:
                return dt.isoformat()
            # Assume Paris timezone if not specified
            return dt.strftime("%Y-%m-%dT%H:%M:%S+01:00")

        fm = {
            "title": self.title,
            "date": format_datetime(self.date),
            "draft": self.draft,
            "expiryDate": format_datetime(self.expiry_date),
            "name": self.name,
            "eventURL": self.event_url,
            "startTime": self.start_time,
            "description": self.description,
            "categories": self.categories,
            "locations": self.locations,
            "dates": self.dates_taxonomy,
            "tags": self.tags,
        }

        # Optional fields
        if self.image:
            fm["image"] = self.image
        if self.event_group_id:
            fm["eventGroupId"] = self.event_group_id
        if self.day_of:
            fm["dayOf"] = self.day_of
        if self.source_id:
            fm["sourceId"] = self.source_id

        # Add crawl timestamp
        fm["lastCrawled"] = format_datetime(datetime.now())
        fm["expired"] = False

        return fm

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        """Create Event from dictionary (e.g., from parser output)."""
        # Parse datetime if string
        start_datetime = data.get("start_datetime")
        if isinstance(start_datetime, str):
            start_datetime = datetime.fromisoformat(start_datetime)

        return cls(
            name=data.get("name", ""),
            event_url=data.get("event_url", ""),
            start_datetime=start_datetime,
            description=data.get("description", ""),
            image=data.get("image"),
            categories=data.get("categories", []),
            locations=data.get("locations", []),
            tags=data.get("tags", []),
            event_group_id=data.get("event_group_id"),
            day_of=data.get("day_of"),
            source_id=data.get("source_id"),
            draft=data.get("draft", False),
        )
