"""Parser for Shotgun (shotgun.live) events.

Shotgun is a ticketing platform for music events, concerts, and festivals.
The site uses Vercel bot protection and React Server Components, requiring
a headless browser (Playwright) to load pages. Event detail pages provide
structured JSON-LD data (schema.org MusicEvent) for reliable extraction.
"""

import json
import re
import time
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

PARIS_TZ = ZoneInfo("Europe/Paris")

# Maximum number of pages to crawl from the listing
MAX_PAGES = 3

# Maximum number of events to process per crawl
MAX_EVENTS = 50


def _get_playwright_page(url, timeout=60000):
    """
    Fetch a page using Playwright headless browser.

    Shotgun.live uses Vercel bot protection that blocks standard HTTP
    requests. Playwright renders JavaScript and passes the challenge.

    Args:
        url: URL to navigate to
        timeout: Page load timeout in milliseconds

    Returns:
        Tuple of (page HTML content, browser instance) or (None, None) on failure
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error(
            "Playwright is required for the Shotgun parser. "
            "Install it with: pip install playwright && playwright install chromium"
        )
        return None, None

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout)
        # Wait for dynamic content to render
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()
        pw.stop()
        return html, None
    except Exception as e:
        logger.error(f"Playwright failed to load {url}: {e}")
        return None, None


def _extract_event_urls_from_html(html, base_url="https://shotgun.live"):
    """
    Extract event URLs from a Shotgun listing page HTML.

    Args:
        html: HTML content of the listing page
        base_url: Base URL for resolving relative links

    Returns:
        List of absolute event URLs
    """
    parser = HTMLParser(html, base_url)
    urls = set()

    # Shotgun uses tracked links with data-slot="tracked-link"
    for link in parser.select('a[href*="/events/"]'):
        href = link.get("href", "")
        if not href:
            continue
        if href.startswith("/"):
            href = f"{base_url}{href}"
        if "/events/" in href:
            urls.add(href)

    return list(urls)


def _extract_json_ld(html):
    """
    Extract JSON-LD structured data from page HTML.

    Shotgun detail pages contain schema.org MusicEvent structured data
    with all event fields.

    Args:
        html: HTML content of the detail page

    Returns:
        List of parsed JSON-LD objects
    """
    results = []
    # Find all <script type="application/ld+json"> blocks
    pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL)

    for match in matches:
        try:
            data = json.loads(match)
            results.append(data)
        except json.JSONDecodeError:
            continue

    return results


def _parse_event_from_json_ld(json_ld, event_url, category_map):
    """
    Parse event data from a schema.org MusicEvent JSON-LD object.

    Args:
        json_ld: Parsed JSON-LD dict with @type MusicEvent
        event_url: URL of the event detail page
        category_map: Mapping of genre names to taxonomy categories

    Returns:
        Event object or None if data is insufficient
    """
    name = json_ld.get("name", "")
    if not name:
        return None

    # Parse start date
    start_date_str = json_ld.get("startDate")
    if not start_date_str:
        return None

    try:
        start_dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        # Convert to Paris timezone
        start_dt = start_dt.astimezone(PARIS_TZ)
    except (ValueError, AttributeError):
        logger.warning(f"Failed to parse date for {name}: {start_date_str}")
        return None

    # Extract description
    description = json_ld.get("description", "")
    if description and len(description) > 160:
        description = description[:157].rsplit(" ", 1)[0] + "..."

    # Extract image
    image_url = json_ld.get("image", "")

    # Extract location
    location_data = json_ld.get("location", {})
    location_name = ""
    if isinstance(location_data, dict):
        location_name = location_data.get("name", "")
        # Also check for address locality
        address = location_data.get("address", {})
        if isinstance(address, dict):
            locality = address.get("addressLocality", "")
            if locality and locality.lower() not in location_name.lower():
                location_name = (
                    f"{location_name}, {locality}" if location_name else locality
                )

    # Extract organizer as additional location context
    organizer = json_ld.get("organizer", {})
    venue_name = ""
    if isinstance(organizer, dict):
        venue_name = organizer.get("name", "")

    # Use venue name from organizer if location is just an address
    if venue_name and not any(
        c.isalpha() and not c.isdigit()
        for c in location_name.split(",")[0]
        if c.strip()
    ):
        display_location = venue_name
    elif venue_name and venue_name != location_name:
        display_location = venue_name
    else:
        display_location = location_name

    # Extract performers/tags
    tags = []
    performers = json_ld.get("performer", [])
    if isinstance(performers, list):
        for performer in performers[:5]:
            if isinstance(performer, dict):
                perf_name = performer.get("name", "")
                if perf_name:
                    tags.append(perf_name.lower())

    # Extract category from offers or event type
    category = _map_category_from_json_ld(json_ld, category_map)

    # Generate source ID from URL slug
    parsed_url = urlparse(event_url)
    path_parts = parsed_url.path.strip("/").split("/")
    slug = path_parts[-1] if path_parts else ""
    source_id = f"shotgun:{slug}"

    locations = [display_location] if display_location else []

    return Event(
        name=name,
        event_url=event_url,
        start_datetime=start_dt,
        description=description,
        image=image_url if image_url else None,
        categories=[category],
        locations=locations,
        tags=tags,
        source_id=source_id,
    )


def _map_category_from_json_ld(json_ld, category_map):
    """
    Determine event category from JSON-LD data.

    Uses the event @type and any genre information available.

    Args:
        json_ld: JSON-LD event data
        category_map: Category mapping from config

    Returns:
        Category string from standard taxonomy
    """
    event_type = json_ld.get("@type", "")

    # MusicEvent is always music
    if event_type == "MusicEvent":
        return "musique"

    # Check for other event types
    type_mapping = {
        "DanceEvent": "danse",
        "TheaterEvent": "theatre",
        "VisualArtsEvent": "art",
        "ComedyEvent": "theatre",
        "Festival": "communaute",
    }

    if event_type in type_mapping:
        return type_mapping[event_type]

    # Default for Shotgun (primarily music platform)
    return "musique"


class ShotgunParser(BaseCrawler):
    """
    Event parser for Shotgun (https://shotgun.live).

    Shotgun is a music event ticketing platform covering clubs, concerts,
    and festivals in the Aix-Marseille area. The site uses Vercel bot
    protection, requiring Playwright for page loading.

    Strategy:
    1. Load the city listing page with Playwright
    2. Extract event URLs from the rendered HTML
    3. Visit each event detail page
    4. Extract structured JSON-LD data (schema.org MusicEvent)
    5. Convert to Event objects
    """

    source_name = "Shotgun"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from Shotgun listing page.

        Since the initial page load via BaseCrawler.crawl() uses httpx
        (which is blocked by Vercel), this method re-fetches the page
        using Playwright to get the actual rendered content.

        Args:
            parser: HTMLParser (unused - page is re-fetched with Playwright)

        Returns:
            List of Event objects
        """
        events = []
        all_event_urls = set()

        # Crawl listing pages to collect event URLs
        for page_num in range(MAX_PAGES):
            page_url = self.base_url
            if page_num > 0:
                page_url = f"{self.base_url}?page={page_num}"

            logger.info(f"Loading Shotgun listing page: {page_url}")
            html, _ = _get_playwright_page(page_url)

            if not html:
                if page_num == 0:
                    logger.error("Failed to load Shotgun listing page")
                    return events
                break

            page_urls = _extract_event_urls_from_html(html)
            if not page_urls:
                logger.info(f"No more events on page {page_num + 1}")
                break

            new_urls = set(page_urls) - all_event_urls
            if not new_urls:
                logger.info(f"No new events on page {page_num + 1}")
                break

            all_event_urls.update(new_urls)
            logger.info(f"Found {len(new_urls)} new event URLs on page {page_num + 1}")

            if len(all_event_urls) >= MAX_EVENTS:
                break

            # Respect rate limiting between pages
            time.sleep(
                self.config.get("rate_limit", {}).get("delay_between_pages", 3.0)
            )

        logger.info(f"Total unique event URLs found: {len(all_event_urls)}")

        # Process each event detail page
        for event_url in list(all_event_urls)[:MAX_EVENTS]:
            try:
                event = self._parse_detail_page(event_url)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event from {event_url}: {e}")

            # Rate limiting between detail page fetches
            time.sleep(
                self.config.get("rate_limit", {}).get("delay_between_pages", 3.0)
            )

        return events

    def _parse_detail_page(self, event_url: str) -> Event | None:
        """
        Fetch and parse a Shotgun event detail page.

        Extracts the JSON-LD structured data which provides all
        event fields in a clean format.

        Args:
            event_url: URL of the event detail page

        Returns:
            Event object or None if parsing failed
        """
        logger.debug(f"Loading event detail page: {event_url}")

        html, _ = _get_playwright_page(event_url)
        if not html:
            logger.warning(f"Failed to load detail page: {event_url}")
            return None

        # Extract JSON-LD data
        json_ld_items = _extract_json_ld(html)

        # Find the MusicEvent JSON-LD
        music_event = None
        for item in json_ld_items:
            if isinstance(item, dict) and item.get("@type") in (
                "MusicEvent",
                "Event",
                "DanceEvent",
                "TheaterEvent",
                "Festival",
            ):
                music_event = item
                break

        if not music_event:
            logger.debug(f"No event JSON-LD found on: {event_url}")
            # Fall back to HTML parsing
            return self._parse_from_html(html, event_url)

        return _parse_event_from_json_ld(music_event, event_url, self.category_map)

    def _parse_from_html(self, html: str, event_url: str) -> Event | None:
        """
        Fallback: parse event from HTML when JSON-LD is not available.

        Args:
            html: HTML content of the detail page
            event_url: URL of the event detail page

        Returns:
            Event object or None if parsing failed
        """
        detail_parser = HTMLParser(html, event_url)

        # Extract title
        h1 = detail_parser.select_one("h1")
        if not h1:
            return None
        name = h1.get_text().strip()
        if not name:
            return None

        # Extract OG meta tags as fallback
        og_description = ""
        og_image = ""

        og_desc_tag = detail_parser.select_one('meta[property="og:description"]')
        if og_desc_tag:
            og_description = og_desc_tag.get("content", "")

        og_img_tag = detail_parser.select_one('meta[property="og:image"]')
        if og_img_tag:
            og_image = og_img_tag.get("content", "")

        # Try to parse date from OG description
        # Format: "Billets pour EVENT à CITY, COUNTRY – le DD mois YYYY"
        event_datetime = None
        if og_description:
            date_match = re.search(
                r"le\s+(\d{1,2})\s+(\w+)\s+(\d{4})",
                og_description.lower(),
            )
            if date_match:
                months = {
                    "janvier": 1,
                    "février": 2,
                    "mars": 3,
                    "avril": 4,
                    "mai": 5,
                    "juin": 6,
                    "juillet": 7,
                    "août": 8,
                    "septembre": 9,
                    "octobre": 10,
                    "novembre": 11,
                    "décembre": 12,
                }
                day = int(date_match.group(1))
                month = months.get(date_match.group(2))
                year = int(date_match.group(3))
                if month:
                    try:
                        event_datetime = datetime(
                            year, month, day, 20, 0, tzinfo=PARIS_TZ
                        )
                    except ValueError:
                        pass

        if not event_datetime:
            return None

        # Generate source ID
        parsed_url = urlparse(event_url)
        path_parts = parsed_url.path.strip("/").split("/")
        slug = path_parts[-1] if path_parts else ""
        source_id = f"shotgun:{slug}"

        return Event(
            name=name,
            event_url=event_url,
            start_datetime=event_datetime,
            description=og_description[:160] if og_description else "",
            image=og_image if og_image else None,
            categories=["musique"],
            locations=[],
            tags=[],
            source_id=source_id,
        )
