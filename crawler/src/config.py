"""Configuration loading and validation for the crawler."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .logger import get_logger

logger = get_logger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""

    pass


@dataclass
class RateLimit:
    """Rate limiting configuration."""

    requests_per_second: float = 1.0
    delay_between_pages: float = 2.0


@dataclass
class Selectors:
    """CSS selectors for event extraction."""

    event_list: str | None = None
    event_item: str | None = None
    event_title: str | None = None
    event_date: str | None = None
    event_time: str | None = None
    event_link: str | None = None
    event_image: str | None = None
    event_description: str | None = None
    event_category: str | None = None


@dataclass
class Source:
    """Configuration for a single event source."""

    name: str
    id: str
    url: str
    parser: str
    enabled: bool = True
    rate_limit: RateLimit = field(default_factory=RateLimit)
    selectors: Selectors = field(default_factory=Selectors)
    categories_map: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Apply environment variable overrides."""
        env_prefix = f"CRAWLER_SOURCE_{self.id.upper().replace('-', '_')}"

        # URL override
        url_override = os.environ.get(f"{env_prefix}_URL")
        if url_override:
            logger.debug(f"Overriding URL for {self.id} from environment")
            self.url = url_override

        # Enabled override
        enabled_override = os.environ.get(f"{env_prefix}_ENABLED")
        if enabled_override is not None:
            self.enabled = enabled_override.lower() in ("true", "1", "yes")
            logger.debug(f"Overriding enabled for {self.id}: {self.enabled}")


@dataclass
class SourcesConfig:
    """Configuration for all event sources."""

    sources: list[Source]
    defaults: dict = field(default_factory=dict)

    def get_enabled_sources(self) -> list[Source]:
        """Return only enabled sources."""
        return [s for s in self.sources if s.enabled]

    def get_source_by_id(self, source_id: str) -> Source | None:
        """Find a source by its ID."""
        for source in self.sources:
            if source.id == source_id:
                return source
        return None

    def get_source_by_parser(self, parser: str) -> list[Source]:
        """Find sources using a specific parser."""
        return [s for s in self.sources if s.parser == parser]


def load_sources_config(config_path: Path) -> SourcesConfig:
    """
    Load and validate sources configuration from YAML file.

    Args:
        config_path: Path to sources.yaml file

    Returns:
        SourcesConfig object with validated configuration

    Raises:
        ConfigurationError: If configuration is invalid
    """
    if not config_path.exists():
        raise ConfigurationError(f"Sources config file not found: {config_path}")

    logger.info(f"Loading sources configuration from {config_path}")

    try:
        with open(config_path, encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in sources config: {e}") from e

    if not raw_config:
        raise ConfigurationError("Sources config file is empty")

    # Validate against schema
    validate_sources_config(raw_config, config_path.parent)

    # Parse defaults
    defaults = raw_config.get("defaults", {})
    default_rate_limit = defaults.get("rate_limit", {})

    # Parse sources
    sources = []
    raw_sources = raw_config.get("sources", [])

    if not raw_sources:
        raise ConfigurationError("No sources defined in configuration")

    for i, raw_source in enumerate(raw_sources):
        try:
            source = _parse_source(raw_source, default_rate_limit)
            sources.append(source)
        except Exception as e:
            source_name = raw_source.get("name", f"source #{i + 1}")
            raise ConfigurationError(f"Invalid source '{source_name}': {e}") from e

    logger.info(f"Loaded {len(sources)} sources ({len([s for s in sources if s.enabled])} enabled)")

    return SourcesConfig(sources=sources, defaults=defaults)


def _parse_source(raw: dict, default_rate_limit: dict) -> Source:
    """Parse a single source from raw config."""
    # Required fields
    for required in ["name", "id", "url", "parser"]:
        if required not in raw:
            raise ConfigurationError(f"Missing required field: {required}")

    # Parse rate limit with defaults
    raw_rate_limit = raw.get("rate_limit", {})
    rate_limit = RateLimit(
        requests_per_second=raw_rate_limit.get(
            "requests_per_second",
            default_rate_limit.get("requests_per_second", 1.0),
        ),
        delay_between_pages=raw_rate_limit.get(
            "delay_between_pages",
            default_rate_limit.get("delay_between_pages", 2.0),
        ),
    )

    # Parse selectors
    raw_selectors = raw.get("selectors", {})
    selectors = Selectors(
        event_list=raw_selectors.get("event_list"),
        event_item=raw_selectors.get("event_item"),
        event_title=raw_selectors.get("event_title"),
        event_date=raw_selectors.get("event_date"),
        event_time=raw_selectors.get("event_time"),
        event_link=raw_selectors.get("event_link"),
        event_image=raw_selectors.get("event_image"),
        event_description=raw_selectors.get("event_description"),
        event_category=raw_selectors.get("event_category"),
    )

    return Source(
        name=raw["name"],
        id=raw["id"],
        url=raw["url"],
        parser=raw["parser"],
        enabled=raw.get("enabled", True),
        rate_limit=rate_limit,
        selectors=selectors,
        categories_map=raw.get("categories_map", {}),
    )


def validate_sources_config(config: dict, config_dir: Path) -> None:
    """
    Validate configuration against JSON Schema.

    Args:
        config: Parsed configuration dictionary
        config_dir: Directory containing schema file

    Raises:
        ConfigurationError: If validation fails
    """
    schema_path = config_dir / "sources.schema.json"

    if not schema_path.exists():
        logger.warning(f"Schema file not found: {schema_path}, skipping validation")
        return

    try:
        import jsonschema
    except ImportError:
        logger.warning("jsonschema not installed, skipping schema validation")
        return

    try:
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON schema: {e}") from e

    try:
        jsonschema.validate(instance=config, schema=schema)
    except jsonschema.ValidationError as e:
        # Format a helpful error message
        path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        raise ConfigurationError(f"Configuration validation failed at '{path}': {e.message}") from e

    logger.debug("Configuration validated against schema")
