"""Parser for La Criée - Théâtre National de Marseille events."""

import re
from datetime import datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

PARIS_TZ = ZoneInfo("Europe/Paris")

# French month name mapping
FRENCH_MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}


def _extract_event_urls_from_html(html: str, base_url: str = "") -> list[str]:
    """
    Extract event detail page URLs from the listing page.

    La Criée event URLs follow: /programmation/evenements/{slug}

    Args:
        html: HTML content of the listing page
        base_url: Base URL for resolving relative links

    Returns:
        List of unique event detail URLs
    """
    parser = HTMLParser(html, base_url)
    urls = set()

    for link in parser.select("a[href*='/programmation/evenements/']"):
        href = link.get("href", "")
        if not href:
            continue

        # Resolve relative URLs
        if href.startswith("/"):
            href = urljoin(base_url, href)

        # Only include detail pages, not the listing itself
        # Detail pages have a slug after /evenements/
        path = href.rstrip("/")
        if "/programmation/evenements/" in path:
            slug_part = path.split("/programmation/evenements/")[-1]
            if slug_part and "/" not in slug_part:
                urls.add(href)

    return sorted(urls)


def _parse_french_date(text: str) -> datetime | None:
    """
    Parse a French date string like "29 janvier 2026" to a date.

    Args:
        text: French date text

    Returns:
        datetime (date only, time at midnight) or None
    """
    text = text.strip().lower()
    match = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", text)
    if not match:
        return None

    day = int(match.group(1))
    month_name = match.group(2)
    year = int(match.group(3))

    month = FRENCH_MONTHS.get(month_name)
    if not month:
        return None

    try:
        return datetime(year, month, day, tzinfo=PARIS_TZ)
    except ValueError:
        return None


def _parse_french_time(text: str) -> tuple[int, int] | None:
    """
    Parse a French time string like "20h", "20h30", "18h15".

    Args:
        text: Time text

    Returns:
        Tuple of (hour, minute) or None
    """
    match = re.search(r"(\d{1,2})h(\d{2})?", text.strip().lower())
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    return (hour, minute)


def _parse_showtimes_from_html(html: str) -> list[dict]:
    """
    Extract individual showtimes from an event detail page.

    La Criée structures dates as blocks with day-of-week headings,
    date text, time, and venue. The pattern in the HTML is:
    - Date: "29 janvier 2026"
    - Time: "20h" or "18h15"
    - Venue: "La Criée - Salle Déméter" or external venue

    Args:
        html: HTML content of the detail page

    Returns:
        List of dicts with 'datetime' and 'venue' keys
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    showtimes = []

    # Strategy: find all text that matches date patterns, then look for
    # adjacent time patterns
    full_text = soup.get_text(separator="\n")
    lines = [line.strip() for line in full_text.split("\n") if line.strip()]

    # Date pattern: "29 janvier 2026"
    date_pattern = re.compile(
        r"(\d{1,2})\s+(janvier|février|fevrier|mars|avril|mai|juin|"
        r"juillet|août|aout|septembre|octobre|novembre|décembre|decembre)"
        r"\s+(\d{4})",
        re.IGNORECASE,
    )
    # Time pattern: "20h" or "20h30"
    time_pattern = re.compile(r"^(\d{1,2})h(\d{2})?$", re.IGNORECASE)

    current_date = None

    for i, line in enumerate(lines):
        # Check for date
        date_match = date_pattern.search(line)
        if date_match:
            dt = _parse_french_date(line)
            if dt:
                current_date = dt
            continue

        # Check for time (only if we have a current date)
        if current_date:
            time_match = time_pattern.match(line)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0

                event_dt = current_date.replace(hour=hour, minute=minute)

                # Look ahead for venue in next few lines
                venue = _find_venue_in_lines(lines, i + 1)

                showtimes.append(
                    {
                        "datetime": event_dt,
                        "venue": venue or "La Criée",
                    }
                )
                continue

    # Deduplicate by datetime
    seen = set()
    unique_showtimes = []
    for st in showtimes:
        key = st["datetime"].isoformat()
        if key not in seen:
            seen.add(key)
            unique_showtimes.append(st)

    return unique_showtimes


def _find_venue_in_lines(lines: list[str], start_idx: int) -> str | None:
    """
    Look ahead in lines to find a venue name after a time entry.

    Skips labels like "Représentation", "Première", "Complet", etc.

    Args:
        lines: List of text lines
        start_idx: Index to start looking from

    Returns:
        Venue name or None
    """
    skip_patterns = {
        "représentation",
        "premiere",
        "première",
        "complet",
        "prendre des places",
        "réserver",
        "audiodescription",
        "visite",
        "rencontre",
        "bord de scène",
        "scolaire",
        "prochainement",
    }

    for i in range(start_idx, min(start_idx + 5, len(lines))):
        line = lines[i].strip()
        line_lower = line.lower()

        # Skip empty and label lines
        if not line or line_lower in skip_patterns:
            continue
        if any(p in line_lower for p in skip_patterns):
            continue

        # Venue indicators
        if "la criée" in line_lower or "salle" in line_lower:
            return line
        if "zef" in line_lower or "théâtre" in line_lower:
            return line

        # If it looks like an address or venue (contains comma or starts with capital)
        if "," in line and any(c.isdigit() for c in line):
            return line

    return None


class LaCrieeParser(BaseCrawler):
    """
    Event parser for La Criée - Théâtre National de Marseille.

    La Criée is the national theatre of Marseille, located on the
    Vieux-Port. It hosts theatre, dance, music, and cinema events.

    This parser:
    1. Extracts event URLs from the listing page
    2. Visits each detail page
    3. Parses French dates, times, category, description, and image
    4. Creates separate Event objects for each showtime
    """

    source_name = "La Criée"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from La Criée listing page.

        Args:
            parser: HTMLParser with the listing page content

        Returns:
            List of Event objects
        """
        events = []

        # Extract event URLs from listing
        event_urls = _extract_event_urls_from_html(str(parser.soup), self.base_url)

        if not event_urls:
            logger.warning("No event URLs found on La Criée")
            return events

        logger.info(f"Found {len(event_urls)} event URLs on La Criée")

        # Visit each detail page
        for event_url in event_urls:
            try:
                page_events = self._parse_detail_page(event_url)
                events.extend(page_events)
            except Exception as e:
                logger.warning(f"Failed to parse event from {event_url}: {e}")

        logger.info(
            f"Extracted {len(events)} events (including multi-date) from La Criée"
        )
        return events

    def _parse_detail_page(self, event_url: str) -> list[Event]:
        """
        Fetch and parse an event detail page.

        Creates a separate Event for each future showtime.

        Args:
            event_url: URL of the event detail page

        Returns:
            List of Event objects (one per showtime)
        """
        html = self.fetch_page(event_url)
        if not html:
            logger.warning(f"Failed to fetch detail page: {event_url}")
            return []

        detail_parser = HTMLParser(html, event_url)

        # Extract event name
        name = self._extract_name(detail_parser)
        if not name:
            logger.debug(f"Could not find event name on: {event_url}")
            return []

        # Extract category
        category = self._extract_category(detail_parser)

        # Extract description
        description = self._extract_description(detail_parser)

        # Extract image (og:image or first significant image)
        image_url = self._extract_image(detail_parser)

        # Extract tags (creator/director names)
        tags = self._extract_tags(detail_parser)

        # Generate base source ID
        source_id_base = _generate_source_id(event_url)

        # Parse all showtimes
        showtimes = _parse_showtimes_from_html(html)

        if not showtimes:
            logger.debug(f"No showtimes found for: {name} on {event_url}")
            return []

        # Filter to future dates and create events
        now = datetime.now(PARIS_TZ)
        events = []

        for st in showtimes:
            dt = st["datetime"]

            # Skip past dates
            if dt < now:
                continue

            # Determine location
            venue_text = st.get("venue", "La Criée")
            location = self.map_location(venue_text)

            event = Event(
                name=name,
                event_url=event_url,
                start_datetime=dt,
                description=description,
                image=image_url,
                categories=[category] if category else ["theatre"],
                locations=[location],
                tags=tags,
                source_id=f"{source_id_base}:{dt.strftime('%Y%m%d-%H%M')}",
            )
            events.append(event)

        return events

    def _extract_name(self, parser: HTMLParser) -> str:
        """Extract event name from detail page."""
        # Try h1 first
        h1 = parser.select_one("h1")
        if h1:
            return h1.get_text().strip()

        # Fallback selectors
        for selector in ["h2", ".spectacle-title"]:
            elem = parser.select_one(selector)
            if elem:
                return elem.get_text().strip()

        return ""

    def _extract_category(self, parser: HTMLParser) -> str:
        """Extract and map event category from detail page."""
        # La Criée shows category near the title, often as a standalone
        # text element. The page text contains category labels like
        # "Théâtre", "Musique", "Danse" etc.
        text = parser.soup.get_text()

        # Known categories to search for in page text
        category_keywords = [
            "Théâtre jeune public",
            "Jeune public",
            "Cinéma - Musique",
            "Cinéma",
            "Théâtre et philosophie",
            "Lecture théâtralisée",
            "Théâtre",
            "Musique",
            "Danse",
            "Conte",
            "Lecture",
            "Rencontres",
        ]

        for kw in category_keywords:
            if kw in text:
                return self.map_category(kw)

        return "theatre"  # Default for a theatre venue

    def _extract_description(self, parser: HTMLParser) -> str:
        """Extract event description from detail page."""
        # Try common description patterns
        for selector in [
            "article p",
            ".description p",
            ".content p",
            "main p",
        ]:
            elems = parser.select(selector)
            for elem in elems:
                text = elem.get_text().strip()
                # Skip very short text and navigation/label text
                if len(text) > 50:
                    return HTMLParser.truncate(text, 160)

        # Fallback: find first substantial paragraph
        for p in parser.select("p"):
            text = p.get_text().strip()
            if len(text) > 50:
                return HTMLParser.truncate(text, 160)

        return ""

    def _extract_image(self, parser: HTMLParser) -> str | None:
        """Extract main image from detail page."""
        # Try og:image meta tag
        og_image = parser.select_one('meta[property="og:image"]')
        if og_image:
            content = og_image.get("content", "")
            if content:
                return str(content)

        # Try images in the page with the storage URL pattern
        for img in parser.select("img"):
            src = img.get("src", "") or img.get("data-src", "")
            if src and "/storage/" in str(src):
                if str(src).startswith("/"):
                    src = urljoin("https://theatre-lacriee.com", str(src))
                return str(src)

        return None

    def _extract_tags(self, parser: HTMLParser) -> list[str]:
        """Extract tags (creator/director names) from detail page."""
        tags = []

        # Look for text patterns like "Author / Director" near the title
        # These appear as subtitle text after h1
        for elem in parser.select("h2, h3"):
            text = elem.get_text().strip()
            # Looks like "Eugène Ionesco / Robin Renucci" or "Molière / Macha Makeïeff"
            if "/" in text and len(text) < 100:
                parts = [p.strip().lower() for p in text.split("/")]
                tags.extend(p for p in parts if p)

        return tags[:5]


def _generate_source_id(url: str) -> str:
    """Generate a unique source ID from an event URL."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path.strip("/")
    segments = path.split("/")
    event_slug = segments[-1] if segments else path
    return f"lacriee:{event_slug}"
