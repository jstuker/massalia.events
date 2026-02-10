#!/usr/bin/env python3
"""
Massalia Events Crawler
=======================

Command-line interface for crawling Marseille cultural event websites.

Usage:
    python crawl.py run                       # Run all enabled sources
    python crawl.py run --source lafriche     # Run specific source
    python crawl.py run --dry-run             # Preview without writing files
    python crawl.py list-sources              # List configured sources
    python crawl.py validate                  # Check configuration
    python crawl.py status                    # Show last crawl results
    python crawl.py clean                     # Remove expired events
"""

import json
import signal
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import click
import yaml

from src.config import ConfigurationError, load_sources_config, validate_sources_config
from src.deduplicator import EventDeduplicator
from src.generators import MarkdownGenerator
from src.logger import get_logger, setup_logging
from src.parsers import get_parser
from src.selection import load_selection_criteria
from src.utils import HTTPClient, ImageDownloader

# Paris timezone for Marseille events
PARIS_TZ = ZoneInfo("Europe/Paris")

# Status file for tracking crawl results
STATUS_FILE = ".crawl_status.json"

# Global flag for interrupt handling
_interrupted = False


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging_from_config(
    config: dict,
    config_dir: Path,
    log_level_override: str | None = None,
    log_file_override: Path | None = None,
) -> None:
    """Configure logging based on config file and CLI overrides."""
    # Get logging configuration (support both old flat format and new nested format)
    logging_cfg = config.get("logging", {})
    if not logging_cfg:
        # Backwards compatibility with old flat config format
        logging_cfg = {
            "log_level": config.get("log_level", "INFO"),
            "log_file": config.get("log_file"),
        }

    # CLI flags override config file settings
    effective_log_level = log_level_override or logging_cfg.get("log_level", "INFO")
    effective_log_file = log_file_override or logging_cfg.get("log_file")
    log_dir = config_dir if effective_log_file else None

    setup_logging(
        level=effective_log_level,
        log_file=str(effective_log_file) if effective_log_file else None,
        log_dir=log_dir,
        log_format=logging_cfg.get("log_format", "text"),
        max_bytes=logging_cfg.get("max_file_size", 10 * 1024 * 1024),
        backup_count=logging_cfg.get("backup_count", 5),
    )


def save_status(config_dir: Path, status: dict) -> None:
    """Save crawl status to file."""
    status_path = config_dir / STATUS_FILE
    status["timestamp"] = datetime.now(PARIS_TZ).isoformat()
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)


def load_status(config_dir: Path) -> dict | None:
    """Load last crawl status from file."""
    status_path = config_dir / STATUS_FILE
    if not status_path.exists():
        return None
    with open(status_path, encoding="utf-8") as f:
        return json.load(f)


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    global _interrupted
    _interrupted = True
    click.echo(
        click.style("\n\nInterrupt received, finishing current task...", fg="yellow")
    )


# Set up signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


@click.group(invoke_without_command=True)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=Path(__file__).parent / "config.yaml",
    help="Path to configuration file",
)
@click.option(
    "--log-level",
    "-l",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    default=None,
    help="Override log level from config",
)
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    default=None,
    help="Override log file path from config",
)
@click.version_option(version="1.0.0", prog_name="massalia-crawler")
@click.pass_context
def cli(ctx, config: Path, log_level: str | None, log_file: Path | None):
    """
    Massalia Events Crawler - Aggregate cultural events from Marseille.

    This crawler fetches events from configured sources, extracts event data,
    downloads images, and generates Hugo-compatible markdown files.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["config_dir"] = config.parent
    ctx.obj["log_level"] = log_level
    ctx.obj["log_file"] = log_file

    # Load config
    try:
        ctx.obj["config"] = load_config(config)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)

    # If no subcommand is provided, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
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
    "--skip-selection",
    is_flag=True,
    default=False,
    help="Skip selection criteria filtering (include all events)",
)
@click.option(
    "--concurrency",
    "-c",
    type=int,
    default=5,
    show_default=True,
    help="Max concurrent threads for detail page fetches (1 = sequential)",
)
@click.pass_context
def run(ctx, source: str | None, dry_run: bool, skip_selection: bool, concurrency: int):
    """
    Run the crawler to fetch and process events.

    By default, crawls all enabled sources. Use --source to crawl a specific source.
    Use --dry-run to preview what would be created without writing files.
    """
    global _interrupted

    cfg = ctx.obj["config"]
    config_dir = ctx.obj["config_dir"]
    log_level = ctx.obj["log_level"]
    log_file = ctx.obj["log_file"]

    # Setup logging
    setup_logging_from_config(cfg, config_dir, log_level, log_file)
    logger = get_logger(__name__)

    # Track effective log level for stack traces
    effective_log_level = log_level or cfg.get("logging", {}).get("log_level", "INFO")

    # Load sources configuration
    sources_file = config_dir / cfg.get("sources_file", "config/sources.yaml")

    try:
        sources_config = load_sources_config(sources_file)
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Load selection criteria
    selection_file = config_dir / cfg.get(
        "selection_file", "config/selection-criteria.yaml"
    )
    if skip_selection:
        logger.info("Selection criteria filtering DISABLED")
        selection_criteria = None
    else:
        selection_criteria = load_selection_criteria(selection_file)

    logger.info("Massalia Events Crawler starting...")

    if dry_run:
        click.echo(click.style("DRY RUN MODE - No files will be written", fg="yellow"))

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

    # Initialize deduplicator for cross-source duplicate detection
    deduplicator = EventDeduplicator(content_dir=output_dir)
    logger.info(f"Deduplicator initialized: {deduplicator.get_stats()}")

    markdown_generator = MarkdownGenerator(
        output_dir=output_dir,
        dry_run=dry_run,
        deduplicator=deduplicator,
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

    # Process each source with progress display
    total_events = 0
    total_accepted = 0
    total_rejected = 0
    total_errors = 0
    sources_processed = 0
    sources_total = len(sources_list)

    for i, src in enumerate(sources_list, 1):
        if _interrupted:
            click.echo(
                click.style(
                    f"\nInterrupted after {sources_processed} sources", fg="yellow"
                )
            )
            break

        if not src.enabled:
            logger.debug(f"Skipping disabled source: {src.name}")
            continue

        # Progress display
        click.echo(f"\n[{i}/{sources_total}] Processing: {src.name} ({src.id})")
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
            "selection_criteria": selection_criteria,
        }

        try:
            parser_class = get_parser(src.parser)
            parser = parser_class(
                config=source_cfg,
                http_client=http_client,
                image_downloader=image_downloader,
                markdown_generator=markdown_generator,
                max_workers=concurrency,
            )

            events = parser.crawl()
            event_count = len(events)
            total_events += event_count
            sources_processed += 1

            # Track selection stats if available
            if hasattr(parser, "selection_stats"):
                stats = parser.selection_stats
                accepted = stats.get("accepted", event_count)
                rejected = stats.get("rejected", 0)
                total_accepted += accepted
                total_rejected += rejected
                click.echo(f"    -> {accepted} accepted, {rejected} rejected")
            else:
                total_accepted += event_count
                click.echo(f"    -> {event_count} events found")

        except ValueError as e:
            logger.warning(f"Parser not available for {src.name}: {e}")
            total_errors += 1
        except Exception as e:
            logger.error(f"Error processing {src.name}: {e}")
            total_errors += 1
            if effective_log_level == "DEBUG":
                logger.exception("Full traceback:")

    # Summary
    click.echo("\n" + "=" * 50)
    click.echo(click.style("CRAWL SUMMARY", bold=True))
    click.echo("=" * 50)
    click.echo(f"  Sources processed:  {sources_processed}/{sources_total}")
    click.echo(f"  Events accepted:    {total_accepted}")
    click.echo(f"  Events rejected:    {total_rejected}")
    click.echo(f"  Errors:             {total_errors}")
    click.echo("=" * 50)

    if dry_run:
        click.echo(click.style("\nDRY RUN - No files were written", fg="yellow"))

    # Save status
    save_status(
        config_dir,
        {
            "sources_processed": sources_processed,
            "sources_total": sources_total,
            "events_accepted": total_accepted,
            "events_rejected": total_rejected,
            "errors": total_errors,
            "dry_run": dry_run,
            "interrupted": _interrupted,
        },
    )

    # Exit code
    if _interrupted:
        sys.exit(130)  # Standard exit code for SIGINT
    elif total_errors > 0:
        sys.exit(1)
    else:
        sys.exit(0)


@cli.command("list-sources")
@click.pass_context
def list_sources(ctx):
    """
    List all configured event sources.

    Shows source ID, name, and enabled status for each configured source.
    """
    cfg = ctx.obj["config"]
    config_dir = ctx.obj["config_dir"]

    # Load sources configuration
    sources_file = config_dir / cfg.get("sources_file", "config/sources.yaml")

    try:
        sources_config = load_sources_config(sources_file)
    except ConfigurationError as e:
        click.echo(click.style(f"Configuration error: {e}", fg="red"), err=True)
        sys.exit(1)

    click.echo("\nConfigured sources:")
    click.echo("-" * 70)
    click.echo(f"{'ID':<20} {'NAME':<30} {'STATUS':<10} {'PARSER':<15}")
    click.echo("-" * 70)

    for src in sources_config.sources:
        status = (
            click.style("enabled", fg="green")
            if src.enabled
            else click.style("disabled", fg="red")
        )
        click.echo(f"{src.id:<20} {src.name:<30} {status:<19} {src.parser:<15}")

    click.echo("-" * 70)
    enabled_count = len(sources_config.get_enabled_sources())
    total_count = len(sources_config.sources)
    click.echo(f"Total: {total_count} sources ({enabled_count} enabled)")


@cli.command()
@click.pass_context
def validate(ctx):
    """
    Validate configuration files.

    Checks config.yaml, sources.yaml, and selection-criteria.yaml for errors.
    Reports any validation issues found.
    """
    cfg = ctx.obj["config"]
    config_path = ctx.obj["config_path"]
    config_dir = ctx.obj["config_dir"]

    errors = []
    warnings = []

    click.echo("\nValidating configuration files...\n")

    # 1. Validate main config.yaml
    click.echo(f"  Checking {config_path.name}...")
    required_keys = ["sources_file"]
    for key in required_keys:
        if key not in cfg:
            errors.append(f"Missing required key in config.yaml: {key}")

    # Check optional but recommended keys
    recommended_keys = ["output_dir", "image_dir", "http", "logging"]
    for key in recommended_keys:
        if key not in cfg:
            warnings.append(f"Missing recommended key in config.yaml: {key}")

    if not errors:
        click.echo(click.style("    ✓ config.yaml is valid", fg="green"))

    # 2. Validate sources.yaml
    sources_file = config_dir / cfg.get("sources_file", "config/sources.yaml")
    click.echo(f"  Checking {sources_file.name}...")

    if not sources_file.exists():
        errors.append(f"Sources file not found: {sources_file}")
    else:
        try:
            with open(sources_file, encoding="utf-8") as f:
                sources_cfg = yaml.safe_load(f)

            # Validate against schema
            try:
                validate_sources_config(sources_cfg, sources_file.parent)
                click.echo(click.style("    ✓ sources.yaml is valid", fg="green"))
            except ConfigurationError as e:
                errors.append(f"Sources validation error: {e}")

            # Check for valid parser names
            from src.parsers import PARSERS

            for source in sources_cfg.get("sources", []):
                parser_name = source.get("parser")
                if parser_name and parser_name not in PARSERS:
                    warnings.append(
                        f"Unknown parser '{parser_name}' for source '{source.get('id')}'"
                    )

        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML in sources.yaml: {e}")

    # 3. Validate selection-criteria.yaml
    selection_file = config_dir / cfg.get(
        "selection_file", "config/selection-criteria.yaml"
    )
    click.echo(f"  Checking {selection_file.name}...")

    if not selection_file.exists():
        warnings.append(f"Selection criteria file not found: {selection_file}")
        click.echo(click.style("    ! File not found (using defaults)", fg="yellow"))
    else:
        try:
            with open(selection_file, encoding="utf-8") as f:
                selection_cfg = yaml.safe_load(f)

            if selection_cfg:
                click.echo(
                    click.style("    ✓ selection-criteria.yaml is valid", fg="green")
                )
            else:
                warnings.append("Selection criteria file is empty")
                click.echo(
                    click.style("    ! File is empty (using defaults)", fg="yellow")
                )

        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML in selection-criteria.yaml: {e}")

    # 4. Check output directories
    click.echo("  Checking output directories...")
    output_dir = config_dir / cfg.get("output_dir", "../content/events")
    image_dir = config_dir / cfg.get("image_dir", "../static/images/events")

    for dir_path, name in [(output_dir, "output_dir"), (image_dir, "image_dir")]:
        if dir_path.exists():
            click.echo(click.style(f"    ✓ {name} exists: {dir_path}", fg="green"))
        else:
            warnings.append(f"{name} does not exist: {dir_path}")
            click.echo(click.style(f"    ! {name} not found: {dir_path}", fg="yellow"))

    # Report results
    click.echo("\n" + "=" * 50)
    if errors:
        click.echo(click.style("VALIDATION FAILED", fg="red", bold=True))
        click.echo("=" * 50)
        click.echo("\nErrors:")
        for error in errors:
            click.echo(click.style(f"  ✗ {error}", fg="red"))
    else:
        click.echo(click.style("VALIDATION PASSED", fg="green", bold=True))
        click.echo("=" * 50)

    if warnings:
        click.echo("\nWarnings:")
        for warning in warnings:
            click.echo(click.style(f"  ! {warning}", fg="yellow"))

    click.echo()

    sys.exit(1 if errors else 0)


@cli.command()
@click.pass_context
def status(ctx):
    """
    Show last crawl results.

    Displays summary statistics from the most recent crawl run.
    """
    config_dir = ctx.obj["config_dir"]

    status_data = load_status(config_dir)

    if not status_data:
        click.echo("No previous crawl status found.")
        click.echo("Run 'python crawl.py run' to perform a crawl.")
        return

    click.echo("\n" + "=" * 50)
    click.echo(click.style("LAST CRAWL STATUS", bold=True))
    click.echo("=" * 50)

    timestamp = status_data.get("timestamp", "Unknown")
    click.echo(f"  Timestamp:          {timestamp}")
    click.echo(
        f"  Sources processed:  {status_data.get('sources_processed', 0)}/{status_data.get('sources_total', 0)}"
    )
    click.echo(f"  Events accepted:    {status_data.get('events_accepted', 0)}")
    click.echo(f"  Events rejected:    {status_data.get('events_rejected', 0)}")
    click.echo(f"  Errors:             {status_data.get('errors', 0)}")

    if status_data.get("dry_run"):
        click.echo(click.style("  Mode:               DRY RUN", fg="yellow"))

    if status_data.get("interrupted"):
        click.echo(click.style("  Status:             INTERRUPTED", fg="yellow"))
    elif status_data.get("errors", 0) > 0:
        click.echo(click.style("  Status:             COMPLETED WITH ERRORS", fg="red"))
    else:
        click.echo(click.style("  Status:             SUCCESS", fg="green"))

    click.echo("=" * 50)


@cli.command()
@click.option(
    "--before",
    "-b",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Clean events before this date (default: today)",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    default=False,
    help="Preview what would be cleaned without making changes",
)
@click.option(
    "--delete",
    is_flag=True,
    default=False,
    help="Delete files instead of marking as expired",
)
@click.pass_context
def clean(ctx, before: datetime | None, dry_run: bool, delete: bool):
    """
    Clean up expired events.

    Marks events with dates before the specified date as expired,
    or optionally deletes them. By default, cleans events before today.
    """
    cfg = ctx.obj["config"]
    config_dir = ctx.obj["config_dir"]

    # Setup logging
    setup_logging_from_config(
        cfg, config_dir, ctx.obj["log_level"], ctx.obj["log_file"]
    )
    logger = get_logger(__name__)

    # Default to today
    if before is None:
        before = datetime.now(PARIS_TZ)
    else:
        before = before.replace(tzinfo=PARIS_TZ)

    # Get output directory
    output_dir = config_dir / cfg.get("output_dir", "../content/events")

    if not output_dir.exists():
        click.echo(
            click.style(f"Output directory not found: {output_dir}", fg="red"), err=True
        )
        sys.exit(1)

    click.echo(f"\nCleaning events before: {before.strftime('%Y-%m-%d')}")
    if dry_run:
        click.echo(click.style("DRY RUN MODE - No changes will be made", fg="yellow"))

    # Find all markdown files
    md_files = list(output_dir.rglob("*.md"))
    cleaned_count = 0
    error_count = 0

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")

            # Parse front matter
            if not content.startswith("---"):
                continue

            end_index = content.index("---", 3)
            front_matter = yaml.safe_load(content[3:end_index])
            body = content[end_index + 3 :]

            # Skip files with invalid front matter
            if not front_matter or not isinstance(front_matter, dict):
                continue

            # Check if already expired
            if front_matter.get("expired", False):
                continue

            # Get event date from front matter
            date_str = front_matter.get("date")
            if not date_str:
                continue

            # Parse date - handle both string and datetime
            if isinstance(date_str, datetime):
                event_date = date_str
            else:
                event_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

            # Check if event is before cutoff
            if event_date.date() >= before.date():
                continue

            # Event should be cleaned
            event_name = front_matter.get("name", md_file.stem)

            if delete:
                if dry_run:
                    click.echo(f"  [DRY RUN] Would delete: {md_file.name}")
                else:
                    md_file.unlink()
                    click.echo(f"  Deleted: {md_file.name}")
                    logger.info(f"Deleted expired event: {event_name}")
            else:
                if dry_run:
                    click.echo(f"  [DRY RUN] Would mark expired: {md_file.name}")
                else:
                    # Mark as expired
                    front_matter["expired"] = True
                    new_content = (
                        "---\n"
                        + yaml.dump(
                            front_matter, allow_unicode=True, default_flow_style=False
                        )
                        + "---"
                        + body
                    )
                    md_file.write_text(new_content, encoding="utf-8")
                    click.echo(f"  Marked expired: {md_file.name}")
                    logger.info(f"Marked event as expired: {event_name}")

            cleaned_count += 1

        except Exception as e:
            logger.error(f"Error processing {md_file}: {e}")
            error_count += 1

    # Summary
    click.echo("\n" + "=" * 50)
    action = "deleted" if delete else "marked expired"
    if dry_run:
        click.echo(f"Would have {action}: {cleaned_count} events")
    else:
        click.echo(f"Events {action}: {cleaned_count}")
    if error_count > 0:
        click.echo(click.style(f"Errors: {error_count}", fg="red"))
    click.echo("=" * 50)


if __name__ == "__main__":
    cli()
