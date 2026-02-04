"""Parser for Théâtre de l'Œuvre events."""

import re
from datetime import datetime
from urllib.parse import urljoin

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import FRENCH_MONTHS, PARIS_TZ, infer_year, parse_french_time
from ..utils.parser import HTMLParser

logger = get_logger(__name__)


class LoeuvreParser(BaseCrawler):
    """
    Event parser for Théâtre de l'Œuvre (https://www.theatre-oeuvre.com).

    Théâtre de l'Œuvre is a 170-seat venue near La Canebière in Marseille's
    Belsunce district, hosting theatre, music, dance, and young audience shows.

    This parser extracts event links from the programmation page and visits
    each event's detail page to extract complete information.
    """

    source_name = "Théâtre de l'Œuvre"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from Théâtre de l'Œuvre by visiting detail pages.

        1. Extracts all event URLs from the programmation page
        2. Visits each event's detail page
        3. Extracts complete event information from the detail page

        Args:
            parser: HTMLParser with programmation page content

        Returns:
            List of Event objects
        """
        events = []

        event_urls = self._find_event_urls(parser)

        if not event_urls:
            logger.warning(
                "No event URLs found on Théâtre de l'Œuvre programmation page"
            )
            return events

        logger.info(
            f"Found {len(event_urls)} event URLs on Théâtre de l'Œuvre programmation"
        )

        for event_url in event_urls:
            try:
                event = self._parse_detail_page(event_url)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event from {event_url}: {e}")

        return events

    def _find_event_urls(self, parser: HTMLParser) -> list[str]:
        """
        Find all event detail page URLs from the programmation page.

        Args:
            parser: HTMLParser with programmation page content

        Returns:
            List of unique event URLs
        """
        urls = set()

        for link in parser.select("a[href*='/evenements/']"):
            href = link.get("href", "")
            if not href:
                continue

            # Make absolute URL
            if href.startswith("/"):
                href = urljoin("https://www.theatre-oeuvre.com", href)

            # Only include event detail pages, not the listing itself
            if "/evenements/" in href and href.rstrip("/") != (
                "https://www.theatre-oeuvre.com/evenements"
            ):
                # Skip if this link contains a "Complet" or "Annulé" badge
                if self._is_cancelled_or_sold_out(link):
                    name = link.select_one("h3")
                    name_text = name.get_text().strip() if name else href
                    logger.debug(f"Skipping sold out/cancelled event: {name_text}")
                    continue

                urls.add(href)

        return list(urls)

    def _is_cancelled_or_sold_out(self, link_element) -> bool:
        """
        Check if an event card indicates the event is sold out or cancelled.

        Args:
            link_element: BeautifulSoup element for the event card link

        Returns:
            True if event should be skipped
        """
        text = link_element.get_text().lower()
        return "complet" in text or "annulé" in text

    def _parse_detail_page(self, event_url: str) -> Event | None:
        """
        Fetch and parse an event detail page.

        Args:
            event_url: URL of the event detail page

        Returns:
            Event object or None if parsing failed
        """
        html = self.fetch_page(event_url)
        if not html:
            logger.warning(f"Failed to fetch detail page: {event_url}")
            return None

        detail_parser = HTMLParser(html, event_url)

        # Extract event name from h1
        name = self._extract_name(detail_parser)
        if not name:
            logger.debug(f"Could not find event name on: {event_url}")
            return None

        # Extract date and time
        event_datetime = self._extract_datetime(detail_parser)
        if not event_datetime:
            logger.debug(f"Could not parse date for: {name} on {event_url}")
            return None

        # Extract other fields
        description = self._extract_description(detail_parser)
        image_url = self._extract_image(detail_parser)
        category = self._extract_category(detail_parser)
        tags = self._extract_tags(detail_parser)
        location = self._extract_location(detail_parser)
        source_id = self._generate_source_id(event_url)

        return Event(
            name=name,
            event_url=event_url,
            start_datetime=event_datetime,
            description=description,
            image=image_url,
            categories=[category],
            locations=[location],
            tags=tags,
            source_id=source_id,
        )

    # Venue name variants used to distinguish venue heading from event title
    _VENUE_NAMES = {
        "théâtre de l'œuvre",
        "theatre de l'oeuvre",
        "théâtre de l'oeuvre",
        "théâtre de l'œuvre – marseille",
        "theatre de l'oeuvre – marseille",
    }

    def _extract_name(self, parser: HTMLParser) -> str:
        """
        Extract event name from detail page.

        The site inconsistently uses h1/h2 for the event title vs venue name.
        We check both and return whichever is NOT the venue name.
        """
        h1 = parser.select_one("h1")
        h2 = parser.select_one("h2")

        h1_text = h1.get_text().strip() if h1 else ""
        h2_text = h2.get_text().strip() if h2 else ""

        h1_is_venue = h1_text.lower() in self._VENUE_NAMES
        h2_is_venue = h2_text.lower() in self._VENUE_NAMES

        # Return whichever heading is NOT the venue name
        if h1_text and not h1_is_venue:
            return h1_text
        if h2_text and not h2_is_venue:
            return h2_text

        # Fallback: return h1 even if it looks like venue name
        return h1_text or h2_text

    def _extract_datetime(self, parser: HTMLParser) -> datetime | None:
        """
        Extract event date and time from detail page.

        Théâtre de l'Œuvre displays dates like:
        - "samedi 31 janvier" with separate "19:00"
        - "vendredi 27 mars" with "20:30"

        The year is inferred from context (current or next year).
        """
        date_result = None
        time_result = None

        # Search all text elements for date and time patterns
        for elem in parser.select("p, div, span, h2, h3, h4, time"):
            text = elem.get_text().strip()
            if not text or len(text) > 200:
                continue

            # Try to find date pattern: "samedi 31 janvier" or "31 janvier"
            if not date_result:
                date_result = self._parse_french_date(text)

            # Try to find time pattern: "19:00" or "20:30" or "19h30"
            if not time_result:
                time_result = self._parse_time(text)

        if not date_result:
            return None

        hour, minute = time_result if time_result else (20, 0)

        try:
            return date_result.replace(hour=hour, minute=minute, tzinfo=PARIS_TZ)
        except ValueError:
            return None

    def _parse_french_date(self, text: str) -> datetime | None:
        """
        Parse a French date string without year.

        Handles:
        - "samedi 31 janvier"
        - "vendredi 27 mars"
        - "31 janvier 2026"

        When no year is given, infers the correct year based on whether
        the date has already passed.
        """
        if not text:
            return None

        text_lower = text.lower()

        # Pattern with year: "31 janvier 2026"
        with_year = re.search(
            r"(\d{1,2})\s+(\w+)\s+(\d{4})", text_lower
        )
        if with_year:
            day = int(with_year.group(1))
            month_name = with_year.group(2)
            year = int(with_year.group(3))
            month = FRENCH_MONTHS.get(month_name)
            if month:
                try:
                    return datetime(year, month, day)
                except ValueError:
                    pass

        # Pattern without year: "samedi 31 janvier" or "31 janvier"
        without_year = re.search(
            r"(\d{1,2})\s+(\w+)\b", text_lower
        )
        if without_year:
            day = int(without_year.group(1))
            month_name = without_year.group(2)
            month = FRENCH_MONTHS.get(month_name)
            if month:
                year = self._infer_year(month, day)
                try:
                    return datetime(year, month, day)
                except ValueError:
                    pass

        return None

    def _parse_time(self, text: str) -> tuple[int, int] | None:
        """Extract time from text. Delegates to shared utility."""
        return parse_french_time(text)

    def _infer_year(self, month: int, day: int) -> int:
        """Infer the year for a date without year. Delegates to shared utility."""
        return infer_year(month, day)

    def _extract_description(self, parser: HTMLParser) -> str:
        """Extract event description from detail page."""
        # Try og:description meta tag first
        og_desc = parser.select_one('meta[property="og:description"]')
        if og_desc:
            content = og_desc.get("content", "")
            if content and len(str(content)) > 20:
                return HTMLParser.truncate(str(content).strip(), 160)

        # Try substantial paragraphs
        for p in parser.select("p"):
            text = p.get_text().strip()
            if len(text) > 50:
                return HTMLParser.truncate(text, 160)

        return ""

    def _extract_image(self, parser: HTMLParser) -> str | None:
        """Extract main image from detail page."""
        # Try og:image meta tag first
        og_image = parser.select_one('meta[property="og:image"]')
        if og_image:
            content = og_image.get("content", "")
            if content:
                return str(content)

        # Try main content images
        for selector in ["article img", ".entry-content img", "img"]:
            img = parser.select_one(selector)
            if img:
                src = img.get("src", "") or img.get("data-src", "")
                if src and not str(src).startswith("data:"):
                    return str(urljoin("https://www.theatre-oeuvre.com", str(src)))

        return None

    def _extract_category(self, parser: HTMLParser) -> str:
        """
        Extract and map category from detail page.

        The site uses two patterns:
        - <dt>Genre :</dt><dd>Pop française</dd> (definition list)
        - Breadcrumb with "Catégorie : Musique"
        """
        # Try Genre definition list: <dt>Genre :</dt><dd>value</dd>
        for dt in parser.select("dt"):
            if "genre" in dt.get_text().lower():
                dd = dt.find_next_sibling("dd")
                if dd:
                    # Genre may contain multiple values like "Rap - Jazz"
                    genre_text = dd.get_text().strip()
                    for part in re.split(r"\s*[-–/,]\s*", genre_text):
                        part = part.strip()
                        if part:
                            mapped = self.map_category(part)
                            if mapped != "communaute":
                                return mapped

        # Try breadcrumb links containing "Catégorie :"
        for link in parser.select("a"):
            text = link.get_text().strip()
            if "catégorie" in text.lower() or "categorie" in text.lower():
                # Extract category name after the colon
                cat_match = re.search(r"[Cc]at[ée]gorie\s*:\s*(.+)", text)
                if cat_match:
                    mapped = self.map_category(cat_match.group(1).strip())
                    if mapped != "communaute":
                        return mapped

        # Try JSON-LD breadcrumb data
        for script in parser.select('script[type="application/ld+json"]'):
            try:
                import json

                data = json.loads(script.string or "")
                breadcrumb = data if data.get("@type") == "BreadcrumbList" else None
                if not breadcrumb and isinstance(data, dict):
                    breadcrumb = data.get("breadcrumb")
                if breadcrumb:
                    for item in breadcrumb.get("itemListElement", []):
                        name = item.get("name", "")
                        cat_match = re.search(
                            r"[Cc]at[ée]gorie\s*:\s*(.+)", name
                        )
                        if cat_match:
                            mapped = self.map_category(cat_match.group(1).strip())
                            if mapped != "communaute":
                                return mapped
            except (json.JSONDecodeError, AttributeError):
                continue

        # Default for this venue (mixed programming)
        return "communaute"

    def _extract_tags(self, parser: HTMLParser) -> list[str]:
        """
        Extract tags from detail page.

        Uses the Genre definition list values (e.g. "Rap - Jazz" -> ["rap", "jazz"])
        and breadcrumb category as tags. Avoids navigation <li> items.
        """
        tags = []

        # Extract from Genre definition list
        for dt in parser.select("dt"):
            if "genre" in dt.get_text().lower():
                dd = dt.find_next_sibling("dd")
                if dd:
                    genre_text = dd.get_text().strip()
                    for part in re.split(r"\s*[-–/,]\s*", genre_text):
                        part = part.strip().lower()
                        if part and part not in tags:
                            tags.append(part)

        # Extract category from breadcrumbs
        for link in parser.select("a"):
            text = link.get_text().strip()
            cat_match = re.search(r"[Cc]at[ée]gorie\s*:\s*(.+)", text)
            if cat_match:
                cat = cat_match.group(1).strip().lower()
                if cat and cat not in tags:
                    tags.append(cat)

        return tags[:5]

    def _extract_location(self, parser: HTMLParser) -> str:
        """
        Extract location from detail page.

        Most events at Théâtre de l'Œuvre are at the theatre itself,
        but some may be at "La Mesón" (their associated bar/restaurant).
        """
        # Search for location text
        full_text = parser.soup.get_text().lower()

        if "la mesón" in full_text or "la meson" in full_text:
            # Check if the event is specifically at La Mesón
            # (some events use this as a secondary venue)
            if "théâtre de l'œuvre" not in full_text.split("la mes")[0][-100:]:
                return "theatre-de-l-oeuvre"

        return "theatre-de-l-oeuvre"

    def _generate_source_id(self, url: str) -> str:
        """Generate unique source ID from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = parsed.path.strip("/")

        # Use last path segment as ID
        segments = path.split("/")
        event_id = segments[-1] if segments else path

        return f"loeuvre:{event_id}"
