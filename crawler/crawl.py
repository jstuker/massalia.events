#!/usr/bin/env python3
"""
Massalia Events Crawler
=======================

Main entry point for crawling Marseille cultural event websites.

Usage:
    python crawl.py                    # Run all enabled sources
    python crawl.py --source lafriche  # Run specific source (by ID)
    python crawl.py --dry-run          # Preview without writing files
    python crawl.py --log-level DEBUG  # Verbose output
"""

import sys
from pathlib import Path

import click
import yaml

from src.config import ConfigurationError, load_sources_config
from src.generators import MarkdownGenerator
from src.logger import get_logger, setup_logging
from src.parsers import get_parser
from src.utils import HTTPClient, ImageDownloader


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=Path(__file__).parent / "config.yaml",
    help="Path to configuration file",
)
@click.option(
    "--source",
    "-s",
    type=str,
    default=None,
    help="Run only specified source (by source ID)",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    default=False,
    help="Preview actions without writing files",
)
@click.option(
    "--log-level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default=None,
    help="Override log level from config",
)
@click.option(
    "--list-sources",
    is_flag=True,
    default=False,
    help="List all configured sources and exit",
)
def main(
    config: Path,
    source: str | None,
    dry_run: bool,
    log_level: str | None,
    list_sources: bool,
):
    """
    Crawl Marseille event websites and generate Hugo content.

    This crawler fetches events from configured sources, extracts event data,
    downloads images, and generates Hugo-compatible markdown files.
    """
    # Load main configuration
    cfg = load_config(config)

    # Setup logging
    effective_log_level = log_level or cfg.get("log_level", "INFO")
    setup_logging(
        level=effective_log_level,
        log_file=cfg.get("log_file"),
    )
    logger = get_logger(__name__)

    # Load sources configuration
    config_dir = config.parent
    sources_file = config_dir / cfg.get("sources_file", "config/sources.yaml")

    try:
        sources_config = load_sources_config(sources_file)
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Handle --list-sources
    if list_sources:
        click.echo("\nConfigured sources:")
        click.echo("-" * 60)
        for src in sources_config.sources:
            status = "enabled" if src.enabled else "disabled"
            click.echo(f"  {src.id:20} {src.name:30} [{status}]")
        click.echo(f"\nTotal: {len(sources_config.sources)} sources "
                   f"({len(sources_config.get_enabled_sources())} enabled)")
        return

    logger.info("Massalia Events Crawler starting...")

    if dry_run:
        logger.info("DRY RUN MODE - No files will be written")

    # Resolve output paths relative to config file location
    output_dir = config_dir / cfg.get("output_dir", "../content/events")
    image_dir = config_dir / cfg.get("image_dir", "../static/images/events")

    logger.debug(f"Output directory: {output_dir.resolve()}")
    logger.debug(f"Image directory: {image_dir.resolve()}")

    # Initialize components
    http_cfg = cfg.get("http", {})
    http_client = HTTPClient(
        timeout=http_cfg.get("timeout", 30),
        retry_count=http_cfg.get("retry_count", 3),
        retry_delay=http_cfg.get("retry_delay", 1.0),
        rate_limit_delay=http_cfg.get("rate_limit_delay", 1.0),
        user_agent=http_cfg.get("user_agent", "MassaliaEventsCrawler/1.0"),
    )

    image_cfg = cfg.get("image_settings", {})
    image_downloader = ImageDownloader(
        output_dir=image_dir,
        max_width=image_cfg.get("max_width", 1200),
        quality=image_cfg.get("quality", 85),
        format=image_cfg.get("format", "webp"),
        http_client=http_client,
        dry_run=dry_run,
    )

    markdown_generator = MarkdownGenerator(
        output_dir=output_dir,
        dry_run=dry_run,
    )

    # Get sources to process
    if source:
        # Find source by ID
        src = sources_config.get_source_by_id(source)
        if not src:
            # Try matching by parser name for backwards compatibility
            sources_list = sources_config.get_source_by_parser(source)
            if not sources_list:
                logger.error(f"No source found with ID or parser: {source}")
                sys.exit(1)
        else:
            sources_list = [src]
    else:
        sources_list = sources_config.get_enabled_sources()

    if not sources_list:
        logger.warning("No sources to process")
        return

    # Process each source
    total_events = 0
    for src in sources_list:
        if not src.enabled:
            logger.debug(f"Skipping disabled source: {src.name}")
            continue

        logger.info(f"Processing source: {src.name} ({src.id})")

        # Build source config dict for parser (backwards compatibility)
        source_cfg = {
            "name": src.name,
            "id": src.id,
            "url": src.url,
            "parser": src.parser,
            "enabled": src.enabled,
            "rate_limit": {
                "requests_per_second": src.rate_limit.requests_per_second,
                "delay_between_pages": src.rate_limit.delay_between_pages,
            },
            "selectors": {
                k: v for k, v in vars(src.selectors).items() if v is not None
            },
            "category_map": src.categories_map,
        }

        try:
            parser_class = get_parser(src.parser)
            parser = parser_class(
                config=source_cfg,
                http_client=http_client,
                image_downloader=image_downloader,
                markdown_generator=markdown_generator,
            )

            events = parser.crawl()
            event_count = len(events)
            total_events += event_count

            logger.info(f"  Found {event_count} events from {src.name}")

        except ValueError as e:
            logger.warning(f"Parser not available for {src.name}: {e}")
        except Exception as e:
            logger.error(f"Error processing {src.name}: {e}")
            if effective_log_level == "DEBUG":
                logger.exception("Full traceback:")

    # Summary
    logger.info(f"Crawl complete. Total events processed: {total_events}")

    if dry_run:
        logger.info("DRY RUN - No files were written")


if __name__ == "__main__":
    main()
