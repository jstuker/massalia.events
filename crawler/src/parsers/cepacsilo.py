"""Parser for Le Cepac Silo events (cepacsilo-marseille.fr)."""

import json
import re
from datetime import datetime
from urllib.parse import urljoin

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import PARIS_TZ
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

# Maximum number of listing pages to crawl
MAX_PAGES = 10


def _extract_event_urls_from_html(html: str, base_url: str = "") -> list[str]:
    """
    Extract event detail page URLs from a listing page.

    Args:
        html: HTML content of the listing page
        base_url: Base URL for resolving relative links

    Returns:
        List of unique event detail URLs
    """
    parser = HTMLParser(html, base_url)
    urls = set()

    # Event detail links follow pattern /evenement/{slug}/
    for link in parser.select("a[href*='/evenement/']"):
        href = link.get("href", "")
        if not href:
            continue

        # Resolve relative URLs
        if href.startswith("/"):
            href = urljoin(base_url, href)

        # Only include event detail pages (singular /evenement/, not /evenements/)
        if "/evenement/" in href and "/evenements/" not in href:
            urls.add(href)

    return sorted(urls)


def _extract_json_ld(html: str) -> list[dict]:
    """
    Extract JSON-LD structured data from HTML.

    Args:
        html: HTML content

    Returns:
        List of parsed JSON-LD objects
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                results.append(data)
            elif isinstance(data, list):
                results.extend(data)
        except (json.JSONDecodeError, TypeError):
            continue

    return results


def _parse_event_dates_from_html(html: str) -> list[datetime]:
    """
    Extract individual event dates from the HTML listing elements.

    Le Cepac Silo shows multiple dates in list items like:
    "samedi 14 février 2026 · 18h00"

    Args:
        html: HTML content of the detail page

    Returns:
        List of datetime objects for each showtime
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    dates = []

    # French month mapping
    months = {
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

    # Pattern: "samedi 14 février 2026 · 18h00" or "samedi 14 février 2026 · 18h"
    date_pattern = re.compile(
        r"(\d{1,2})\s+(\w+)\s+(\d{4})\s*[·\-]\s*(\d{1,2})h(\d{2})?",
        re.IGNORECASE,
    )

    # Remove booking modals for related events so their dates aren't picked up.
    # Each event detail page includes modal-booking-event popups for the main
    # event AND for "Vous aimerez aussi" (related) events.  The main event's
    # own dates are shown separately in .bl-he__list-sessions in the article.
    for modal in soup.select(".modal-booking-event"):
        modal.decompose()

    # Also remove card-event / bl-evc__list sections (related events carousel)
    for elem in soup.select(".bl-evc__list, .card-event"):
        elem.decompose()

    # Search in li elements (primary location for dates)
    for li in soup.find_all("li"):
        text = li.get_text().strip()
        match = date_pattern.search(text)
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3))
            hour = int(match.group(4))
            minute = int(match.group(5)) if match.group(5) else 0

            month = months.get(month_name)
            if month:
                try:
                    dt = datetime(year, month, day, hour, minute, tzinfo=PARIS_TZ)
                    dates.append(dt)
                except ValueError:
                    continue

    # Fallback: search entire text for date patterns if no li matches
    if not dates:
        text = soup.get_text()
        for match in date_pattern.finditer(text):
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3))
            hour = int(match.group(4))
            minute = int(match.group(5)) if match.group(5) else 0

            month = months.get(month_name)
            if month:
                try:
                    dt = datetime(year, month, day, hour, minute, tzinfo=PARIS_TZ)
                    dates.append(dt)
                except ValueError:
                    continue

    return dates


def _parse_event_from_json_ld(
    json_ld: dict, event_url: str, category_map: dict
) -> Event | None:
    """
    Parse an Event from JSON-LD structured data.

    Note: Le Cepac Silo JSON-LD has startDate as the first showtime and
    endDate as the last showtime, so startDate is used for the event date.
    For multi-date events, we rely on HTML date parsing instead.

    Args:
        json_ld: JSON-LD Event dict
        event_url: URL of the event page
        category_map: Category mapping dict

    Returns:
        Event object or None if required fields are missing
    """
    name = json_ld.get("name", "").strip()
    if not name:
        return None

    # Parse start date
    start_date_str = json_ld.get("startDate", "")
    if not start_date_str:
        return None

    start_datetime = _parse_iso_datetime(start_date_str)
    if not start_datetime:
        return None

    # Extract description
    description = json_ld.get("description", "").strip()
    # The site uses a placeholder description in JSON-LD; ignore it
    if "Kira and Morrison" in description or "Snickertown" in description:
        description = ""
    if len(description) > 160:
        description = description[:157] + "..."

    # Extract image (can be a string URL, a list of URLs, or a dict with "url")
    raw_image = json_ld.get("image", "")
    if isinstance(raw_image, list):
        image = raw_image[0] if raw_image else ""
    elif isinstance(raw_image, dict):
        image = raw_image.get("url", "")
    else:
        image = raw_image

    # Extract category from event type tag on the page
    category = "communaute"  # Default

    # Generate source ID from URL slug
    source_id = _generate_source_id(event_url)

    # Location is always Le Cepac Silo
    locations = ["le-cepac-silo-marseille"]

    # Extract performer as tag
    tags = []
    performer = json_ld.get("performer")
    if performer:
        if isinstance(performer, dict):
            perf_name = performer.get("name", "").strip().lower()
            if perf_name and perf_name != name.lower():
                tags.append(perf_name)
        elif isinstance(performer, list):
            for p in performer:
                perf_name = p.get("name", "").strip().lower()
                if perf_name:
                    tags.append(perf_name)

    return Event(
        name=name,
        event_url=event_url,
        start_datetime=start_datetime,
        description=description,
        image=image if image else None,
        categories=[category],
        locations=locations,
        tags=tags[:5],
        source_id=source_id,
    )


def _parse_iso_datetime(date_str: str) -> datetime | None:
    """
    Parse an ISO datetime string to a timezone-aware datetime in Paris TZ.

    Args:
        date_str: ISO format datetime string

    Returns:
        datetime in Paris timezone, or None on failure
    """
    try:
        # Handle .000000Z format
        date_str = date_str.replace(".000000Z", "+00:00").replace("Z", "+00:00")
        dt = datetime.fromisoformat(date_str)
        return dt.astimezone(PARIS_TZ)
    except (ValueError, TypeError):
        return None


def _generate_source_id(url: str) -> str:
    """Generate a unique source ID from an event URL."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path.strip("/")
    segments = path.split("/")
    event_slug = segments[-1] if segments else path
    return f"cepacsilo:{event_slug}"


class CepacSiloParser(BaseCrawler):
    """
    Event parser for Le Cepac Silo (cepacsilo-marseille.fr).

    Le Cepac Silo is a 2,050-seat venue in a converted grain silo
    on the port of Marseille, hosting concerts, comedy, theatre,
    and dance events.

    This parser:
    1. Crawls paginated listing pages (/evenements/page/N/)
    2. Extracts event detail URLs
    3. Visits each detail page to extract JSON-LD + HTML data
    4. Creates separate Event objects for each showtime of multi-date events
    """

    source_name = "Le Cepac Silo"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from Le Cepac Silo listing pages.

        Args:
            parser: HTMLParser with the first listing page content

        Returns:
            List of Event objects
        """
        events = []

        # Collect event URLs from all listing pages
        all_event_urls = self._collect_all_event_urls(parser)

        if not all_event_urls:
            logger.warning("No event URLs found on Le Cepac Silo")
            return events

        logger.info(f"Found {len(all_event_urls)} event URLs on Le Cepac Silo")

        # Batch-fetch all detail pages concurrently
        pages = self.fetch_pages(all_event_urls)

        for event_url in all_event_urls:
            html = pages.get(event_url, "")
            if not html:
                continue
            try:
                page_events = self._parse_detail_page(event_url, html=html)
                events.extend(page_events)
            except Exception as e:
                logger.warning(f"Failed to parse event from {event_url}: {e}")

        logger.info(
            f"Extracted {len(events)} events (including multi-date) from Le Cepac Silo"
        )
        return events

    def _collect_all_event_urls(self, first_page_parser: HTMLParser) -> list[str]:
        """
        Collect event URLs from all listing pages with pagination.

        Args:
            first_page_parser: HTMLParser with first page content

        Returns:
            List of unique event detail URLs
        """
        all_urls = set()

        # Extract from first page
        first_page_urls = _extract_event_urls_from_html(
            str(first_page_parser.soup), self.base_url
        )
        all_urls.update(first_page_urls)

        # Check for pagination and fetch subsequent pages
        for page_num in range(2, MAX_PAGES + 1):
            page_url = f"{self.base_url.rstrip('/')}/page/{page_num}/"
            html = self.fetch_page(page_url)
            if not html:
                break

            page_urls = _extract_event_urls_from_html(html, self.base_url)
            if not page_urls:
                break

            all_urls.update(page_urls)
            logger.debug(
                f"Page {page_num}: found {len(page_urls)} events "
                f"(total: {len(all_urls)})"
            )

        return sorted(all_urls)

    def _parse_detail_page(
        self, event_url: str, html: str | None = None
    ) -> list[Event]:
        """
        Parse an event detail page.

        For events with multiple showtimes, creates a separate Event
        for each future date.

        Args:
            event_url: URL of the event detail page
            html: Pre-fetched HTML content (fetched if not provided)

        Returns:
            List of Event objects (one per showtime)
        """
        if html is None:
            html = self.fetch_page(event_url)
        if not html:
            logger.warning(f"Failed to fetch detail page: {event_url}")
            return []

        # Extract JSON-LD for base event info
        json_ld_list = _extract_json_ld(html)
        event_json_ld = None
        for item in json_ld_list:
            if item.get("@type") == "Event":
                event_json_ld = item
                break

        if not event_json_ld:
            logger.debug(f"No Event JSON-LD found on: {event_url}")
            return []

        # Parse base event from JSON-LD
        base_event = _parse_event_from_json_ld(
            event_json_ld, event_url, self.category_map
        )
        if not base_event:
            logger.debug(f"Could not parse base event from JSON-LD: {event_url}")
            return []

        # Extract category from HTML (more reliable than JSON-LD on this site)
        category = self._extract_category_from_html(html)
        if category:
            base_event.categories = [category]

        # Extract description from HTML if JSON-LD had placeholder
        if not base_event.description:
            base_event.description = self._extract_description_from_html(html)

        # Parse all individual showtimes from HTML
        all_dates = _parse_event_dates_from_html(html)

        if not all_dates:
            # Use JSON-LD startDate as single event
            return [base_event]

        # Filter to unique dates and create one event per showtime
        now = datetime.now(PARIS_TZ)
        events = []
        seen_dates = set()

        for dt in all_dates:
            # Skip past dates
            if dt < now:
                continue

            # Deduplicate same datetime
            dt_key = dt.isoformat()
            if dt_key in seen_dates:
                continue
            seen_dates.add(dt_key)

            # Create event for this showtime
            event = Event(
                name=base_event.name,
                event_url=event_url,
                start_datetime=dt,
                description=base_event.description,
                image=base_event.image,
                categories=list(base_event.categories),
                locations=list(base_event.locations),
                tags=list(base_event.tags),
                source_id=f"{_generate_source_id(event_url)}:{dt.strftime('%Y%m%d-%H%M')}",
            )
            events.append(event)

        # If all dates were in the past, still return the base event
        # if its JSON-LD date is in the future
        if not events and base_event.start_datetime >= now:
            return [base_event]

        return events

    def _extract_category_from_html(self, html: str) -> str:
        """
        Extract event category from HTML elements.

        Looks for the .card-event__tag or .term class.
        """
        detail_parser = HTMLParser(html, self.base_url)

        # Try specific category selectors used by Cepac Silo
        for selector in [".card-event__tag", ".term", ".content-header .term"]:
            elem = detail_parser.select_one(selector)
            if elem:
                category_text = elem.get_text().strip()
                if category_text:
                    return self.map_category(category_text)

        return ""

    def _extract_description_from_html(self, html: str) -> str:
        """Extract event description from HTML content."""
        detail_parser = HTMLParser(html, self.base_url)

        # Try selectors commonly used on the Cepac Silo site
        for selector in [".about p", ".about", ".description", "article p"]:
            elem = detail_parser.select_one(selector)
            if elem:
                text = elem.get_text().strip()
                if len(text) > 20:
                    return HTMLParser.truncate(text, 160)

        return ""
