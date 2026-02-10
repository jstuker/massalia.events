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

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..models.venue import Venue
from ..utils.french_date import FRENCH_MONTHS, PARIS_TZ
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

# Maximum number of pages to crawl from the listing
MAX_PAGES = 3

# Maximum number of events to process per crawl
MAX_EVENTS = 50


class PlaywrightSession:
    """Manages a single Playwright browser instance for multiple page fetches.

    Reuses one Chromium process across all pages in a crawl session,
    creating a new tab (page) per URL and closing it after extraction.

    If an asyncio event loop is already running (preventing the Playwright
    sync API from working directly), the browser runs in a background thread
    with queue-based communication.

    Usage::

        with PlaywrightSession() as session:
            html1 = session.fetch_page("https://example.com/page1")
            html2 = session.fetch_page("https://example.com/page2")
    """

    def __init__(self, timeout=60000):
        self.timeout = timeout
        self._pw = None
        self._browser = None
        self._use_thread = False
        self._thread = None
        self._request_queue = None
        self._response_queue = None

    def __enter__(self):
        self._start()
        return self

    def __exit__(self, *exc):
        self._stop()
        return False

    def _start(self):
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            logger.error(
                "Playwright is required for the Shotgun parser. "
                "Install it with: pip install playwright && playwright install chromium"
            )
            raise

        try:
            self._start_direct()
        except RuntimeError as e:
            if "asyncio" in str(e).lower() or "event loop" in str(e).lower():
                logger.debug("Asyncio loop detected, running Playwright in thread")
                self._start_in_thread()
            else:
                raise

    def _start_direct(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)

    def _start_in_thread(self):
        import queue
        import threading

        self._use_thread = True
        self._request_queue = queue.Queue()
        self._response_queue = queue.Queue()
        ready_event = threading.Event()
        startup_error = [None]

        def worker():
            from playwright.sync_api import sync_playwright

            pw = sync_playwright().start()
            try:
                browser = pw.chromium.launch(headless=True)
                try:
                    ready_event.set()
                    while True:
                        msg = self._request_queue.get()
                        if msg is None:
                            break
                        url, timeout = msg
                        try:
                            page = browser.new_page()
                            try:
                                page.goto(
                                    url,
                                    wait_until="networkidle",
                                    timeout=timeout,
                                )
                                page.wait_for_timeout(2000)
                                html = page.content()
                                self._response_queue.put(html)
                            finally:
                                page.close()
                        except Exception as e:
                            logger.error(
                                f"Playwright thread: failed to load {url}: {e}"
                            )
                            self._response_queue.put(None)
                finally:
                    browser.close()
            except Exception as e:
                startup_error[0] = e
                ready_event.set()
            finally:
                pw.stop()

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()
        ready_event.wait(timeout=30)

        if startup_error[0]:
            raise startup_error[0]

    def fetch_page(self, url, timeout=None):
        """Fetch a page using the shared browser instance.

        Creates a new tab, navigates to the URL, extracts content,
        and closes the tab — keeping the browser alive for reuse.

        Args:
            url: URL to navigate to
            timeout: Page load timeout in ms (defaults to session timeout)

        Returns:
            HTML content string, or None on failure
        """
        timeout = timeout or self.timeout

        if self._use_thread:
            return self._fetch_in_thread(url, timeout)
        return self._fetch_direct(url, timeout)

    def _fetch_direct(self, url, timeout):
        try:
            page = self._browser.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=timeout)
                page.wait_for_timeout(2000)
                return page.content()
            finally:
                page.close()
        except Exception as e:
            logger.error(f"Playwright failed to load {url}: {e}")
            return None

    def _fetch_in_thread(self, url, timeout):
        try:
            self._request_queue.put((url, timeout))
            return self._response_queue.get(timeout=timeout / 1000 + 30)
        except Exception as e:
            logger.error(f"Playwright thread failed for {url}: {e}")
            return None

    def _stop(self):
        if self._use_thread:
            if self._request_queue:
                self._request_queue.put(None)
            if self._thread:
                self._thread.join(timeout=10)
        else:
            if self._browser:
                try:
                    self._browser.close()
                except Exception:
                    pass
            if self._pw:
                try:
                    self._pw.stop()
                except Exception:
                    pass


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


def _extract_venue_from_json_ld(json_ld):
    """
    Extract venue metadata from a schema.org event JSON-LD object.

    Combines location (Place) and organizer (LocalBusiness) data to
    build a complete Venue object with address, coordinates, and website.

    Args:
        json_ld: Parsed JSON-LD dict with event data

    Returns:
        Venue object or None if no venue data available
    """
    location_data = json_ld.get("location", {})
    organizer = json_ld.get("organizer", {})

    if not isinstance(location_data, dict) and not isinstance(organizer, dict):
        return None

    # Extract organizer info
    venue_name = ""
    source_url = ""
    if isinstance(organizer, dict):
        venue_name = organizer.get("name", "")
        source_url = organizer.get("url", "")

    # Extract location address details
    street_address = ""
    postal_code = ""
    city = "Marseille"
    latitude = None
    longitude = None

    if isinstance(location_data, dict):
        address = location_data.get("address", {})
        if isinstance(address, dict):
            street_address = address.get("streetAddress", "")
            postal_code = address.get("postalCode", "")
            city = address.get("addressLocality", "Marseille")

        geo = location_data.get("geo", {})
        if isinstance(geo, dict):
            lat = geo.get("latitude")
            lon = geo.get("longitude")
            if lat is not None:
                latitude = float(lat)
            if lon is not None:
                longitude = float(lon)

        # Use location name as venue name if organizer didn't provide one
        if not venue_name:
            location_name = location_data.get("name", "")
            # Strip address suffixes like "Baby Club, 13006 Marseille, France"
            if location_name and "," in location_name:
                venue_name = location_name.split(",")[0].strip()
            else:
                venue_name = location_name

    if not venue_name:
        return None

    return Venue(
        name=venue_name,
        street_address=street_address,
        postal_code=postal_code,
        city=city,
        latitude=latitude,
        longitude=longitude,
        source_url=source_url,
    )


def _parse_event_from_json_ld(json_ld, event_url, category_map):
    """
    Parse event data from a schema.org MusicEvent JSON-LD object.

    Args:
        json_ld: Parsed JSON-LD dict with @type MusicEvent
        event_url: URL of the event detail page
        category_map: Mapping of genre names to taxonomy categories

    Returns:
        Tuple of (Event, Venue) or (None, None) if data is insufficient
    """
    name = json_ld.get("name", "")
    if not name:
        return None, None

    # Parse start date
    start_date_str = json_ld.get("startDate")
    if not start_date_str:
        return None, None

    try:
        start_dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        # Convert to Paris timezone
        start_dt = start_dt.astimezone(PARIS_TZ)
    except (ValueError, AttributeError):
        logger.warning(f"Failed to parse date for {name}: {start_date_str}")
        return None, None

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

    # Extract venue metadata
    venue = _extract_venue_from_json_ld(json_ld)

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

    event = Event(
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

    return event, venue


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
    6. Collect venue metadata for location page generation
    """

    source_name = "Shotgun"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Accumulated venue data keyed by slug
        self.venues: dict[str, Venue] = {}
        # Shared Playwright browser session (set during crawl)
        self._pw_session: PlaywrightSession | None = None

    def crawl(self) -> list[Event]:
        """
        Execute crawl with a shared Playwright browser session.

        Wraps the base crawl in a PlaywrightSession context manager
        so that a single Chromium process is reused for all page fetches.
        """
        try:
            with PlaywrightSession() as session:
                self._pw_session = session
                return super().crawl()
        except ImportError:
            logger.error("Cannot crawl Shotgun: Playwright not installed")
            return []
        finally:
            self._pw_session = None

    def fetch_page(self, url: str) -> str:
        """
        Fetch page using shared Playwright browser session.

        Overrides BaseCrawler.fetch_page() which uses httpx. Shotgun.live
        returns 429 to standard HTTP clients due to Vercel's bot detection.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string, or empty string on failure
        """
        logger.info(f"Fetching with Playwright: {url}")
        if self._pw_session:
            html = self._pw_session.fetch_page(url)
            return html or ""
        logger.warning("No Playwright session available")
        return ""

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from Shotgun listing page.

        Uses the first page HTML already fetched by crawl() via fetch_page(),
        then fetches additional pages with Playwright for pagination.

        Args:
            parser: HTMLParser with first listing page content

        Returns:
            List of Event objects
        """
        events = []
        all_event_urls = set()

        # Page 1 was already fetched by BaseCrawler.crawl() -> fetch_page()
        first_page_html = str(parser.soup)
        first_page_urls = _extract_event_urls_from_html(first_page_html)

        if not first_page_urls:
            logger.info("No events found on first listing page")
            return events

        all_event_urls.update(first_page_urls)
        logger.info(f"Found {len(first_page_urls)} event URLs on page 1")

        # Fetch additional listing pages
        for page_num in range(1, MAX_PAGES):
            if len(all_event_urls) >= MAX_EVENTS:
                break

            # Respect rate limiting between pages
            time.sleep(
                self.config.get("rate_limit", {}).get("delay_between_pages", 3.0)
            )

            page_url = f"{self.base_url}?page={page_num}"
            logger.info(f"Loading Shotgun listing page: {page_url}")
            html = self._pw_session.fetch_page(page_url) if self._pw_session else None

            if not html:
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

        # Export collected venue data
        if self.venues:
            self._export_venues()

        return events

    def _export_venues(self):
        """
        Export collected venue metadata to a JSON file.

        Writes accumulated venue data to crawler/data/venues-shotgun.json
        for use in generating location pages.
        """
        import os
        from pathlib import Path

        data_dir = Path(__file__).parent.parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        output_path = data_dir / "venues-shotgun.json"

        venues_data = {
            slug: venue.to_dict() for slug, venue in sorted(self.venues.items())
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(venues_data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Exported {len(self.venues)} venues to {output_path}"
        )

    def _parse_detail_page(self, event_url: str) -> Event | None:
        """
        Fetch and parse a Shotgun event detail page.

        Extracts the JSON-LD structured data which provides all
        event fields in a clean format. Also collects venue metadata.

        Args:
            event_url: URL of the event detail page

        Returns:
            Event object or None if parsing failed
        """
        logger.debug(f"Loading event detail page: {event_url}")

        html = self._pw_session.fetch_page(event_url) if self._pw_session else None
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

        event, venue = _parse_event_from_json_ld(
            music_event, event_url, self.category_map
        )

        # Collect venue metadata
        if venue and venue.slug and venue.slug not in self.venues:
            self.venues[venue.slug] = venue
            logger.debug(f"Collected venue: {venue.name} ({venue.slug})")

        return event

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
                day = int(date_match.group(1))
                month = FRENCH_MONTHS.get(date_match.group(2))
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
