"""Parser for Biennale des écritures du réel (Théâtre La Cité) events."""

import re
from datetime import datetime
from urllib.parse import urlparse

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import FRENCH_MONTHS, PARIS_TZ
from ..utils.parser import HTMLParser
from ..utils.sanitize import sanitize_description

logger = get_logger(__name__)

# Bullet separator used in date/location strings on the site
BULLET = "\u2022"


def _extract_event_urls(html: str, base_url: str) -> list[str]:
    """
    Extract event detail page URLs from the listing page.

    Args:
        html: HTML content of the listing page
        base_url: Base URL for resolving relative links

    Returns:
        List of unique absolute event URLs
    """
    parser = HTMLParser(html, base_url)
    urls = set()

    for li in parser.select("section.eventsTiles ul li"):
        link = li.find("a")
        if not link:
            continue
        href = link.get("href", "")
        if href and "/agenda/" in href:
            urls.add(
                href if href.startswith("http") else f"{base_url.rstrip('/')}{href}"
            )

    return sorted(urls)


def _parse_sidebar_dates(html: str) -> list[dict]:
    """
    Extract individual date/time entries from the detail page sidebar.

    The sidebar contains entries like:
        -> jeu. 19 mars . 19:00
        -> ven. 20 mars . 21:00

    Args:
        html: HTML content of the detail page

    Returns:
        List of dicts with 'date' (datetime) and optional 'time' (str HH:MM)
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results = []

    sidebar = soup.select_one("aside#textSide")
    if not sidebar:
        return results

    for li in sidebar.select(".datesAndPlaces ul li p"):
        text = li.get_text(strip=True)
        if not text:
            continue

        # Clean arrow prefix and normalize
        text = text.lstrip("->").lstrip("\u2192").strip()

        # Pattern: "jeu. 19 mars . 19:00" or "jeu. 19 mars • 19:00"
        # Also handles "mer. 1 avril . 14:30"
        date_match = re.search(
            r"(\d{1,2})\s+(" + "|".join(FRENCH_MONTHS.keys()) + r")(?:\s+(\d{4}))?",
            text,
            re.IGNORECASE,
        )
        if not date_match:
            continue

        day = int(date_match.group(1))
        month = FRENCH_MONTHS.get(date_match.group(2).lower())
        year = int(date_match.group(3)) if date_match.group(3) else None

        # Extract time: "19:00" or "14:30"
        time_match = re.search(r"(\d{1,2}):(\d{2})", text)
        hour, minute = (0, 0)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))

        if month:
            results.append(
                {
                    "day": day,
                    "month": month,
                    "year": year,
                    "hour": hour,
                    "minute": minute,
                }
            )

    return results


def _parse_header_date(text: str) -> list[dict]:
    """
    Parse date info from the header's p.dates element.

    Formats:
        "2 avril 2026 • 14:30"       -> single date with time
        "19 • 20 mars 2026"           -> date range same month
        "10 avril • 3 mai 2026"       -> date range spanning months

    Args:
        text: Date text from header

    Returns:
        List of dicts with day, month, year, hour, minute
    """
    text = text.strip()
    results = []

    # Try: "DD month YYYY • HH:MM" (single date with time)
    single_match = re.match(
        r"(\d{1,2})\s+("
        + "|".join(FRENCH_MONTHS.keys())
        + r")\s+(\d{4})\s*"
        + BULLET
        + r"\s*(\d{1,2}):(\d{2})",
        text,
        re.IGNORECASE,
    )
    if single_match:
        results.append(
            {
                "day": int(single_match.group(1)),
                "month": FRENCH_MONTHS[single_match.group(2).lower()],
                "year": int(single_match.group(3)),
                "hour": int(single_match.group(4)),
                "minute": int(single_match.group(5)),
            }
        )
        return results

    # Try: "DD month YYYY" (single date, no time)
    single_no_time = re.match(
        r"(\d{1,2})\s+(" + "|".join(FRENCH_MONTHS.keys()) + r")\s+(\d{4})$",
        text.strip(),
        re.IGNORECASE,
    )
    if single_no_time:
        results.append(
            {
                "day": int(single_no_time.group(1)),
                "month": FRENCH_MONTHS[single_no_time.group(2).lower()],
                "year": int(single_no_time.group(3)),
                "hour": 0,
                "minute": 0,
            }
        )
        return results

    # Try: "DD • DD month YYYY" (range same month)
    range_same = re.match(
        r"(\d{1,2})\s*"
        + BULLET
        + r"\s*(\d{1,2})\s+("
        + "|".join(FRENCH_MONTHS.keys())
        + r")\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if range_same:
        month = FRENCH_MONTHS[range_same.group(3).lower()]
        year = int(range_same.group(4))
        for day in range(int(range_same.group(1)), int(range_same.group(2)) + 1):
            results.append(
                {
                    "day": day,
                    "month": month,
                    "year": year,
                    "hour": 0,
                    "minute": 0,
                }
            )
        return results

    # Try: "DD month • DD month YYYY" (range spanning months)
    range_cross = re.match(
        r"(\d{1,2})\s+("
        + "|".join(FRENCH_MONTHS.keys())
        + r")\s*"
        + BULLET
        + r"\s*(\d{1,2})\s+("
        + "|".join(FRENCH_MONTHS.keys())
        + r")\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if range_cross:
        # For cross-month ranges, just return start and end dates
        # (sidebar dates will have the precise individual dates)
        results.append(
            {
                "day": int(range_cross.group(1)),
                "month": FRENCH_MONTHS[range_cross.group(2).lower()],
                "year": int(range_cross.group(5)),
                "hour": 0,
                "minute": 0,
            }
        )
        results.append(
            {
                "day": int(range_cross.group(3)),
                "month": FRENCH_MONTHS[range_cross.group(4).lower()],
                "year": int(range_cross.group(5)),
                "hour": 0,
                "minute": 0,
            }
        )
        return results

    return results


def _build_datetime(entry: dict) -> datetime | None:
    """Build a timezone-aware datetime from a parsed date dict."""
    try:
        return datetime(
            entry["year"],
            entry["month"],
            entry["day"],
            entry.get("hour", 0),
            entry.get("minute", 0),
            tzinfo=PARIS_TZ,
        )
    except (ValueError, TypeError):
        return None


class EcrituresDuReelParser(BaseCrawler):
    """
    Parser for Biennale des écritures du réel events.

    The Biennale is programmed by Théâtre La Cité and takes place
    at various venues across Marseille. Events include theatre,
    film, lectures, concerts, and performances.

    This parser:
    1. Extracts event URLs from the biennale programmation page
    2. Fetches each detail page
    3. Parses dates from sidebar (preferred) or header
    4. Creates separate Event objects for each showtime
    """

    source_name = "Biennale des écritures du réel"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """Parse events from the biennale programmation page."""
        events = []

        event_urls = _extract_event_urls(str(parser.soup), self.base_url)
        if not event_urls:
            logger.warning("No event URLs found on Biennale programmation page")
            return events

        logger.info(f"Found {len(event_urls)} event URLs on Biennale programmation")

        pages = self.fetch_pages(event_urls)

        for url in event_urls:
            html = pages.get(url, "")
            if not html:
                continue
            try:
                page_events = self._parse_detail_page(url, html)
                events.extend(page_events)
            except Exception as e:
                logger.warning(f"Failed to parse event from {url}: {e}")

        logger.info(
            f"Extracted {len(events)} events from Biennale des écritures du réel"
        )
        return events

    def _parse_detail_page(self, url: str, html: str) -> list[Event]:
        """Parse a single event detail page into one or more Events."""
        detail = HTMLParser(html, url)

        # Extract title
        name = self._extract_name(detail)
        if not name:
            logger.debug(f"No title found on {url}")
            return []

        # Extract category from tags
        category = self._extract_category(detail)

        # Extract description
        description = self._extract_description(detail)

        # Extract image
        image_url = self._extract_image(detail)

        # Extract venue
        venue_name = self._extract_venue(detail)

        # Extract tags (artist/author names)
        tags = self._extract_tags(detail)

        # Generate source ID base from URL slug
        source_id_base = _generate_source_id(url)

        # Parse showtimes: prefer sidebar dates, fall back to header dates
        showtimes = _parse_sidebar_dates(html)
        header_dates = []

        if not showtimes:
            # Fall back to header date
            dates_elem = detail.select_one("header.textHead p.dates")
            if dates_elem:
                dates_text = dates_elem.get_text(strip=True)
                header_dates = _parse_header_date(dates_text)

        # Infer year for sidebar dates that lack it
        if showtimes:
            # Get year from header date text
            dates_elem = detail.select_one("header.textHead p.dates")
            header_text = dates_elem.get_text(strip=True) if dates_elem else ""
            year_match = re.search(r"(\d{4})", header_text)
            default_year = (
                int(year_match.group(1)) if year_match else datetime.now(PARIS_TZ).year
            )

            for st in showtimes:
                if st.get("year") is None:
                    st["year"] = default_year

        date_entries = showtimes or header_dates
        if not date_entries:
            logger.debug(f"No dates found for: {name} on {url}")
            return []

        # Build events for each showtime
        now = datetime.now(PARIS_TZ)
        events = []
        location = self.map_location(venue_name or "Théâtre La Cité")

        for entry in date_entries:
            dt = _build_datetime(entry)
            if not dt or dt < now:
                continue

            event = Event(
                name=name,
                event_url=url,
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
        """Extract event title from detail page."""
        title_elem = parser.select_one("header.textHead h1.pageTitle")
        if title_elem:
            # h1 may contain <br> tags; use get_text with separator
            return " ".join(title_elem.get_text(separator=" ").split())

        # Fallback to any h1
        h1 = parser.select_one("h1")
        if h1:
            return " ".join(h1.get_text(separator=" ").split())

        return ""

    def _extract_category(self, parser: HTMLParser) -> str:
        """Extract and map event category."""
        # From detail page: header.textHead p.subtitle span.type
        type_elem = parser.select_one("header.textHead p.subtitle span.type")
        if type_elem:
            raw = type_elem.get_text(strip=True).rstrip(" •").strip()
            if raw:
                return self.map_category(raw)

        # From listing-style tags
        tags_elem = parser.select_one("figure .tags p")
        if tags_elem:
            raw = tags_elem.get_text(strip=True)
            if raw:
                # May be comma-separated; take first
                first = raw.split(",")[0].strip()
                return self.map_category(first)

        return "theatre"

    def _extract_description(self, parser: HTMLParser) -> str:
        """Extract event description from the main content area."""
        # Description is in article.text, after header.textHead
        article = parser.select_one("section.grid-2 > article.text")
        if article:
            # Get paragraphs that are not inside the header
            header = article.find("header")
            for p in article.find_all("p"):
                # Skip paragraphs inside header
                if header and p.find_parent("header"):
                    continue
                text = sanitize_description(p.get_text())
                if len(text) > 50:
                    return HTMLParser.truncate(text, 160)

        # Fallback: meta description
        meta = parser.select_one('meta[name="description"]')
        if meta:
            content = meta.get("content", "")
            if content:
                return HTMLParser.truncate(sanitize_description(str(content)), 160)

        return ""

    def _extract_image(self, parser: HTMLParser) -> str | None:
        """Extract main event image."""
        # Try header image
        header_img = parser.select_one("header.header figure img")
        if header_img:
            src = header_img.get("src", "")
            if src:
                return src if str(src).startswith("http") else None

        # Try og:image
        og = parser.select_one('meta[property="og:image"]')
        if og:
            content = og.get("content", "")
            if content:
                return str(content)

        return None

    def _extract_venue(self, parser: HTMLParser) -> str | None:
        """Extract venue name from sidebar."""
        venue_elem = parser.select_one("aside#textSide h2.location")
        if venue_elem:
            # Remove nested spans (like additionalInfos with address)
            for span in venue_elem.find_all("span"):
                span.decompose()
            # Remove SVG elements
            for svg in venue_elem.find_all("svg"):
                svg.decompose()
            text = venue_elem.get_text(strip=True)
            if text:
                return text
        return None

    def _extract_tags(self, parser: HTMLParser) -> list[str]:
        """Extract artist/author tags from subtitle."""
        subtitle = parser.select_one("header.textHead p.subtitle")
        if not subtitle:
            return []

        # Get text after span.type (e.g. "de Nicolas Lambert")
        type_span = subtitle.find("span", class_="type")
        if type_span:
            type_span.extract()

        text = subtitle.get_text(strip=True)
        # Remove common prefixes
        text = re.sub(r"^(de|du|d'|par)\s+", "", text, flags=re.IGNORECASE)
        if text and len(text) < 100:
            return [text.lower()]

        return []


def _generate_source_id(url: str) -> str:
    """Generate a source ID base from event URL."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    segments = path.split("/")
    slug = segments[-1] if segments else path
    return f"ecrituresdureel:{slug}"
