"""Parser for Espace Julien events (espace-julien.com).

Espace Julien is a 1,000-capacity music venue on Cours Julien in Marseille,
open since 1984. The website also lists events for Le Makeda and Cafe Julien,
managed by the same organization.

The site is built on Drupal with infinite scroll pagination (?page=N).
Each event detail page contains JSON-LD structured data (schema.org/Event).
"""

import json
from datetime import datetime
from urllib.parse import urlparse

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import PARIS_TZ
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

# Maximum number of listing pages to crawl
MAX_PAGES = 5


def _extract_event_urls(parser: HTMLParser) -> list[str]:
    """
    Extract event detail page URLs from a listing page.

    Args:
        parser: HTMLParser with listing page content

    Returns:
        List of unique absolute event URLs
    """
    urls = set()

    for link in parser.select("div.views-row a[href]"):
        href = link.get("href", "")
        if not href:
            continue

        # Only include /agenda/ detail pages, not the listing itself
        if "/agenda/" in href and href.rstrip("/") != "/agenda":
            url = parser.get_link(link, selector=None)
            if not url:
                # Fallback: resolve manually
                from urllib.parse import urljoin

                url = urljoin(parser.base_url, href)
            if url:
                urls.add(url)

    return sorted(urls)


def _extract_event_categories(card: object) -> list[str]:
    """
    Extract category slugs from an event card's badge elements.

    Args:
        card: BeautifulSoup Tag for a views-row element

    Returns:
        List of category term names (e.g., ['rap-hip-hop', 'festival-avec-le-temps'])
    """
    categories = []
    for badge in card.select("span.badge[data-term-name]"):
        term = badge.get("data-term-name", "").strip()
        if term:
            categories.append(term)
    return categories


def _is_sold_out(card: object) -> bool:
    """Check if an event card has a sold-out badge."""
    return card.select_one("span.--evt-status-full") is not None


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


def _parse_iso_datetime(date_str: str) -> datetime | None:
    """
    Parse an ISO datetime string to a timezone-aware datetime in Paris TZ.

    Args:
        date_str: ISO format datetime string (e.g., "2026-03-07T20:00:00+01:00")

    Returns:
        datetime in Paris timezone, or None on failure
    """
    try:
        date_str = date_str.replace(".000000Z", "+00:00").replace("Z", "+00:00")
        dt = datetime.fromisoformat(date_str)
        return dt.astimezone(PARIS_TZ)
    except (ValueError, TypeError):
        return None


def _extract_image_url(json_ld: dict) -> str | None:
    """
    Extract image URL from JSON-LD, handling various formats.

    Args:
        json_ld: JSON-LD Event dict

    Returns:
        Image URL string or None
    """
    raw_image = json_ld.get("image", "")
    if isinstance(raw_image, list):
        image = raw_image[0] if raw_image else ""
    elif isinstance(raw_image, dict):
        image = raw_image.get("url", "")
    else:
        image = raw_image
    return image if image else None


def _extract_venue_name(json_ld: dict) -> str:
    """
    Extract venue name from JSON-LD location field.

    Args:
        json_ld: JSON-LD Event dict

    Returns:
        Venue name string (defaults to "Espace Julien")
    """
    location = json_ld.get("location", {})
    if isinstance(location, dict):
        return location.get("name", "Espace Julien").strip()
    return "Espace Julien"


def _generate_source_id(url: str) -> str:
    """Generate a unique source ID from an event URL slug."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    segments = path.split("/")
    event_slug = segments[-1] if segments else path
    return f"espacejulien:{event_slug}"


class EspaceJulienParser(BaseCrawler):
    """
    Event parser for Espace Julien (espace-julien.com).

    This parser:
    1. Crawls paginated listing pages (/agenda?page=N)
    2. Collects event URLs and category info from listing cards
    3. Fetches detail pages and extracts JSON-LD structured data
    4. Maps venues (Espace Julien, Le Makeda, Cafe Julien)
    """

    source_name = "Espace Julien"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from Espace Julien listing pages.

        Args:
            parser: HTMLParser with the first listing page content

        Returns:
            List of Event objects
        """
        # Collect event metadata from all listing pages
        event_meta = self._collect_event_metadata(parser)

        if not event_meta:
            logger.warning("No event URLs found on Espace Julien")
            return []

        logger.info(f"Found {len(event_meta)} event URLs on Espace Julien")

        # Batch-fetch all detail pages
        urls = list(event_meta.keys())
        pages = self.fetch_pages(urls)

        events = []
        for url in urls:
            html = pages.get(url, "")
            if not html:
                continue
            try:
                meta = event_meta[url]
                event = self._parse_detail_page(url, html, meta)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event from {url}: {e}")

        logger.info(f"Extracted {len(events)} events from Espace Julien")
        return events

    def _collect_event_metadata(self, first_page_parser: HTMLParser) -> dict[str, dict]:
        """
        Collect event URLs and card metadata from all listing pages.

        Returns:
            Dict mapping URL -> metadata dict with 'categories' and 'sold_out'
        """
        all_meta: dict[str, dict] = {}

        # Process first page
        self._extract_metadata_from_page(first_page_parser, all_meta)

        # Paginate through additional pages
        for page_num in range(1, MAX_PAGES + 1):
            page_url = f"{self.base_url.rstrip('/')}?page={page_num}"
            html = self.fetch_page(page_url)
            if not html:
                break

            page_parser = HTMLParser(html, self.base_url)
            cards_before = len(all_meta)
            self._extract_metadata_from_page(page_parser, all_meta)

            new_cards = len(all_meta) - cards_before
            if new_cards == 0:
                break

            logger.debug(
                f"Page {page_num}: found {new_cards} new events "
                f"(total: {len(all_meta)})"
            )

        return all_meta

    def _extract_metadata_from_page(
        self, parser: HTMLParser, meta: dict[str, dict]
    ) -> None:
        """
        Extract event URLs and metadata from a single listing page.

        Args:
            parser: HTMLParser for the page
            meta: Dict to update with URL -> metadata mappings
        """
        for card in parser.select("div.views-row"):
            link_el = card.select_one("a[href*='/agenda/']")
            if not link_el:
                continue

            href = link_el.get("href", "")
            if not href or href.rstrip("/") == "/agenda":
                continue

            from urllib.parse import urljoin

            url = urljoin(parser.base_url, href)

            if url not in meta:
                categories = _extract_event_categories(card)
                sold_out = _is_sold_out(card)
                meta[url] = {
                    "categories": categories,
                    "sold_out": sold_out,
                }

    def _parse_detail_page(self, url: str, html: str, meta: dict) -> Event | None:
        """
        Parse an event from its detail page JSON-LD.

        Args:
            url: Event detail page URL
            html: HTML content of the detail page
            meta: Metadata dict from listing page (categories, sold_out)

        Returns:
            Event object or None if parsing fails
        """
        # Find Event JSON-LD
        json_ld_list = _extract_json_ld(html)
        event_json_ld = None
        for item in json_ld_list:
            if item.get("@type") == "Event":
                event_json_ld = item
                break

        if not event_json_ld:
            logger.debug(f"No Event JSON-LD found on: {url}")
            return None

        # Extract required fields
        name = event_json_ld.get("name", "").strip()
        if not name:
            return None

        start_date_str = event_json_ld.get("startDate", "")
        if not start_date_str:
            return None

        start_datetime = _parse_iso_datetime(start_date_str)
        if not start_datetime:
            return None

        # Skip past events
        now = datetime.now(PARIS_TZ)
        if start_datetime < now:
            return None

        # Extract description from performer info in JSON-LD
        description = self._extract_description(json_ld=event_json_ld, html=html)

        # Extract image
        image = _extract_image_url(event_json_ld)

        # Map categories from listing page metadata
        categories = []
        for raw_cat in meta.get("categories", []):
            mapped = self.map_category(raw_cat)
            if mapped and mapped not in categories:
                categories.append(mapped)
        if not categories:
            # Fallback: try keywords from JSON-LD
            keywords = event_json_ld.get("keywords", "")
            if keywords:
                for kw in keywords.split(","):
                    mapped = self.map_category(kw.strip())
                    if mapped and mapped not in categories:
                        categories.append(mapped)
        if not categories:
            categories = ["musique"]  # Default for a music venue

        # Map venue location
        venue_name = _extract_venue_name(event_json_ld)
        locations = [self.map_location(venue_name)]

        # Extract performer tags
        tags = self._extract_performer_tags(event_json_ld, name)

        return Event(
            name=name,
            event_url=url,
            start_datetime=start_datetime,
            description=description,
            image=image,
            categories=categories,
            locations=locations,
            tags=tags,
            source_id=_generate_source_id(url),
        )

    def _extract_description(self, json_ld: dict, html: str) -> str:
        """Extract event description from JSON-LD performers or HTML."""
        # Try performer description from JSON-LD
        performers = json_ld.get("performer", [])
        if isinstance(performers, dict):
            performers = [performers]

        for performer in performers:
            desc = performer.get("description", "").strip()
            if desc and len(desc) > 20:
                return HTMLParser.truncate(HTMLParser.clean_text(desc), 160)

        # Fallback: try HTML meta description or content
        detail = HTMLParser(html, self.base_url)
        meta_desc = detail.get_attr(detail.soup, "content", 'meta[name="description"]')
        if meta_desc and len(meta_desc) > 20:
            return HTMLParser.truncate(HTMLParser.clean_text(meta_desc), 160)

        return ""

    def _extract_performer_tags(self, json_ld: dict, event_name: str) -> list[str]:
        """Extract performer names as tags from JSON-LD."""
        tags = []
        performers = json_ld.get("performer", [])
        if isinstance(performers, dict):
            performers = [performers]

        for performer in performers:
            perf_name = performer.get("name", "").strip().lower()
            if perf_name and perf_name != event_name.lower():
                tags.append(perf_name)

        return tags[:5]
