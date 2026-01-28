"""Venue data model for location metadata extracted from event sources."""

from dataclasses import dataclass, field

from .event import slugify


@dataclass
class Venue:
    """
    Venue data model for storing location metadata.

    Extracted from JSON-LD structured data (schema.org Place/LocalBusiness)
    in event source pages. Used to generate Hugo location pages.
    """

    name: str
    slug: str = ""
    street_address: str = ""
    postal_code: str = ""
    city: str = "Marseille"
    latitude: float | None = None
    longitude: float | None = None
    website: str = ""
    venue_type: str = ""
    source_url: str = ""
    aliases: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Generate slug from name if not provided."""
        if not self.slug and self.name:
            self.slug = slugify(self.name)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON/YAML serialization."""
        d = {
            "name": self.name,
            "slug": self.slug,
        }
        if self.street_address:
            d["street_address"] = self.street_address
        if self.postal_code:
            d["postal_code"] = self.postal_code
        if self.city:
            d["city"] = self.city
        if self.latitude is not None:
            d["latitude"] = self.latitude
        if self.longitude is not None:
            d["longitude"] = self.longitude
        if self.website:
            d["website"] = self.website
        if self.venue_type:
            d["venue_type"] = self.venue_type
        if self.source_url:
            d["source_url"] = self.source_url
        if self.aliases:
            d["aliases"] = self.aliases
        return d
