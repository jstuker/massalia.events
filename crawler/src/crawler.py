"""Base crawler class with common functionality."""

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from .logger import get_logger
from .models.event import Event
from .utils.parser import HTMLParser

if TYPE_CHECKING:
    from .generators.markdown import MarkdownGenerator
    from .selection import SelectionCriteria
    from .utils.http import HTTPClient
    from .utils.images import ImageDownloader
    from .venue_manager import VenueManager

logger = get_logger(__name__)


class BaseCrawler(ABC):
    """
    Abstract base class for event crawlers.

    Provides common functionality for fetching pages, parsing events,
    and generating output. Subclasses must implement parse_events()
    for site-specific extraction logic.
    """

    # Override in subclass with source identifier
    source_name: str = "unknown"

    def __init__(
        self,
        config: dict,
        http_client: "HTTPClient",
        image_downloader: "ImageDownloader",
        markdown_generator: "MarkdownGenerator",
        max_workers: int = 5,
        venue_manager: "VenueManager | None" = None,
    ):
        """
        Initialize the crawler.

        Args:
            config: Source configuration from config.yaml
            http_client: HTTP client for fetching pages
            image_downloader: Image downloader for event images
            markdown_generator: Generator for Hugo markdown files
            max_workers: Max concurrent threads for detail page fetches
            venue_manager: Optional VenueManager for location mapping
        """
        self.config = config
        self.http_client = http_client
        self.image_downloader = image_downloader
        self.markdown_generator = markdown_generator
        self.max_workers = max_workers
        self.venue_manager = venue_manager

        self.source_name = config.get("name", self.source_name)
        self.source_id = config.get("id", "unknown")
        self.base_url = config.get("url", "")
        self.category_map = config.get("category_map", {})

        # Selection criteria (optional)
        self.selection_criteria: SelectionCriteria | None = config.get(
            "selection_criteria"
        )

        # Track selection statistics
        self.selection_stats = {"accepted": 0, "rejected": 0}

    def crawl(self) -> list[Event]:
        """
        Execute the crawl process.

        Returns:
            List of Event objects that were processed
        """
        logger.info(f"Starting crawl for {self.source_name}")
        logger.debug(f"Base URL: {self.base_url}")

        # Reset selection stats
        self.selection_stats = {"accepted": 0, "rejected": 0}

        # Fetch the page
        html = self.fetch_page(self.base_url)
        if not html:
            logger.error(f"Failed to fetch page: {self.base_url}")
            return []

        # Parse events from HTML
        parser = HTMLParser(html, self.base_url)
        events = self.parse_events(parser)

        logger.info(f"Parsed {len(events)} events from {self.source_name}")

        # Process each event
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
        Fetch a page's HTML content.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string, or empty string on failure
        """
        try:
            return self.http_client.get_text(url)
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return ""

    def fetch_pages(self, urls: list[str]) -> dict[str, str]:
        """
        Fetch multiple pages concurrently using a thread pool.

        Respects per-source rate limiting via HTTPClient. When max_workers=1,
        behaves identically to sequential fetch_page() calls.

        Args:
            urls: List of URLs to fetch

        Returns:
            Dict mapping URL to HTML content (empty string on failure)
        """
        results: dict[str, str] = {}

        if not urls:
            return results

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {
                executor.submit(self.fetch_page, url): url for url in urls
            }
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    results[url] = future.result()
                except Exception as e:
                    logger.error(f"Failed to fetch {url}: {e}")
                    results[url] = ""

        return results

    @abstractmethod
    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from HTML content.

        Subclasses must implement this method with site-specific
        extraction logic.

        Args:
            parser: HTMLParser instance with page content

        Returns:
            List of Event objects
        """
        pass

    def process_event(self, event: Event) -> Event | None:
        """
        Process a single event: apply selection, download image, generate markdown.

        Args:
            event: Event to process

        Returns:
            Processed event, or None if skipped/rejected
        """
        # Remap locations through VenueManager (slugified -> canonical slug)
        if self.venue_manager and event.locations:
            event.locations = [
                self.venue_manager.map_location(loc) for loc in event.locations
            ]

        # Apply selection criteria if configured
        if self.selection_criteria:
            result = self.selection_criteria.evaluate(
                name=event.name,
                date=event.start_datetime,
                location=" ".join(event.locations) if event.locations else "",
                description=event.description,
                category=" ".join(event.categories) if event.categories else "",
                url=event.event_url,
            )

            if not result.accepted:
                logger.debug(f"Rejected: {event.name} - {result.reason}")
                self.selection_stats["rejected"] += 1
                return None
            else:
                logger.debug(f"Accepted: {event.name} - {result.reason}")

        # Check for duplicates by source ID
        if event.source_id:
            existing = self.markdown_generator.find_by_source_id(event.source_id)
            if existing:
                logger.debug(f"Skipping duplicate: {event.name} ({event.source_id})")
                return None

        # Download and process image
        if event.image and event.image.startswith("http"):
            local_path = self.image_downloader.download(
                event.image,
                event_slug=event.slug,
            )
            if local_path:
                event.image = local_path

        # Generate markdown file
        self.markdown_generator.generate(event)

        self.selection_stats["accepted"] += 1
        return event

    def map_category(self, raw_category: str) -> str:
        """
        Map source category to standard taxonomy.

        Uses selection criteria category mapping if available,
        otherwise falls back to source-specific or default mapping.

        Args:
            raw_category: Category from source site

        Returns:
            Standard category slug
        """
        # Try selection criteria mapping first
        if self.selection_criteria:
            return self.selection_criteria.map_category(raw_category)

        # Look up in source-specific category map
        if self.category_map:
            for source_cat, target_cat in self.category_map.items():
                if source_cat.lower() in raw_category.lower():
                    return target_cat

        # Default mappings
        defaults = {
            "danse": "danse",
            "dance": "danse",
            "musique": "musique",
            "music": "musique",
            "concert": "musique",
            "theatre": "theatre",
            "théâtre": "theatre",
            "spectacle": "theatre",
            "art": "art",
            "expo": "art",
            "exposition": "art",
            "communaute": "communaute",
            "atelier": "communaute",
            "workshop": "communaute",
        }

        raw_lower = raw_category.lower()
        for key, value in defaults.items():
            if key in raw_lower:
                return value

        # Unknown category
        logger.warning(f"Unknown category: {raw_category}")
        return "communaute"  # Default fallback

    def map_location(self, raw_location: str) -> str:
        """
        Map source location to standard taxonomy slug.

        Delegates to VenueManager when available, otherwise returns as-is.

        Args:
            raw_location: Location name from source

        Returns:
            Location slug
        """
        if self.venue_manager:
            return self.venue_manager.map_location(raw_location)
        return raw_location
