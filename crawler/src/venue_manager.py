"""Venue manager - single source of truth for venue data and name-to-slug mappings.

Loads venues from venues.yaml and builds a lookup table for mapping raw
location names (from event sources) to canonical venue slugs.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from .logger import get_logger

logger = get_logger(__name__)

# French articles to strip when generating lookup variants
FRENCH_ARTICLES = {"le", "la", "les", "l", "un", "une", "des", "du", "de", "d"}


def _strip_accents(text: str) -> str:
    """Remove accents from text (e->e, u->u, etc.)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip accents, collapse whitespace."""
    text = text.lower().strip()
    # Replace ligatures before accent stripping (NFKD doesn't decompose these)
    text = text.replace("\u0153", "oe")  # œ -> oe
    text = text.replace("\u00e6", "ae")  # æ -> ae
    text = _strip_accents(text)
    # Replace hyphens, apostrophes, special chars with spaces
    text = re.sub(r"[-\u2019\u2018'`]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = " ".join(text.split())
    return text


def _slug_to_words(slug: str) -> str:
    """Convert a slug to space-separated words: 'le-cepac-silo' -> 'le cepac silo'."""
    return slug.replace("-", " ")


def _extract_alias_slug(alias_path: str) -> str:
    """Extract slug from Hugo alias path: '/locations/foo/' -> 'foo'."""
    parts = alias_path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "locations":
        return parts[1]
    return ""


def _strip_articles(text: str) -> str:
    """Strip leading French articles from normalized text."""
    words = text.split()
    while words and words[0] in FRENCH_ARTICLES:
        words.pop(0)
    return " ".join(words)


@dataclass
class VenueDuplicateResult:
    """A pair of venues that may be duplicates."""

    slug_a: str
    slug_b: str
    similarity: float
    match_type: str  # "name", "address", "website"


@dataclass
class VenueAuditResult:
    """Results of a venue audit."""

    missing_fields: list[dict] = field(default_factory=list)
    duplicates: list[VenueDuplicateResult] = field(default_factory=list)
    unmapped_locations: list[str] = field(default_factory=list)
    total_venues: int = 0


class VenueManager:
    """Single source of truth for venue data and name-to-slug mappings.

    Loads venues from venues.yaml and builds a lookup table from:
    - Venue title (normalized, accent-stripped)
    - Venue slug (as hyphen-separated words)
    - Hugo aliases (extract slug from /locations/foo/ paths)
    - search_names entries (explicit name variants)
    - Auto-generated variants (accent-stripped, article-stripped)

    Matching uses exact match first, then substring match (longest key first).
    """

    def __init__(self, venues_path: Path | str | None = None):
        if venues_path is None:
            venues_path = Path(__file__).parent.parent / "data" / "venues.yaml"
        self.venues_path = Path(venues_path)
        self.venues: list[dict] = []
        self._lookup: dict[str, str] = {}  # normalized_key -> slug
        self._sorted_keys: list[str] = []  # keys sorted by length desc

        self._load()
        self._build_lookup()

    def _load(self) -> None:
        """Load venues from YAML file."""
        if not self.venues_path.exists():
            logger.warning(f"Venues file not found: {self.venues_path}")
            return

        with open(self.venues_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if isinstance(data, list):
            self.venues = data
        else:
            logger.warning(f"Unexpected venues data format: {type(data)}")

    def _build_lookup(self) -> None:
        """Build name-to-slug lookup table from venue data."""
        lookup: dict[str, str] = {}

        for venue in self.venues:
            slug = venue.get("slug", "")
            if not slug:
                continue

            title = venue.get("title", "")
            aliases = venue.get("aliases", [])
            search_names = venue.get("search_names", [])

            keys: set[str] = set()

            # 1. Slug as words: "le-cepac-silo" -> "le cepac silo"
            keys.add(_slug_to_words(slug))

            # 2. Title (normalized)
            if title:
                norm_title = _normalize(title)
                keys.add(norm_title)
                # Article-stripped title
                stripped = _strip_articles(norm_title)
                if stripped and stripped != norm_title:
                    keys.add(stripped)

            # 3. Aliases: extract slug from /locations/foo/ paths
            for alias in aliases or []:
                alias_slug = _extract_alias_slug(alias)
                if alias_slug:
                    alias_words = _slug_to_words(alias_slug)
                    keys.add(alias_words)
                    # Accent-stripped version of alias
                    stripped_alias = _strip_accents(alias_words)
                    if stripped_alias != alias_words:
                        keys.add(stripped_alias)

            # 4. Explicit search_names
            for search_name in search_names or []:
                keys.add(_normalize(search_name))

            # 5. Generate accent-stripped variants of all keys
            accent_variants = set()
            for key in keys:
                stripped = _strip_accents(key)
                if stripped != key:
                    accent_variants.add(stripped)
            keys.update(accent_variants)

            # Add all keys to lookup (first venue wins on collision)
            for key in keys:
                if not key:
                    continue
                if key not in lookup:
                    lookup[key] = slug
                elif lookup[key] != slug:
                    logger.debug(
                        f"Lookup key '{key}' already maps to '{lookup[key]}', "
                        f"skipping '{slug}'"
                    )

        self._lookup = lookup
        # Sort keys by length (longest first) for substring matching
        self._sorted_keys = sorted(lookup.keys(), key=len, reverse=True)

        logger.info(
            f"Built venue lookup: {len(self.venues)} venues, {len(self._lookup)} keys"
        )

    def map_location(self, raw_name: str) -> str:
        """Map a raw location name to a canonical venue slug.

        Tries exact match first, then substring match (longest key first
        to avoid false positives from short keys).

        Args:
            raw_name: Raw location name from event source (or already-slugified)

        Returns:
            Canonical venue slug, or raw_name unchanged if no match
        """
        if not raw_name:
            return raw_name

        normalized = _normalize(raw_name)

        # 1. Exact match
        if normalized in self._lookup:
            return self._lookup[normalized]

        # 2. Substring match (longest key first)
        for key in self._sorted_keys:
            if key in normalized:
                return self._lookup[key]

        # No match - return as-is
        return raw_name

    def get_venue(self, slug: str) -> dict | None:
        """Get venue data by slug."""
        for venue in self.venues:
            if venue.get("slug") == slug:
                return venue
        return None

    def get_all_slugs(self) -> set[str]:
        """Get all known venue slugs."""
        return {v["slug"] for v in self.venues if v.get("slug")}

    def find_duplicates(self, threshold: float = 0.85) -> list[VenueDuplicateResult]:
        """Find potential duplicate venues using name/address/website similarity.

        Args:
            threshold: Minimum similarity score to report (0.0-1.0)

        Returns:
            List of potential duplicate pairs
        """
        duplicates = []

        for i in range(len(self.venues)):
            for j in range(i + 1, len(self.venues)):
                a = self.venues[i]
                b = self.venues[j]

                slug_a = a.get("slug", "")
                slug_b = b.get("slug", "")

                # Name similarity
                name_a = _normalize(a.get("title", ""))
                name_b = _normalize(b.get("title", ""))
                if name_a and name_b:
                    name_sim = SequenceMatcher(None, name_a, name_b).ratio()
                    if name_sim >= threshold:
                        duplicates.append(
                            VenueDuplicateResult(
                                slug_a=slug_a,
                                slug_b=slug_b,
                                similarity=name_sim,
                                match_type="name",
                            )
                        )
                        continue

                # Address similarity
                addr_a = _normalize(a.get("address", ""))
                addr_b = _normalize(b.get("address", ""))
                if addr_a and addr_b and len(addr_a) > 10 and len(addr_b) > 10:
                    addr_sim = SequenceMatcher(None, addr_a, addr_b).ratio()
                    if addr_sim >= threshold:
                        duplicates.append(
                            VenueDuplicateResult(
                                slug_a=slug_a,
                                slug_b=slug_b,
                                similarity=addr_sim,
                                match_type="address",
                            )
                        )
                        continue

                # Website domain match
                web_a = a.get("website", "")
                web_b = b.get("website", "")
                if web_a and web_b:
                    domain_a = _extract_domain(web_a)
                    domain_b = _extract_domain(web_b)
                    if domain_a and domain_b and domain_a == domain_b:
                        duplicates.append(
                            VenueDuplicateResult(
                                slug_a=slug_a,
                                slug_b=slug_b,
                                similarity=1.0,
                                match_type="website",
                            )
                        )

        return duplicates

    def discover_unmapped(self, events_dir: Path | str) -> list[str]:
        """Scan event frontmatter for location slugs not in venues.yaml.

        Args:
            events_dir: Path to Hugo content/events directory

        Returns:
            Sorted list of unknown location slugs
        """
        events_dir = Path(events_dir)
        known_slugs = self.get_all_slugs()
        # Also include alias slugs as known
        for venue in self.venues:
            for alias in venue.get("aliases", []) or []:
                alias_slug = _extract_alias_slug(alias)
                if alias_slug:
                    known_slugs.add(alias_slug)

        unknown_slugs: set[str] = set()
        for md_file in events_dir.rglob("*.fr.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
                if not text.startswith("---"):
                    continue
                end = text.index("---", 3)
                front_matter = yaml.safe_load(text[3:end])
                if front_matter and isinstance(front_matter.get("locations"), list):
                    for loc in front_matter["locations"]:
                        if loc and loc not in known_slugs:
                            unknown_slugs.add(loc)
            except Exception:
                continue

        return sorted(unknown_slugs)

    def audit(self, events_dir: Path | str) -> VenueAuditResult:
        """Run comprehensive venue audit.

        Args:
            events_dir: Path to Hugo content/events directory

        Returns:
            VenueAuditResult with missing fields, duplicates, unmapped locations
        """
        required_fields = ["title", "description", "address", "website"]
        missing_fields = []
        for venue in self.venues:
            slug = venue.get("slug", "unknown")
            missing = [f for f in required_fields if not venue.get(f)]
            if missing:
                missing_fields.append({"slug": slug, "fields": missing})

        duplicates = self.find_duplicates()
        unmapped = self.discover_unmapped(events_dir)

        return VenueAuditResult(
            missing_fields=missing_fields,
            duplicates=duplicates,
            unmapped_locations=unmapped,
            total_venues=len(self.venues),
        )

    def add_venue(self, venue_dict: dict) -> None:
        """Add a venue to the in-memory list and rebuild lookup.

        Args:
            venue_dict: Venue data dict with at minimum a 'slug' key
        """
        self.venues.append(venue_dict)
        self._build_lookup()

    def append_stubs(self, new_slugs: list[str]) -> list[dict]:
        """Append stub venue entries for new slugs to venues.yaml.

        Args:
            new_slugs: List of slugs to add as stubs

        Returns:
            List of new venue dicts that were added
        """
        new_venues = []
        for slug in new_slugs:
            venue = {
                "slug": slug,
                "title": _slug_to_title(slug),
                "description": "",
                "address": "",
                "website": "",
                "type": "Lieu",
                "aliases": [],
                "body": "",
            }
            new_venues.append(venue)
            self.venues.append(venue)

        if new_venues:
            with open(self.venues_path, "a", encoding="utf-8") as f:
                f.write(
                    "\n# ============================================================\n"
                    "# Auto-discovered venues (stub entries -- fill in details)\n"
                    "# ============================================================\n\n"
                )
                for venue in new_venues:
                    f.write(f"- slug: {venue['slug']}\n")
                    f.write(f'  title: "{venue["title"]}"\n')
                    f.write('  description: ""\n')
                    f.write('  address: ""\n')
                    f.write('  website: ""\n')
                    f.write('  type: "Lieu"\n')
                    f.write("  aliases: []\n")
                    f.write('  body: ""\n\n')

            self._build_lookup()

        return new_venues


def _extract_domain(url: str) -> str:
    """Extract domain from URL for comparison."""
    url = url.lower().strip()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    return url.split("/")[0]


def _slug_to_title(slug: str) -> str:
    """Convert a slug to a human-readable title.

    E.g. 'theatre-des-calanques' -> 'Theatre des Calanques'
    """
    minor_words = {
        "de",
        "des",
        "du",
        "d",
        "la",
        "le",
        "les",
        "l",
        "et",
        "en",
        "a",
        "au",
        "aux",
    }
    words = slug.split("-")
    titled = []
    for i, word in enumerate(words):
        if i == 0 or word not in minor_words:
            titled.append(word.capitalize())
        else:
            titled.append(word)
    return " ".join(titled)
