"""Parser for Agenda Culturel (13.agendaculturel.fr) events.

Agenda Culturel is a cultural events aggregator covering concerts, theatre,
dance, exhibitions, and festivals in the Bouches-du-Rhône department.
The site uses Cloudflare Turnstile protection, requiring a non-headless
Playwright browser to load pages. Event listing pages contain schema.org
microdata, and detail pages provide JSON-LD structured data.
"""

import base64
import json
import re
import time
from datetime import datetime
from urllib.parse import urlparse

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import PARIS_TZ
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

# Maximum number of events to process per crawl
MAX_EVENTS = 60

# Category listing pages to crawl (skip the root page)
CATEGORY_LISTING_URLS = [
    "https://13.agendaculturel.fr/concert/",
    "https://13.agendaculturel.fr/theatre/",
    "https://13.agendaculturel.fr/danse/",
    "https://13.agendaculturel.fr/arts-du-spectacle/",
    "https://13.agendaculturel.fr/exposition/",
]

# Event URL path prefixes that indicate actual event pages
EVENT_PATH_PREFIXES = (
    "/concert/",
    "/theatre/",
    "/danse/",
    "/exposition/",
    "/festival/",
    "/humour/",
    "/cirque/",
    "/opera/",
    "/jeune-public/",
    "/arts-du-spectacle/",
    "/cafe-theatre/",
    "/cinema/",
    "/conference/",
    "/salon/",
)

# Schema.org event types to our category taxonomy
SCHEMA_TYPE_MAP = {
    "MusicEvent": "musique",
    "TheaterEvent": "theatre",
    "DanceEvent": "danse",
    "VisualArtsEvent": "art",
    "ExhibitionEvent": "art",
    "Festival": "communaute",
    "ChildrensEvent": "theatre",
    "ComedyEvent": "theatre",
    "Event": "communaute",
}

# URL path prefix to category mapping
PATH_CATEGORY_MAP = {
    "concert": "musique",
    "theatre": "theatre",
    "danse": "danse",
    "exposition": "art",
    "festival": "communaute",
    "humour": "theatre",
    "cirque": "theatre",
    "opera": "musique",
    "jeune-public": "theatre",
    "arts-du-spectacle": "theatre",
    "cafe-theatre": "theatre",
    "cinema": "art",
    "conference": "communaute",
    "salon": "communaute",
}


def _dismiss_cookie_banner(page):
    """
    Dismiss the cookie consent banner if present.

    The site uses FundingChoices (Google Consent) which shows a consent
    dialog with an "Autoriser" (Allow) button. Clicking it prevents the
    banner from blocking interaction on subsequent page loads.
    """
    try:
        consent_btn = page.locator("button.fc-cta-consent.fc-primary-button")
        if consent_btn.is_visible(timeout=2000):
            consent_btn.click()
            logger.debug("Cookie consent banner dismissed")
            page.wait_for_timeout(1000)
    except Exception:
        # Banner not present or already dismissed — not an error
        pass


def _extract_page_image(page):
    """
    Extract the main event image from a loaded Playwright page.

    Tries three strategies in order:
    1. JS fetch() of the og:image URL (works when same-origin)
    2. Canvas capture of the largest rendered <img> (works when no CORS)
    3. Playwright element screenshot (always works, captures rendered pixels)

    Args:
        page: Playwright page with a loaded detail page

    Returns:
        Tuple of (image_bytes, image_url), or (None, None) on failure
    """
    try:
        # Get og:image URL from meta tag
        image_url = page.evaluate(
            """() => {
            const meta = document.querySelector('meta[property="og:image"]');
            return meta ? meta.content : null;
        }"""
        )

        if not image_url:
            logger.debug("No og:image meta tag found on page")
            return None, None

        # Strategy 1: download via browser's fetch (has cookies/session)
        image_b64 = page.evaluate(
            """async (url) => {
            try {
                const resp = await fetch(url);
                if (!resp.ok) return null;
                const buf = await resp.arrayBuffer();
                const bytes = new Uint8Array(buf);
                let binary = '';
                const chunkSize = 8192;
                for (let i = 0; i < bytes.length; i += chunkSize) {
                    const chunk = bytes.subarray(i, Math.min(i + chunkSize, bytes.length));
                    binary += String.fromCharCode.apply(null, chunk);
                }
                return btoa(binary);
            } catch {
                return null;
            }
        }""",
            image_url,
        )

        if image_b64:
            logger.debug(f"Extracted image via JS fetch: {image_url}")
            return base64.b64decode(image_b64), image_url

        logger.debug("JS fetch failed for og:image, trying canvas capture")

        # Strategy 2: capture from rendered <img> via canvas
        image_b64 = page.evaluate(
            """() => {
            const imgs = document.querySelectorAll('img');
            let bestImg = null;
            let bestArea = 0;
            for (const img of imgs) {
                if (img.complete && img.naturalWidth > 100) {
                    const area = img.naturalWidth * img.naturalHeight;
                    if (area > bestArea) {
                        bestArea = area;
                        bestImg = img;
                    }
                }
            }
            if (!bestImg) return null;
            try {
                const canvas = document.createElement('canvas');
                canvas.width = bestImg.naturalWidth;
                canvas.height = bestImg.naturalHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(bestImg, 0, 0);
                return canvas.toDataURL('image/png').split(',')[1];
            } catch {
                return null;
            }
        }"""
        )

        if image_b64:
            logger.debug(f"Extracted image via canvas capture: {image_url}")
            return base64.b64decode(image_b64), image_url

        logger.debug("Canvas capture failed (likely CORS), trying element screenshot")

        # Strategy 3: Playwright element screenshot (bypasses CORS entirely)
        # Find the largest visible image and take a screenshot of it
        best_img = _screenshot_best_image(page)
        if best_img:
            logger.debug(f"Extracted image via element screenshot: {image_url}")
            return best_img, image_url

        logger.debug("All image extraction strategies failed")

    except Exception as e:
        logger.warning(f"Failed to extract image from page: {e}")

    return None, None


def _screenshot_best_image(page):
    """
    Take a Playwright screenshot of the largest visible image element.

    This bypasses CORS restrictions since it captures rendered pixels
    at the browser level, not via JavaScript canvas.

    Args:
        page: Playwright page with loaded content

    Returns:
        PNG bytes of the image, or None on failure
    """
    try:
        # Find the best image candidate using JS, return its index
        best_index = page.evaluate(
            """() => {
            const imgs = [...document.querySelectorAll('img')];
            let bestIdx = -1;
            let bestArea = 0;
            for (let i = 0; i < imgs.length; i++) {
                const img = imgs[i];
                const rect = img.getBoundingClientRect();
                if (img.complete && rect.width > 100 && rect.height > 100) {
                    const area = rect.width * rect.height;
                    if (area > bestArea) {
                        bestArea = area;
                        bestIdx = i;
                    }
                }
            }
            return bestIdx;
        }"""
        )

        if best_index < 0:
            return None

        img_locator = page.locator("img").nth(best_index)
        if not img_locator.is_visible():
            return None

        screenshot_bytes = img_locator.screenshot(type="png")
        if screenshot_bytes and len(screenshot_bytes) > 500:
            return screenshot_bytes

    except Exception as e:
        logger.debug(f"Element screenshot failed: {e}")

    return None


def _is_cloudflare_challenge(html):
    """Check if HTML content is a Cloudflare challenge page."""
    return "Verify you are human" in html or "Just a moment" in html


class CloudflarePlaywrightSession:
    """Manages a single non-headless Playwright browser for Cloudflare-protected sites.

    Reuses one Chromium process and browser context across all pages in a crawl
    session. The shared context preserves Cloudflare Turnstile cookies, so the
    challenge only needs to be solved once (8s wait on the first page, 1s on
    subsequent pages). The cookie consent banner is dismissed once per session.

    If an asyncio event loop is already running, the browser runs in a
    background thread with queue-based communication.

    Usage::

        with CloudflarePlaywrightSession() as session:
            html1, _, _ = session.fetch_page("https://example.com/listing")
            html2, img, url = session.fetch_page("https://example.com/detail", extract_image=True)
    """

    FIRST_PAGE_WAIT = 8000
    SUBSEQUENT_PAGE_WAIT = 1000

    def __init__(self, timeout=60000):
        self.timeout = timeout
        self._pw = None
        self._browser = None
        self._context = None
        self._use_thread = False
        self._thread = None
        self._request_queue = None
        self._response_queue = None
        self._challenge_passed = False
        self._banner_dismissed = False

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
                "Playwright is required for the Agenda Culturel parser. "
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
        self._browser = self._pw.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-position=-9999,-9999",
            ],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
        )
        self._context.add_init_script(
            'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        )

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

            challenge_passed = False
            banner_dismissed = False

            pw = sync_playwright().start()
            try:
                browser = pw.chromium.launch(
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--window-position=-9999,-9999",
                    ],
                )
                try:
                    context = browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent=(
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        locale="fr-FR",
                    )
                    context.add_init_script(
                        'Object.defineProperty(navigator, "webdriver", '
                        "{get: () => undefined})"
                    )
                    ready_event.set()

                    while True:
                        msg = self._request_queue.get()
                        if msg is None:
                            break
                        url, timeout, extract_image = msg
                        try:
                            page = context.new_page()
                            try:
                                page.goto(
                                    url,
                                    wait_until="domcontentloaded",
                                    timeout=timeout,
                                )
                                if not challenge_passed:
                                    page.wait_for_timeout(
                                        CloudflarePlaywrightSession.FIRST_PAGE_WAIT
                                    )
                                else:
                                    page.wait_for_timeout(
                                        CloudflarePlaywrightSession.SUBSEQUENT_PAGE_WAIT
                                    )

                                html = page.content()
                                if _is_cloudflare_challenge(html):
                                    logger.warning(
                                        "Cloudflare challenge detected, "
                                        "waiting longer..."
                                    )
                                    page.wait_for_timeout(10000)
                                    html = page.content()

                                if not _is_cloudflare_challenge(html):
                                    challenge_passed = True

                                if not banner_dismissed:
                                    _dismiss_cookie_banner(page)
                                    banner_dismissed = True

                                image_bytes = None
                                image_url = None
                                if extract_image:
                                    image_bytes, image_url = _extract_page_image(page)

                                self._response_queue.put((html, image_bytes, image_url))
                            finally:
                                page.close()
                        except Exception as e:
                            logger.error(
                                f"Playwright thread: failed to load {url}: {e}"
                            )
                            self._response_queue.put((None, None, None))
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

    def fetch_page(self, url, extract_image=False):
        """Fetch a page using the shared browser context.

        Creates a new tab, navigates to the URL, waits for Cloudflare
        challenge (full wait on first page, brief wait thereafter),
        extracts content, and closes the tab.

        Args:
            url: URL to navigate to
            extract_image: Whether to extract the page's main image

        Returns:
            Tuple of (html, image_bytes, image_url). image_bytes and
            image_url are None unless extract_image is True.
        """
        if self._use_thread:
            return self._fetch_in_thread(url, extract_image)
        return self._fetch_direct(url, extract_image)

    def _fetch_direct(self, url, extract_image):
        try:
            page = self._context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)

                if not self._challenge_passed:
                    page.wait_for_timeout(self.FIRST_PAGE_WAIT)
                else:
                    page.wait_for_timeout(self.SUBSEQUENT_PAGE_WAIT)

                html = page.content()

                if _is_cloudflare_challenge(html):
                    logger.warning("Cloudflare challenge detected, waiting longer...")
                    page.wait_for_timeout(10000)
                    html = page.content()

                if not _is_cloudflare_challenge(html):
                    self._challenge_passed = True

                if not self._banner_dismissed:
                    _dismiss_cookie_banner(page)
                    self._banner_dismissed = True

                image_bytes = None
                image_url = None
                if extract_image:
                    image_bytes, image_url = _extract_page_image(page)

                return html, image_bytes, image_url
            finally:
                page.close()
        except Exception as e:
            logger.error(f"Playwright failed to load {url}: {e}")
            return None, None, None

    def _fetch_in_thread(self, url, extract_image):
        try:
            self._request_queue.put((url, self.timeout, extract_image))
            return self._response_queue.get(timeout=self.timeout / 1000 + 30)
        except Exception as e:
            logger.error(f"Playwright thread failed for {url}: {e}")
            return None, None, None

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


def _extract_events_from_listing(html, base_url="https://13.agendaculturel.fr"):
    """
    Extract event data from listing page using schema.org microdata.

    The listing page contains event cards with class 'y-card' (vertical/featured)
    and 'x-card' (horizontal/compact) that have schema.org itemscope/itemtype
    attributes and structured fields.

    Args:
        html: HTML content of the listing page
        base_url: Base URL for resolving relative links

    Returns:
        List of dicts with event data extracted from microdata
    """
    parser = HTMLParser(html, base_url)
    events = []

    # Find all event cards with schema.org microdata (y-card and x-card)
    cards = parser.select("div.y-card[itemscope], div.x-card[itemscope]")
    if not cards:
        # Fallback: find any itemscope with event types
        cards = parser.select("[itemscope][itemtype*='schema.org']")
        cards = [
            c
            for c in cards
            if any(
                t in (c.get("itemtype") or "")
                for t in ["Event", "MusicEvent", "TheaterEvent", "DanceEvent"]
            )
        ]

    for card in cards:
        schema_type = (card.get("itemtype") or "").split("/")[-1]

        # Skip Place elements (nested inside event cards)
        if schema_type == "Place":
            continue

        name_el = card.find(itemprop="name")
        url_el = card.find(itemprop="url")
        date_el = card.find("time")
        loc_el = card.find(itemprop="location")
        img_el = card.find(itemprop="image")
        desc_el = card.find(itemprop="description")

        if not name_el or not url_el:
            continue

        name = name_el.get_text().strip()
        url = url_el.get("href", "")
        if url and not url.startswith("http"):
            url = f"{base_url}{url}"

        # Extract date from <time datetime="...">
        date_str = date_el.get("datetime", "") if date_el else ""

        # Extract location name
        location_name = ""
        if loc_el:
            loc_name_el = loc_el.find(itemprop="name")
            if loc_name_el:
                location_name = loc_name_el.get_text().strip()

        # Extract image URL
        image_url = ""
        if img_el:
            image_url = img_el.get("content", "") or img_el.get("src", "")

        # Extract description
        description = ""
        if desc_el:
            description = desc_el.get_text().strip()

        events.append(
            {
                "name": name,
                "url": url,
                "date": date_str,
                "location": location_name,
                "image": image_url,
                "description": description,
                "schema_type": schema_type,
            }
        )

    return events


def _extract_json_ld(html):
    """
    Extract JSON-LD structured data from page HTML.

    Args:
        html: HTML content of the detail page

    Returns:
        List of parsed JSON-LD objects
    """
    results = []
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
    Parse event data from a schema.org JSON-LD object.

    Args:
        json_ld: Parsed JSON-LD dict with event data
        event_url: URL of the event detail page
        category_map: Mapping of category names to taxonomy categories

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
        start_dt = datetime.fromisoformat(start_date_str)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=PARIS_TZ)
        else:
            start_dt = start_dt.astimezone(PARIS_TZ)
    except (ValueError, AttributeError):
        logger.warning(f"Failed to parse date for {name}: {start_date_str}")
        return None

    # If time is midnight (00:00), default to 20:00
    if start_dt.hour == 0 and start_dt.minute == 0:
        start_dt = start_dt.replace(hour=20, minute=0)

    # Extract description
    description = json_ld.get("description", "")
    if description and len(description) > 160:
        description = description[:157].rsplit(" ", 1)[0] + "..."

    # Images from agendaculturel.fr are Cloudflare-protected and return 403
    # even in a browser, so we skip image extraction for this source.

    # Extract location
    location_data = json_ld.get("location", {})
    location_name = ""
    if isinstance(location_data, dict):
        location_name = location_data.get("name", "")

    # Determine category from schema @type and URL path
    event_type = json_ld.get("@type", "")
    category = _map_category(event_type, event_url, category_map)

    # Generate source ID from URL
    parsed_url = urlparse(event_url)
    path = parsed_url.path.strip("/")
    # Remove .html suffix for cleaner IDs
    if path.endswith(".html"):
        path = path[:-5]
    source_id = f"agendaculturel:{path}"

    # Build locations list
    locations = [location_name] if location_name else []

    return Event(
        name=name,
        event_url=event_url,
        start_datetime=start_dt,
        description=description,
        image=None,
        categories=[category],
        locations=locations,
        tags=[],
        source_id=source_id,
    )


def _parse_event_from_microdata(event_data, category_map):
    """
    Create an Event from listing page microdata when detail page fails.

    Args:
        event_data: Dict with extracted microdata fields
        category_map: Category mapping from config

    Returns:
        Event object or None if data is insufficient
    """
    name = event_data.get("name", "")
    url = event_data.get("url", "")
    date_str = event_data.get("date", "")

    if not name or not url or not date_str:
        return None

    try:
        start_dt = datetime.fromisoformat(date_str)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=PARIS_TZ)
    except (ValueError, AttributeError):
        return None

    # Default time to 20:00 if midnight
    if start_dt.hour == 0 and start_dt.minute == 0:
        start_dt = start_dt.replace(hour=20, minute=0)

    description = event_data.get("description", "")
    if description and len(description) > 160:
        description = description[:157].rsplit(" ", 1)[0] + "..."

    location_name = event_data.get("location", "")
    schema_type = event_data.get("schema_type", "")

    category = _map_category(schema_type, url, category_map)

    parsed_url = urlparse(url)
    path = parsed_url.path.strip("/")
    if path.endswith(".html"):
        path = path[:-5]
    source_id = f"agendaculturel:{path}"

    locations = [location_name] if location_name else []

    return Event(
        name=name,
        event_url=url,
        start_datetime=start_dt,
        description=description,
        image=None,
        categories=[category],
        locations=locations,
        tags=[],
        source_id=source_id,
    )


def _map_category(schema_type, event_url, category_map):
    """
    Determine event category from schema.org type and URL path.

    Args:
        schema_type: Schema.org @type value (e.g., "MusicEvent")
        event_url: Event URL for path-based category detection
        category_map: Category mapping from config

    Returns:
        Category string from standard taxonomy
    """
    # Check category_map first
    if category_map:
        for key, value in category_map.items():
            if key == schema_type:
                return value

    # Check schema type map
    if schema_type in SCHEMA_TYPE_MAP:
        return SCHEMA_TYPE_MAP[schema_type]

    # Extract category from URL path
    parsed = urlparse(event_url)
    path_parts = parsed.path.strip("/").split("/")
    if path_parts:
        first_segment = path_parts[0]
        if first_segment in PATH_CATEGORY_MAP:
            return PATH_CATEGORY_MAP[first_segment]
        # Check category map for URL path segment
        if category_map and first_segment in category_map:
            return category_map[first_segment]

    return "communaute"


def _is_marseille_area(event_url, location_name="", city=""):
    """
    Check if an event is in the Marseille area.

    Filters based on URL city segment and location metadata.

    Args:
        event_url: Event URL (contains city in path)
        location_name: Venue name
        city: City from structured data

    Returns:
        True if event appears to be in Marseille area
    """
    # Cities we want to include
    included_cities = {
        "marseille",
        "aix-en-provence",
        "aubagne",
        "cassis",
        "la-ciotat",
        "martigues",
        "vitrolles",
        "istres",
        "salon-de-provence",
    }

    # Check URL path for city
    parsed = urlparse(event_url)
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) >= 2:
        url_city = path_parts[1].lower()
        if url_city in included_cities:
            return True

    # Check city from structured data
    if city:
        city_lower = city.lower()
        for included in included_cities:
            if included.replace("-", " ") in city_lower or included in city_lower:
                return True

    # If URL has no city segment (e.g., /festival/slug.html), include it
    # as it may be a regional event
    if len(path_parts) < 3:
        return True

    return False


class AgendaCulturelParser(BaseCrawler):
    """
    Event parser for Agenda Culturel (https://13.agendaculturel.fr).

    Agenda Culturel is a cultural events aggregator for the
    Bouches-du-Rhône department, covering concerts, theatre, dance,
    exhibitions, and festivals. The site uses Cloudflare Turnstile
    protection, requiring a non-headless Playwright browser.

    Strategy:
    1. Load each category listing page with Playwright (non-headless)
    2. Extract event data from schema.org microdata on listing cards
    3. Deduplicate events across category pages
    4. Visit each event detail page for complete JSON-LD data
    5. Filter for Marseille-area events
    6. Convert to Event objects
    """

    source_name = "Agenda Culturel"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Shared Playwright browser session (set during crawl)
        self._pw_session: CloudflarePlaywrightSession | None = None

    def crawl(self) -> list[Event]:
        """
        Crawl multiple category listing pages on Agenda Culturel.

        Overrides BaseCrawler.crawl() to iterate over CATEGORY_LISTING_URLS
        instead of fetching a single root page. Wraps everything in a
        CloudflarePlaywrightSession so one Chromium process is reused for
        all page fetches.

        Returns:
            List of processed Event objects
        """
        try:
            with CloudflarePlaywrightSession() as session:
                self._pw_session = session
                return self._crawl_with_session()
        except ImportError:
            logger.error("Cannot crawl Agenda Culturel: Playwright not installed")
            return []
        finally:
            self._pw_session = None

    def _crawl_with_session(self) -> list[Event]:
        """Execute the crawl logic with an active Playwright session."""
        logger.info(f"Starting crawl for {self.source_name}")
        self.selection_stats = {"accepted": 0, "rejected": 0}

        # Collect events from all category listing pages
        all_listing_events = []
        seen_urls = set()

        for listing_url in CATEGORY_LISTING_URLS:
            html = self.fetch_page(listing_url)
            if not html:
                logger.warning(f"Failed to fetch listing page: {listing_url}")
                continue

            listing_events = _extract_events_from_listing(html)
            logger.info(f"Found {len(listing_events)} events on {listing_url}")

            for event_data in listing_events:
                event_url = event_data.get("url", "")
                if event_url and event_url not in seen_urls:
                    seen_urls.add(event_url)
                    all_listing_events.append(event_data)

            # Rate limit between listing page fetches
            time.sleep(
                self.config.get("rate_limit", {}).get("delay_between_pages", 3.0)
            )

        if not all_listing_events:
            logger.warning("No events found on any Agenda Culturel listing page")
            return []

        logger.info(
            f"Found {len(all_listing_events)} unique events "
            f"across {len(CATEGORY_LISTING_URLS)} category pages"
        )

        # Filter for Marseille area events
        marseille_events = [
            e
            for e in all_listing_events
            if _is_marseille_area(e.get("url", ""), e.get("location", ""))
        ]
        logger.info(f"Filtered to {len(marseille_events)} Marseille-area events")

        # Visit detail pages and create Event objects
        events = []
        for event_data in marseille_events[:MAX_EVENTS]:
            event_url = event_data.get("url", "")
            if not event_url:
                continue

            try:
                event = self._parse_detail_page(event_url)
                if event:
                    events.append(event)
                else:
                    event = _parse_event_from_microdata(event_data, self.category_map)
                    if event:
                        events.append(event)
                        logger.debug(f"Used microdata fallback for: {event.name}")
            except Exception as e:
                logger.warning(f"Failed to parse event from {event_url}: {e}")

            # Rate limiting between detail page fetches
            time.sleep(
                self.config.get("rate_limit", {}).get("delay_between_pages", 3.0)
            )

        logger.info(f"Parsed {len(events)} events from {self.source_name}")

        # Process each event (selection, dedup, markdown generation)
        processed_events = []
        for event in events:
            try:
                processed = self.process_event(event)
                if processed:
                    processed_events.append(processed)
            except Exception as e:
                logger.error(f"Error processing event '{event.name}': {e}")

        return processed_events

    def fetch_page(self, url: str) -> str:
        """
        Fetch page using shared non-headless Playwright session.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string, or empty string on failure
        """
        logger.info(f"Fetching with Playwright (non-headless): {url}")
        if not self._pw_session:
            logger.warning("No Playwright session available")
            return ""

        html, _, _ = self._pw_session.fetch_page(url)
        if not html:
            return ""

        # Verify we got actual content, not a challenge page
        if _is_cloudflare_challenge(html):
            logger.error(f"Cloudflare challenge not bypassed for: {url}")
            return ""

        return html

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from Agenda Culturel listing page.

        Extracts events from the schema.org microdata on the main page,
        then visits detail pages for complete data.

        Args:
            parser: HTMLParser with first listing page content

        Returns:
            List of Event objects
        """
        events = []

        # Extract events from listing page microdata
        listing_html = str(parser.soup)
        listing_events = _extract_events_from_listing(listing_html)

        if not listing_events:
            logger.warning("No events found on Agenda Culturel listing page")
            return events

        logger.info(
            f"Found {len(listing_events)} events on Agenda Culturel listing page"
        )

        # Filter for Marseille area events
        marseille_events = [
            e
            for e in listing_events
            if _is_marseille_area(e.get("url", ""), e.get("location", ""))
        ]
        logger.info(f"Filtered to {len(marseille_events)} Marseille-area events")

        # Process each event detail page
        for event_data in marseille_events[:MAX_EVENTS]:
            event_url = event_data.get("url", "")
            if not event_url:
                continue

            try:
                event = self._parse_detail_page(event_url)
                if event:
                    events.append(event)
                else:
                    # Fallback: use listing page data
                    event = _parse_event_from_microdata(event_data, self.category_map)
                    if event:
                        events.append(event)
                        logger.debug(f"Used microdata fallback for: {event.name}")
            except Exception as e:
                logger.warning(f"Failed to parse event from {event_url}: {e}")

            # Rate limiting between detail page fetches
            time.sleep(
                self.config.get("rate_limit", {}).get("delay_between_pages", 3.0)
            )

        return events

    def _parse_detail_page(self, event_url: str) -> Event | None:
        """
        Fetch and parse an event detail page.

        Extracts JSON-LD structured data from the detail page for
        complete event information. Also extracts the event image
        directly from the Playwright session (since image URLs return
        403 when fetched separately via HTTP).

        Args:
            event_url: URL of the event detail page

        Returns:
            Event object or None if parsing failed
        """
        logger.debug(f"Loading event detail page: {event_url}")

        if not self._pw_session:
            logger.warning("No Playwright session available")
            return None

        # Fetch HTML and image in the same Playwright session
        html, image_bytes, image_url = self._pw_session.fetch_page(
            event_url, extract_image=True
        )
        if not html:
            logger.warning(f"Failed to load detail page: {event_url}")
            return None

        # Verify we got actual content, not a challenge page
        if _is_cloudflare_challenge(html):
            logger.error(f"Cloudflare challenge not bypassed for: {event_url}")
            return None

        # Try JSON-LD first (most reliable)
        json_ld_items = _extract_json_ld(html)

        event_json_ld = None
        for item in json_ld_items:
            if isinstance(item, dict) and item.get("@type") in (
                "MusicEvent",
                "TheaterEvent",
                "DanceEvent",
                "VisualArtsEvent",
                "ExhibitionEvent",
                "Festival",
                "ChildrensEvent",
                "ComedyEvent",
                "Event",
            ):
                event_json_ld = item
                break

        if event_json_ld:
            event = _parse_event_from_json_ld(
                event_json_ld, event_url, self.category_map
            )
        else:
            # Fallback: parse from HTML
            logger.debug(f"No JSON-LD found, trying HTML parsing for: {event_url}")
            event = self._parse_from_html(html, event_url)

        # Save image extracted from Playwright session
        if event and image_bytes:
            local_path = self.image_downloader.save_from_bytes(
                image_bytes,
                image_url=image_url or "",
                event_slug=event.slug,
                event_date=event.start_datetime,
            )
            if local_path:
                event.image = local_path
                logger.debug(f"Saved image for {event.name}: {local_path}")

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

        # Extract title from h1
        h1 = detail_parser.select_one("h1")
        if not h1:
            return None
        name = h1.get_text().strip()
        if not name:
            return None

        # Remove city suffix like " à Marseille le 29 janvier 2026"
        # H1 format: "Concert Randjess à Marseille le 29 janvier 2026"
        name_match = re.match(
            r"(?:Concert|Spectacle|Festival|Exposition)?\s*(.+?)(?:\s+à\s+.+)?$", name
        )
        if name_match:
            name = name_match.group(1).strip()

        # Extract date from <time> elements
        event_datetime = None
        time_el = detail_parser.select_one("time[datetime]")
        if time_el:
            date_str = time_el.get("datetime", "")
            if date_str:
                try:
                    event_datetime = datetime.fromisoformat(date_str)
                    if event_datetime.tzinfo is None:
                        event_datetime = event_datetime.replace(tzinfo=PARIS_TZ)
                except (ValueError, AttributeError):
                    pass

        if not event_datetime:
            return None

        # Default time to 20:00 if midnight
        if event_datetime.hour == 0 and event_datetime.minute == 0:
            event_datetime = event_datetime.replace(hour=20, minute=0)

        # Extract description from meta or content
        description = ""
        og_desc = detail_parser.select_one('meta[property="og:description"]')
        if og_desc:
            description = og_desc.get("content", "")
        if description and len(description) > 160:
            description = description[:157].rsplit(" ", 1)[0] + "..."

        # Images from agendaculturel.fr are Cloudflare-protected (403),
        # so we skip image extraction.

        # Extract location
        location_name = ""
        loc_el = detail_parser.select_one("[itemprop='location'] [itemprop='name']")
        if loc_el:
            location_name = loc_el.get_text().strip()

        # Determine category
        category = _map_category("", event_url, self.category_map)

        # Generate source ID
        parsed_url = urlparse(event_url)
        path = parsed_url.path.strip("/")
        if path.endswith(".html"):
            path = path[:-5]
        source_id = f"agendaculturel:{path}"

        locations = [location_name] if location_name else []

        return Event(
            name=name,
            event_url=event_url,
            start_datetime=event_datetime,
            description=description,
            image=None,
            categories=[category],
            locations=locations,
            tags=[],
            source_id=source_id,
        )
