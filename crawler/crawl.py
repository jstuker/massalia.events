#!/usr/bin/env python3
"""
Massalia Events Crawler
=======================

Main entry point for crawling Marseille cultural event websites.

Usage:
    python crawl.py                    # Run all enabled sources
    python crawl.py --source lafriche  # Run specific source
    python crawl.py --dry-run          # Preview without writing files
    python crawl.py --log-level DEBUG  # Verbose output
"""

import sys
from pathlib import Path

import click
import yaml

from src.logger import setup_logging, get_logger
from src.parsers import get_parser
from src.utils import HTTPClient, ImageDownloader
from src.generators import MarkdownGenerator


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
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
    help="Run only specified source (by parser name)",
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
def main(config: Path, source: str | None, dry_run: bool, log_level: str | None):
    """
    Crawl Marseille event websites and generate Hugo content.

    This crawler fetches events from configured sources, extracts event data,
    downloads images, and generates Hugo-compatible markdown files.
    """
    # Load configuration
    cfg = load_config(config)

    # Setup logging
    effective_log_level = log_level or cfg.get("log_level", "INFO")
    setup_logging(
        level=effective_log_level,
        log_file=cfg.get("log_file"),
    )
    logger = get_logger(__name__)

    logger.info("Massalia Events Crawler starting...")

    if dry_run:
        logger.info("DRY RUN MODE - No files will be written")

    # Resolve output paths relative to config file location
    config_dir = config.parent
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
    sources = cfg.get("sources", [])
    if not sources:
        logger.warning("No sources configured")
        return

    # Filter to specific source if requested
    if source:
        sources = [s for s in sources if s.get("parser", "").lower() == source.lower()]
        if not sources:
            logger.error(f"No source found with parser: {source}")
            sys.exit(1)

    # Process each source
    total_events = 0
    for source_cfg in sources:
        if not source_cfg.get("enabled", True):
            logger.debug(f"Skipping disabled source: {source_cfg.get('name')}")
            continue

        source_name = source_cfg.get("name", "Unknown")
        parser_name = source_cfg.get("parser")

        if not parser_name:
            logger.warning(f"Source '{source_name}' has no parser configured")
            continue

        logger.info(f"Processing source: {source_name}")

        try:
            parser_class = get_parser(parser_name)
            parser = parser_class(
                config=source_cfg,
                http_client=http_client,
                image_downloader=image_downloader,
                markdown_generator=markdown_generator,
            )

            events = parser.crawl()
            event_count = len(events)
            total_events += event_count

            logger.info(f"  Found {event_count} events from {source_name}")

        except Exception as e:
            logger.error(f"Error processing {source_name}: {e}")
            if effective_log_level == "DEBUG":
                logger.exception("Full traceback:")

    # Summary
    logger.info(f"Crawl complete. Total events processed: {total_events}")

    if dry_run:
        logger.info("DRY RUN - No files were written")


if __name__ == "__main__":
    main()
