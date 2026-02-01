"""Base crawler class with common functionality."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .logger import get_logger
from .models.event import Event
from .utils.parser import HTMLParser

if TYPE_CHECKING:
    from .generators.markdown import MarkdownGenerator
    from .selection import SelectionCriteria
    from .utils.http import HTTPClient
    from .utils.images import ImageDownloader

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
    ):
        """
        Initialize the crawler.

        Args:
            config: Source configuration from config.yaml
            http_client: HTTP client for fetching pages
            image_downloader: Image downloader for event images
            markdown_generator: Generator for Hugo markdown files
        """
        self.config = config
        self.http_client = http_client
        self.image_downloader = image_downloader
        self.markdown_generator = markdown_generator

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

        Args:
            raw_location: Location name from source

        Returns:
            Location slug
        """
        # Known location mappings
        known_locations = {
            # Existing venues
            "klap": "klap",
            "la friche": "la-friche",
            "friche": "la-friche",
            "la criee": "la-criee",
            "la criée": "la-criee",
            "criee": "la-criee",
            "criée": "la-criee",
            "chateau de servieres": "chateau-de-servieres",
            "servieres": "chateau-de-servieres",
            "notre dame de la garde": "notre-dame-de-la-garde",
            "notre-dame": "notre-dame-de-la-garde",
            # Shotgun venues
            "baby club": "baby-club",
            "bohemia": "bohemia",
            "boum marseille": "boum-marseille",
            "boum": "boum-marseille",
            "bounce club": "bounce-club-marseille",
            "bounce club marseille": "bounce-club-marseille",
            "cabaret aleatoire": "cabaret-aleatoire",
            "cabaret aléatoire": "cabaret-aleatoire",
            "danceteria": "danceteria",
            "esquina tropical": "esquina-tropical",
            "francois rouzier": "francois-rouzier",
            "françois rouzier": "francois-rouzier",
            "ipn club": "ipn-club-aix",
            "ipn club aix": "ipn-club-aix",
            "la traverse de balkis": "la-traverse-de-balkis",
            "traverse de balkis": "la-traverse-de-balkis",
            "la wo": "la-wo-marseille",
            "la wo marseille": "la-wo-marseille",
            "le bazar": "le-bazar",
            "le bouge": "le-bouge-marseille",
            "le bougé": "le-bouge-marseille",
            "le bouge marseille": "le-bouge-marseille",
            "le chapiteau": "le-chapiteau-marseille",
            "le chapiteau marseille": "le-chapiteau-marseille",
            "le makeda": "le-makeda",
            "makeda": "le-makeda",
            "le nucleaire": "le-nucleaire-marseille",
            "le nucléaire": "le-nucleaire-marseille",
            "le nucleaire marseille": "le-nucleaire-marseille",
            "level up project": "level-up-project",
            "mama shelter": "mama-shelter-marseille",
            "mama shelter marseille": "mama-shelter-marseille",
            "manray": "manray-club",
            "manray club": "manray-club",
            "mira": "mira",
            "rockypop": "rockypop-marseille",
            "rockypop marseille": "rockypop-marseille",
            "shafro": "shafro",
            "sunny comedy club": "sunny-comedy-club",
            "the pablo club": "the-pablo-club",
            "pablo club": "the-pablo-club",
            "unite 22": "unite-22",
            "unité 22": "unite-22",
            "vice versa": "vice-versa-marseille",
            "vice versa marseille": "vice-versa-marseille",
            "vl": "vl",
            # Journal Zébuline venues
            "le zef": "le-zef",
            "mucem": "mucem",
            "théâtre de l'oeuvre": "theatre-de-l-oeuvre",
            "theatre de l'oeuvre": "theatre-de-l-oeuvre",
            "théâtre de l'œuvre": "theatre-de-l-oeuvre",
            "la mesón": "theatre-de-l-oeuvre",
            "la meson": "theatre-de-l-oeuvre",
            "le merlan": "le-merlan",
            "ballet national de marseille": "ballet-national-de-marseille",
            "opéra de marseille": "opera-de-marseille",
            "opera de marseille": "opera-de-marseille",
            "le silo": "le-cepac-silo-marseille",
            "cepac silo": "le-cepac-silo-marseille",
            "le cepac silo": "le-cepac-silo-marseille",
            "espace julien": "espace-julien",
            "le moulin": "le-moulin",
            "mac marseille": "mac-marseille",
            "l'alhambra": "l-alhambra",
            "théâtre joliette": "theatre-joliette",
            "theatre joliette": "theatre-joliette",
            "théâtre toursky": "scene-mediterranee",
            "theatre toursky": "scene-mediterranee",
            "théâtre nono": "theatre-nono",
            "theatre nono": "theatre-nono",
            "théâtre gyptis": "theatre-gyptis",
            "theatre gyptis": "theatre-gyptis",
            "gyptis": "theatre-gyptis",
            "la minoterie": "la-minoterie",
            "3 bisf": "3-bisf",
            "les bancs publics": "les-bancs-publics",
            "montévidéo": "montevideo",
            "montevideo": "montevideo",
            "pavillon noir": "pavillon-noir",
            "frac marseille": "frac-marseille",
            "bmvr alcazar": "bmvr-alcazar",
            "alcazar": "bmvr-alcazar",
            "musée cantini": "musee-cantini",
            "musee cantini": "musee-cantini",
            "le grand théâtre de provence": "grand-theatre-de-provence",
            "le grand theatre de provence": "grand-theatre-de-provence",
            "grand théâtre de provence": "grand-theatre-de-provence",
            "grand theatre de provence": "grand-theatre-de-provence",
            "théâtre du lacydon": "theatre-du-lacydon",
            "theatre du lacydon": "theatre-du-lacydon",
            "théâtre off": "theatre-off",
            "theatre off": "theatre-off",
        }

        raw_lower = raw_location.lower()
        for key, slug in known_locations.items():
            if key in raw_lower:
                return slug

        # Return as-is if not found (will be slugified by Event model)
        return raw_location
