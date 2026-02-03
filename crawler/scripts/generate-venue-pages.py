#!/usr/bin/env python3
"""
Generate Hugo location pages from venues.yaml data.

This script reads venue data from data/venues.yaml and creates/updates
Hugo content pages under content/locations/[slug]/_index.fr.md.

Usage:
    python scripts/generate-venue-pages.py           # Update all venues
    python scripts/generate-venue-pages.py --dry-run # Preview changes
    python scripts/generate-venue-pages.py --force   # Overwrite existing pages
"""

import argparse
from pathlib import Path

import yaml


def load_venues(venues_file: Path) -> list[dict]:
    """Load venue data from YAML file."""
    with open(venues_file, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def generate_frontmatter(venue: dict) -> str:
    """Generate YAML front matter for a venue page."""
    lines = ["---"]

    # Required fields
    lines.append(f'title: "{venue.get("title", "")}"')
    lines.append(f'description: "{venue.get("description", "")}"')

    # Optional fields
    lines.append(f'address: "{venue.get("address", "")}"')
    lines.append(f'website: "{venue.get("website", "")}"')
    lines.append(f'type: "{venue.get("type", "Lieu")}"')

    # Aliases
    aliases = venue.get("aliases", [])
    if aliases:
        lines.append("aliases:")
        for alias in aliases:
            lines.append(f'  - "{alias}"')
    else:
        lines.append("aliases: []")

    lines.append("---")
    return "\n".join(lines)


def generate_page_content(venue: dict) -> str:
    """Generate full page content for a venue."""
    frontmatter = generate_frontmatter(venue)
    body = venue.get("body", "")

    if body:
        return f"{frontmatter}\n\n{body}\n"
    else:
        return f"{frontmatter}\n"


def update_venue_page(
    venue: dict,
    locations_dir: Path,
    dry_run: bool = False,
    force: bool = False,
) -> tuple[str, str]:
    """
    Update or create a venue page.

    Returns:
        Tuple of (action, message) where action is 'created', 'updated',
        'skipped', or 'unchanged'
    """
    slug = venue.get("slug")
    if not slug:
        return ("skipped", "No slug defined")

    page_dir = locations_dir / slug
    page_file = page_dir / "_index.fr.md"

    new_content = generate_page_content(venue)

    # Check if page exists
    if page_file.exists():
        existing_content = page_file.read_text(encoding="utf-8")

        # Check if content is different
        if existing_content.strip() == new_content.strip():
            return ("unchanged", str(page_file))

        # Page exists but content differs
        if not force:
            # Check if existing page has empty/stub content
            if is_stub_page(existing_content):
                action = "updated"
            else:
                return ("skipped", f"Page exists (use --force to overwrite): {page_file}")
        else:
            action = "updated"
    else:
        action = "created"

    if not dry_run:
        page_dir.mkdir(parents=True, exist_ok=True)
        page_file.write_text(new_content, encoding="utf-8")

    return (action, str(page_file))


def is_stub_page(content: str) -> bool:
    """Check if a page is a stub (has empty description or body)."""
    # Check for empty description
    if 'description: ""' in content:
        return True

    # Check for empty body (only frontmatter)
    lines = content.strip().split("\n")
    # Find the end of frontmatter
    in_frontmatter = False
    body_start = 0
    for i, line in enumerate(lines):
        if line == "---":
            if not in_frontmatter:
                in_frontmatter = True
            else:
                body_start = i + 1
                break

    # Check if there's any content after frontmatter
    body = "\n".join(lines[body_start:]).strip()
    return len(body) == 0


def main():
    parser = argparse.ArgumentParser(
        description="Generate Hugo location pages from venues.yaml"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing pages even if they have content",
    )
    parser.add_argument(
        "--venues-file",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "venues.yaml",
        help="Path to venues.yaml file",
    )
    parser.add_argument(
        "--locations-dir",
        type=Path,
        default=Path(__file__).parent.parent.parent / "content" / "locations",
        help="Path to content/locations directory",
    )
    args = parser.parse_args()

    # Load venues
    if not args.venues_file.exists():
        print(f"Error: Venues file not found: {args.venues_file}")
        return 1

    venues = load_venues(args.venues_file)
    print(f"Loaded {len(venues)} venues from {args.venues_file}")

    if args.dry_run:
        print("\n[DRY RUN] No files will be written\n")

    # Process each venue
    stats = {"created": 0, "updated": 0, "skipped": 0, "unchanged": 0}

    for venue in venues:
        action, message = update_venue_page(
            venue,
            args.locations_dir,
            dry_run=args.dry_run,
            force=args.force,
        )
        stats[action] += 1

        if action == "created":
            print(f"  [CREATE] {message}")
        elif action == "updated":
            print(f"  [UPDATE] {message}")
        elif action == "skipped":
            print(f"  [SKIP]   {message}")
        # Don't print unchanged to reduce noise

    # Summary
    print(f"\nSummary:")
    print(f"  Created:   {stats['created']}")
    print(f"  Updated:   {stats['updated']}")
    print(f"  Unchanged: {stats['unchanged']}")
    print(f"  Skipped:   {stats['skipped']}")

    return 0


if __name__ == "__main__":
    exit(main())
