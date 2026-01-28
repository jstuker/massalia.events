#!/usr/bin/env python3
"""
Generate Hugo location pages for venues from venues.yaml.

Reads venue data from crawler/data/venues.yaml and creates
content/locations/[slug]/_index.fr.md pages following the
existing location page format.

Usage:
    python scripts/generate-venue-pages.py              # Generate all pages
    python scripts/generate-venue-pages.py --dry-run    # Preview without writing
"""

import argparse
import sys
from pathlib import Path

import yaml

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENUES_FILE = PROJECT_ROOT / "crawler" / "data" / "venues.yaml"
LOCATIONS_DIR = PROJECT_ROOT / "content" / "locations"


def load_venues(venues_path: Path) -> list[dict]:
    """Load venue data from YAML file."""
    if not venues_path.exists():
        print(f"Error: venues file not found: {venues_path}")
        sys.exit(1)

    with open(venues_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, list):
        print(f"Error: venues.yaml must contain a list of venues")
        sys.exit(1)

    return data


def generate_page_content(venue: dict) -> str:
    """Generate the _index.fr.md content for a venue."""
    title = venue["title"]
    description = venue["description"]
    address = venue.get("address", "")
    arrondissement = venue.get("arrondissement", "")
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
        f'arrondissement: "{arrondissement}"',
        f'website: "{website}"',
        f'type: "{venue_type}"',
        "",
        "# Aliases pour le crawler (variations du nom)",
        "aliases:",
    ]

    for alias in aliases:
        lines.append(f'  - "{alias}"')

    lines.append("---")
    lines.append("")

    if body:
        lines.append(body)
        lines.append("")

    return "\n".join(lines)


def generate_venue_pages(venues: list[dict], dry_run: bool = False) -> int:
    """Generate location pages for all venues.

    Args:
        venues: List of venue dicts from venues.yaml
        dry_run: If True, only print what would be created

    Returns:
        Number of pages created
    """
    created = 0
    skipped = 0

    for venue in venues:
        slug = venue["slug"]
        venue_dir = LOCATIONS_DIR / slug
        page_path = venue_dir / "_index.fr.md"

        if page_path.exists():
            print(f"  SKIP  {slug}/ (already exists)")
            skipped += 1
            continue

        content = generate_page_content(venue)

        if dry_run:
            print(f"  DRY   {slug}/")
            print(f"        title: {venue['title']}")
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
    venues = load_venues(args.venues_file)
    print(f"Found {len(venues)} venues")
    print()

    if args.dry_run:
        print("DRY RUN - no files will be created")
        print()

    created, skipped = generate_venue_pages(venues, dry_run=args.dry_run)

    print()
    print(f"Created: {created}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
