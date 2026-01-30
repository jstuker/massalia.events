#!/usr/bin/env python3
"""
Generate Hugo location pages for venues from venues.yaml.

First discovers any new location slugs referenced in event markdown
files that are missing from venues.yaml, and appends stub entries
for them. Then creates content/locations/[slug]/_index.fr.md pages
following the existing location page format.

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
EVENTS_DIR = PROJECT_ROOT / "content" / "events"


def slug_to_title(slug: str) -> str:
    """Convert a slug to a human-readable title.

    E.g. 'theatre-des-calanques' -> 'Theatre des Calanques'
    """
    minor_words = {
        "de", "des", "du", "d", "la", "le", "les", "l", "et", "en", "a", "au", "aux",
    }
    words = slug.split("-")
    titled = []
    for i, word in enumerate(words):
        if i == 0 or word not in minor_words:
            titled.append(word.capitalize())
        else:
            titled.append(word)
    return " ".join(titled)


def collect_event_location_slugs(events_dir: Path) -> set[str]:
    """Scan all event markdown files and collect unique location slugs."""
    slugs = set()
    for md_file in events_dir.rglob("*.fr.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            end = text.index("---", 3)
            front_matter = yaml.safe_load(text[3:end])
            if front_matter and isinstance(front_matter.get("locations"), list):
                for loc in front_matter["locations"]:
                    if loc:
                        slugs.add(loc)
        except Exception:
            continue
    return slugs


def discover_new_slugs(venues: list[dict], events_dir: Path) -> list[str]:
    """Find location slugs used in events but missing from venues.yaml."""
    known_slugs = {v["slug"] for v in venues}
    event_slugs = collect_event_location_slugs(events_dir)
    return sorted(event_slugs - known_slugs)


def append_new_venues(
    venues_path: Path, new_slugs: list[str], dry_run: bool = False
) -> list[dict]:
    """Append stub venue entries for newly discovered slugs to venues.yaml.

    Returns the list of new venue dicts that were added.
    """
    new_venues = []
    for slug in new_slugs:
        new_venues.append({
            "slug": slug,
            "title": slug_to_title(slug),
            "description": "",
            "address": "",
            "arrondissement": "",
            "website": "",
            "type": "Lieu",
            "aliases": [],
            "body": "",
        })

    if new_venues and not dry_run:
        with open(venues_path, "a", encoding="utf-8") as f:
            f.write(
                "\n# ============================================================\n"
                "# Auto-discovered venues (stub entries — fill in details)\n"
                "# ============================================================\n\n"
            )
            for venue in new_venues:
                f.write(f"- slug: {venue['slug']}\n")
                f.write(f'  title: "{venue["title"]}"\n')
                f.write(f'  description: ""\n')
                f.write(f'  address: ""\n')
                f.write(f'  arrondissement: ""\n')
                f.write(f'  website: ""\n')
                f.write(f'  type: "Lieu"\n')
                f.write(f"  aliases: []\n")
                f.write(f'  body: ""\n\n')

    return new_venues


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
    print(f"Found {len(venues)} venues in venues.yaml")
    print()

    # Step 1: Discover new location slugs from event files
    print("Scanning event files for new location slugs...")
    new_slugs = discover_new_slugs(venues, EVENTS_DIR)
    if new_slugs:
        print(f"  Found {len(new_slugs)} new slug(s):")
        for slug in new_slugs:
            action = "DRY" if args.dry_run else "ADD"
            print(f"    {action}  {slug}")
        new_venues = append_new_venues(
            args.venues_file, new_slugs, dry_run=args.dry_run
        )
        venues.extend(new_venues)
        print()
    else:
        print("  No new slugs found.")
        print()

    # Step 2: Generate Hugo location pages
    if args.dry_run:
        print("DRY RUN - no files will be written")
        print()

    created, skipped = generate_venue_pages(venues, dry_run=args.dry_run)

    print()
    print(f"Venues discovered: {len(new_slugs)}, Pages created: {created}, Pages skipped: {skipped}")


if __name__ == "__main__":
    main()
