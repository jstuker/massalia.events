"""Parser for Cité de la Musique (citemusique-marseille.com) events.

Cité de la Musique is a concert venue at 4 rue Bernard du Bois, 13001
Marseille. It hosts world music concerts, jazz, classical, electroacoustic
music, open stages, and youth performances across two spaces: Auditorium
and Club 27.

The listing page at /concerts-spectacles/ contains all upcoming events
as <li> elements with rich CSS classes encoding date (d-YYYYMMDD),
genre (musique-du-monde, jazz, etc.), and venue (auditorium, club-27).

Strategy:
1. Parse the listing page for event URLs and metadata from CSS classes.
2. Fetch detail pages for title, description, image, and date/time.
3. Map CSS class categories to our standard taxonomy.
"""

import re
from datetime import datetime
from urllib.parse import urlparse

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import PARIS_TZ
from ..utils.parser import HTMLParser
from ..utils.sanitize import sanitize_description

logger = get_logger(__name__)

# CSS classes on listing <li> that map to event categories
CATEGORY_CLASSES = {
    "concert",
    "spectacle",
    "scene-ouverte",
    "rencontre",
    "projection",
    "jeune-public",
    "conference",
}

# CSS classes representing music genres (used as tags)
GENRE_CLASSES = {
    "musique-du-monde",
    "jazz",
    "musique-classique",
    "musique-contemporaine",
    "musique-electroacoustique",
}

# CSS classes representing venue spaces
VENUE_CLASSES = {
    "auditorium",
    "club-27",
}


class CiteMusiqueParser(BaseCrawler):
    """Parser for Cité de la Musique events.

    Parses the /concerts-spectacles/ listing page for event URLs and
    metadata, then fetches individual detail pages for full event info.
    """

    source_name = "Cité de la Musique"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """Parse events from Cité de la Musique listing page.

        Args:
            parser: HTMLParser with the listing page content.

        Returns:
            List of Event objects.
        """
        events = []

        # Extract event items and their metadata from the listing page
        items = parser.select("li.event-v2-list-item")
        if not items:
            logger.warning("No event items found on Cité de la Musique listing")
            return events

        logger.info(f"Found {len(items)} event items on Cité de la Musique listing")

        # Collect event URLs and listing metadata
        event_data = {}
        event_urls = []

        for item in items:
            link = item.select_one("a[href*='/evenement/']")
            if not link:
                continue

            url = link.get("href", "")
            if not url or url in event_data:
                continue

            # Extract metadata from CSS classes
            classes = item.get("class", [])
            if isinstance(classes, str):
                classes = classes.split()

            event_urls.append(url)
            event_data[url] = {
                "classes": classes,
                "date_class": self._extract_date_from_classes(classes),
                "categories": self._extract_categories_from_classes(classes),
                "tags": self._extract_tags_from_classes(classes),
            }

        if not event_urls:
            logger.warning("No event URLs found on Cité de la Musique listing")
            return events

        logger.info(f"Fetching {len(event_urls)} detail pages")

        # Fetch detail pages concurrently
        pages = self.fetch_pages(event_urls)

        for url in event_urls:
            html = pages.get(url, "")
            if not html:
                continue

            try:
                listing_meta = event_data.get(url, {})
                event = self._parse_detail_page(url, html, listing_meta)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event from {url}: {e}")

        logger.info(f"Parsed {len(events)} events from Cité de la Musique")
        return events

    def _parse_detail_page(
        self, url: str, html: str, listing_meta: dict
    ) -> Event | None:
        """Parse a single event detail page.

        Args:
            url: Event page URL.
            html: HTML content of the detail page.
            listing_meta: Metadata extracted from the listing page CSS classes.

        Returns:
            Event object or None if required fields are missing.
        """
        detail = HTMLParser(html, url)

        # Extract title
        name = self._extract_name(detail)
        if not name:
            logger.debug(f"No title found on: {url}")
            return None

        # Extract date/time
        start_datetime = self._extract_datetime(detail, listing_meta)
        if not start_datetime:
            logger.debug(f"No valid date found for: {name}")
            return None

        # Extract description
        description = self._extract_description(detail)

        # Extract image
        image = self._extract_image(detail)

        # Categories from listing CSS classes
        categories = listing_meta.get("categories", ["musique"])
        if not categories:
            categories = ["musique"]

        # Tags from genre CSS classes
        tags = listing_meta.get("tags", [])

        # Location from detail page
        location = self._extract_location(detail)

        # Source ID from URL slug
        source_id = self._generate_source_id(url)

        return Event(
            name=name,
            event_url=url,
            start_datetime=start_datetime,
            description=description,
            image=image,
            categories=categories,
            locations=[location],
            tags=tags,
            source_id=source_id,
        )

    def _extract_name(self, parser: HTMLParser) -> str:
        """Extract event title from detail page."""
        # Primary: h2.event-title
        name = parser.get_text(parser.soup, "h2.event-title")
        if name:
            return sanitize_description(name)

        # Fallback: first h2
        name = parser.get_text(parser.soup, "h2")
        if name:
            return sanitize_description(name)

        return ""

    def _extract_datetime(
        self, parser: HTMLParser, listing_meta: dict
    ) -> datetime | None:
        """Extract event date and time.

        Uses the listing CSS class date (d-YYYYMMDD) as primary source,
        with time parsed from the .evenement_date text on the detail page.
        """
        # Parse date from listing CSS class (most reliable)
        date_str = listing_meta.get("date_class", "")
        dt = self._parse_date_class(date_str)

        if not dt:
            # Fallback: parse from detail page .evenement_date text
            date_text = parser.get_text(parser.soup, ".evenement_date")
            if date_text:
                dt = self._parse_french_datetime(date_text)

        if not dt:
            return None

        # Extract time from .evenement_date text
        date_text = parser.get_text(parser.soup, ".evenement_date")
        if date_text:
            time_str = HTMLParser.parse_time(date_text)
            if time_str:
                hour, minute = map(int, time_str.split(":"))
                dt = dt.replace(hour=hour, minute=minute)

        # Ensure timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=PARIS_TZ)

        return dt

    def _extract_description(self, parser: HTMLParser) -> str:
        """Extract event description.

        Tries og:description meta tag first, then content paragraphs.
        """
        # Try og:description
        meta = parser.soup.select_one('meta[property="og:description"]')
        if meta:
            content = meta.get("content", "")
            if content:
                clean = sanitize_description(content)
                return HTMLParser.truncate(clean, 160)

        # Fallback: content paragraphs
        content_area = parser.soup.select_one(".content")
        if content_area:
            paragraphs = content_area.select("p")
            for p in paragraphs:
                text = p.get_text().strip()
                if len(text) > 30:
                    clean = sanitize_description(text)
                    return HTMLParser.truncate(clean, 160)

        return ""

    def _extract_image(self, parser: HTMLParser) -> str | None:
        """Extract event image URL.

        Tries .magnific-image href first, then og:image meta tag.
        """
        # Primary: magnific-image link href (full-size image)
        mag = parser.soup.select_one("a.magnific-image")
        if mag:
            href = mag.get("href", "")
            if href and href.startswith("http"):
                return href

        # Fallback: og:image meta
        meta = parser.soup.select_one('meta[property="og:image"]')
        if meta:
            content = meta.get("content", "")
            if content and content.startswith("http"):
                return content

        return None

    def _extract_location(self, parser: HTMLParser) -> str:
        """Extract location from detail page.

        Returns a location slug based on the venue text.
        """
        salle_text = parser.get_text(parser.soup, ".evenement_salle")
        if salle_text:
            lower = salle_text.lower()
            if "club 27" in lower:
                return "cite-de-la-musique"
            if "auditorium" in lower:
                return "cite-de-la-musique"

        # Default for this single-venue source
        return "cite-de-la-musique"

    def _generate_source_id(self, url: str) -> str:
        """Generate unique source ID from event URL slug."""
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        segments = path.split("/")
        slug = segments[-1] if segments else path
        return f"citemusique:{slug}"

    @staticmethod
    def _extract_date_from_classes(classes: list[str]) -> str:
        """Extract date string from CSS classes (d-YYYYMMDD format)."""
        for cls in classes:
            if cls.startswith("d-") and len(cls) == 10:
                return cls[2:]  # Return YYYYMMDD
        return ""

    def _extract_categories_from_classes(self, classes: list[str]) -> list[str]:
        """Map CSS classes to standard event categories."""
        mapped = set()
        for cls in classes:
            if cls in CATEGORY_CLASSES or cls in GENRE_CLASSES:
                cat = self.map_category(cls)
                if cat:
                    mapped.add(cat)

        return list(mapped) if mapped else ["musique"]

    @staticmethod
    def _extract_tags_from_classes(classes: list[str]) -> list[str]:
        """Extract genre tags from CSS classes."""
        tags = []
        for cls in classes:
            if cls in GENRE_CLASSES:
                # Convert CSS class to readable tag
                tag = cls.replace("-", " ")
                tags.append(tag)
        return tags[:5]

    @staticmethod
    def _parse_date_class(date_str: str) -> datetime | None:
        """Parse date from CSS class YYYYMMDD format."""
        if not date_str or len(date_str) != 8:
            return None
        try:
            return datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=PARIS_TZ)
        except ValueError:
            return None

    @staticmethod
    def _parse_french_datetime(text: str) -> datetime | None:
        """Parse French datetime like 'Vendredi 13 Février 2026 à 20h00'."""
        if not text:
            return None

        text = text.strip().lower()

        # Match: day_name DD month YYYY à HHhMM
        pattern = re.compile(
            r"(\d{1,2})\s+(\w+)\s+(\d{4})\s*(?:à|a)\s*(\d{1,2})h(\d{2})?",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            year = int(match.group(3))
            hour = int(match.group(4))
            minute = int(match.group(5)) if match.group(5) else 0

            month = HTMLParser.FRENCH_MONTHS.get(month_name)
            if month:
                try:
                    return datetime(year, month, day, hour, minute, tzinfo=PARIS_TZ)
                except ValueError:
                    pass

        # Fallback: just date without time
        date = HTMLParser.parse_date(text)
        if date:
            return date.replace(tzinfo=PARIS_TZ)

        return None
