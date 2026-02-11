#!/usr/bin/env python3
"""
Generate Hugo location pages for venues from venues.yaml.

Uses VenueManager to discover new location slugs referenced in event
markdown files, appends stub entries to venues.yaml, and creates
content/locations/[slug]/_index.fr.md pages.

Usage:
    python scripts/generate-venue-pages.py              # Generate all pages
    python scripts/generate-venue-pages.py --dry-run    # Preview without writing
"""

import argparse
import sys
from pathlib import Path

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENUES_FILE = PROJECT_ROOT / "crawler" / "data" / "venues.yaml"
LOCATIONS_DIR = PROJECT_ROOT / "content" / "locations"
EVENTS_DIR = PROJECT_ROOT / "content" / "events"

# Add crawler to path so we can import VenueManager
sys.path.insert(0, str(PROJECT_ROOT / "crawler"))

from src.venue_manager import VenueManager  # noqa: E402


def generate_page_content(venue: dict) -> str:
    """Generate the _index.fr.md content for a venue."""
    title = venue.get("title", "")
    description = venue.get("description", "")
    address = venue.get("address", "")
    website = venue.get("website", "")
    venue_type = venue.get("type", "Salle de spectacle")
    aliases = venue.get("aliases", [])
    body = venue.get("body", "")

    # Build YAML front matter
    lines = [
        "---",
        f'title: "{title}"',
        f'description: "{description}"',
        "",
        "# Informations du lieu",
        f'address: "{address}"',
        f'website: "{website}"',
        f'type: "{venue_type}"',
        "",
        "# Aliases pour le crawler (variations du nom)",
        "aliases:",
    ]

    for alias in aliases or []:
        lines.append(f'  - "{alias}"')

    lines.append("---")
    lines.append("")

    if body:
        lines.append(body)
        lines.append("")

    return "\n".join(lines)


def generate_venue_pages(venues: list[dict], dry_run: bool = False) -> tuple[int, int]:
    """Generate location pages for all venues.

    Args:
        venues: List of venue dicts from venues.yaml
        dry_run: If True, only print what would be created

    Returns:
        Tuple of (created, skipped) counts
    """
    created = 0
    skipped = 0

    for venue in venues:
        slug = venue.get("slug", "")
        if not slug:
            continue

        venue_dir = LOCATIONS_DIR / slug
        page_path = venue_dir / "_index.fr.md"

        if page_path.exists():
            print(f"  SKIP  {slug}/ (already exists)")
            skipped += 1
            continue

        content = generate_page_content(venue)

        if dry_run:
            print(f"  DRY   {slug}/")
            print(f"        title: {venue.get('title', '')}")
            print(f"        type: {venue.get('type', 'Salle de spectacle')}")
        else:
            venue_dir.mkdir(parents=True, exist_ok=True)
            page_path.write_text(content, encoding="utf-8")
            print(f"  CREATE {slug}/")

        created += 1

    return created, skipped


def main():
    parser = argparse.ArgumentParser(
        description="Generate Hugo location pages for venues"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without creating files",
    )
    parser.add_argument(
        "--venues-file",
        type=Path,
        default=VENUES_FILE,
        help=f"Path to venues YAML file (default: {VENUES_FILE})",
    )
    args = parser.parse_args()

    print(f"Loading venues from: {args.venues_file}")
    vm = VenueManager(args.venues_file)
    print(f"Found {len(vm.venues)} venues in venues.yaml")
    print()

    # Step 1: Discover new location slugs from event files
    print("Scanning event files for new location slugs...")
    new_slugs = vm.discover_unmapped(EVENTS_DIR)
    if new_slugs:
        print(f"  Found {len(new_slugs)} new slug(s):")
        for slug in new_slugs:
            action = "DRY" if args.dry_run else "ADD"
            print(f"    {action}  {slug}")

        if not args.dry_run:
            vm.append_stubs(new_slugs)
        print()
    else:
        print("  No new slugs found.")
        print()

    # Step 2: Generate Hugo location pages
    if args.dry_run:
        print("DRY RUN - no files will be written")
        print()

    created, skipped = generate_venue_pages(vm.venues, dry_run=args.dry_run)

    print()
    print(
        f"Venues discovered: {len(new_slugs)}, "
        f"Pages created: {created}, Pages skipped: {skipped}"
    )


if __name__ == "__main__":
    main()
