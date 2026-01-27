"""Duplicate event detection and merging."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING

import frontmatter

from .logger import get_logger

if TYPE_CHECKING:
    from .models.event import Event

logger = get_logger(__name__)


@dataclass
class DuplicateResult:
    """Result of duplicate detection check."""

    is_duplicate: bool
    confidence: float
    existing_file: Path | None
    match_reasons: list[str]
    should_merge: bool

    @property
    def is_near_duplicate(self) -> bool:
        """Check if this is a near-duplicate requiring manual review."""
        return 0.5 <= self.confidence < 0.7


@dataclass
class EventIndex:
    """Indexed event data for fast lookup."""

    path: Path
    name: str
    date: str
    start_time: str
    location: str
    event_url: str
    source_id: str
    description: str
    image: str | None


@dataclass
class MergeResult:
    """Result of merging duplicate event data."""

    updated: bool
    changes: list[str] = field(default_factory=list)


class EventDeduplicator:
    """
    Detect duplicate events across multiple sources.

    Uses multiple signals to identify duplicates:
    1. Exact booking URL match (highest confidence)
    2. Date + time + location match with similar name
    3. Very similar name on same date

    Provides merge functionality to combine information from
    duplicate sources into a single event.
    """

    # Confidence thresholds
    DUPLICATE_THRESHOLD = 0.7
    MERGE_THRESHOLD = 0.8
    NEAR_DUPLICATE_MIN = 0.5

    def __init__(self, content_dir: str | Path):
        """
        Initialize the deduplicator.

        Args:
            content_dir: Path to Hugo content/events directory
        """
        self.content_dir = Path(content_dir)
        self.event_index: dict[str, dict] = {
            "by_url": {},
            "by_date_location": {},
            "by_name": {},
        }
        self._build_index()

    def _build_index(self) -> None:
        """Build index of existing events for fast lookup."""
        if not self.content_dir.exists():
            logger.warning(f"Content directory not found: {self.content_dir}")
            return

        event_count = 0
        for md_file in self.content_dir.rglob("*.md"):
            # Skip index files
            if md_file.name.startswith("_"):
                continue

            try:
                event_data = self._load_event_file(md_file)
                if event_data:
                    self._index_event(event_data)
                    event_count += 1
            except Exception as e:
                logger.warning(f"Failed to index {md_file}: {e}")

        logger.info(
            f"Built event index: {event_count} events, "
            f"{len(self.event_index['by_url'])} URLs, "
            f"{len(self.event_index['by_date_location'])} date/location combos"
        )

    def _load_event_file(self, md_file: Path) -> EventIndex | None:
        """Load event data from markdown file."""
        post = frontmatter.load(md_file)

        # Get event name (try multiple field names for compatibility)
        name = post.get("name") or post.get("eventName") or post.get("title", "")
        if not name:
            return None

        # Get date
        date_val = post.get("date")
        if date_val:
            if isinstance(date_val, datetime):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val)[:10]
        else:
            date_str = ""

        # Get location (first from list)
        locations = post.get("locations", [])
        location = locations[0] if locations else ""

        return EventIndex(
            path=md_file,
            name=name,
            date=date_str,
            start_time=post.get("startTime", ""),
            location=location,
            event_url=post.get("eventURL", ""),
            source_id=post.get("sourceId", ""),
            description=post.get("description", ""),
            image=post.get("image"),
        )

    def _index_event(self, event: EventIndex) -> None:
        """Add event to all relevant indexes."""
        # Index by booking URL
        if event.event_url:
            url_key = self._normalize_url(event.event_url)
            self.event_index["by_url"][url_key] = event

        # Index by date + location
        if event.date and event.location:
            dl_key = self._date_location_key(
                event.date, event.start_time, event.location
            )
            if dl_key not in self.event_index["by_date_location"]:
                self.event_index["by_date_location"][dl_key] = []
            self.event_index["by_date_location"][dl_key].append(event)

        # Index by normalized name
        if event.name:
            name_key = self._normalize_name(event.name)
            if name_key not in self.event_index["by_name"]:
                self.event_index["by_name"][name_key] = []
            self.event_index["by_name"][name_key].append(event)

    def check_duplicate(self, event: "Event") -> DuplicateResult:
        """
        Check if event is a duplicate of an existing event.

        Args:
            event: Event to check

        Returns:
            DuplicateResult with duplicate status and confidence
        """
        reasons: list[str] = []
        confidence = 0.0
        existing: EventIndex | None = None

        # 1. Check booking URL (strongest signal - 95% confidence)
        if event.event_url:
            url_key = self._normalize_url(event.event_url)
            if url_key in self.event_index["by_url"]:
                existing = self.event_index["by_url"][url_key]
                reasons.append(f"Matching booking URL: {event.event_url}")
                confidence = 0.95
                logger.debug(f"URL match found: {event.event_url}")

        # 2. Check date + time + location
        if event.start_datetime and event.locations:
            date_str = event.start_datetime.strftime("%Y-%m-%d")
            time_str = event.start_datetime.strftime("%H:%M")
            location = event.locations[0] if event.locations else ""

            dl_key = self._date_location_key(date_str, time_str, location)
            if dl_key in self.event_index["by_date_location"]:
                matches = self.event_index["by_date_location"][dl_key]
                for match in matches:
                    # Skip if already matched by URL
                    if existing and match.path == existing.path:
                        continue

                    name_sim = self._name_similarity(event.name, match.name)
                    if name_sim > 0.7:
                        if confidence < 0.85:
                            existing = match
                            confidence = 0.85
                        reasons.append(
                            f"Same date/time/location + similar name ({name_sim:.0%})"
                        )
                        logger.debug(
                            f"Date/location match with similar name: {match.name}"
                        )
                    elif name_sim > 0.5:
                        if confidence < 0.6:
                            confidence = max(confidence, 0.6)
                            existing = match
                        reasons.append(
                            f"Same date/time/location, moderate name similarity ({name_sim:.0%})"
                        )

        # 3. Check similar names on same date (weaker signal)
        if event.name and event.start_datetime and confidence < 0.8:
            name_key = self._normalize_name(event.name)
            date_str = event.start_datetime.strftime("%Y-%m-%d")

            if name_key in self.event_index["by_name"]:
                for match in self.event_index["by_name"][name_key]:
                    # Skip if already matched
                    if existing and match.path == existing.path:
                        continue

                    if self._same_date(date_str, match.date):
                        name_sim = self._name_similarity(event.name, match.name)
                        if name_sim > 0.85:
                            if confidence < 0.75:
                                existing = match
                                confidence = 0.75
                            reasons.append(
                                f"Very similar name on same date ({name_sim:.0%})"
                            )
                            logger.debug(f"Name match on same date: {match.name}")

        is_duplicate = confidence >= self.DUPLICATE_THRESHOLD
        should_merge = is_duplicate and confidence >= self.MERGE_THRESHOLD

        if is_duplicate:
            logger.info(
                f"Duplicate detected: '{event.name}' "
                f"(confidence: {confidence:.0%}, reasons: {reasons})"
            )
        elif confidence >= self.NEAR_DUPLICATE_MIN:
            logger.info(
                f"Near-duplicate detected: '{event.name}' "
                f"(confidence: {confidence:.0%}, requires review)"
            )

        return DuplicateResult(
            is_duplicate=is_duplicate,
            confidence=confidence,
            existing_file=existing.path if existing else None,
            match_reasons=reasons,
            should_merge=should_merge,
        )

    def merge_event(self, existing_file: Path, new_event: "Event") -> MergeResult:
        """
        Merge new event data into existing event file.

        Strategy:
        - Keep existing event as primary
        - Fill missing description from new event
        - Fill missing image from new event
        - Add alternate source URL
        - Update lastCrawled timestamp

        Args:
            existing_file: Path to existing event markdown file
            new_event: New event with additional data

        Returns:
            MergeResult with update status and changes made
        """
        changes: list[str] = []

        try:
            post = frontmatter.load(existing_file)
        except Exception as e:
            logger.error(f"Failed to load {existing_file} for merge: {e}")
            return MergeResult(updated=False)

        # Fill missing description
        existing_desc = post.get("description", "")
        if not existing_desc and new_event.description:
            post["description"] = new_event.description
            changes.append("Added description from alternate source")

        # Fill missing image
        existing_image = post.get("image")
        if not existing_image and new_event.image:
            post["image"] = new_event.image
            changes.append("Added image from alternate source")

        # Track alternate source URLs
        alt_sources = post.get("alternateSources", [])
        if new_event.event_url and new_event.event_url not in alt_sources:
            existing_url = post.get("eventURL", "")
            if new_event.event_url != existing_url:
                alt_sources.append(new_event.event_url)
                post["alternateSources"] = alt_sources
                changes.append(f"Added alternate source: {new_event.event_url}")

        # Track source IDs
        if new_event.source_id:
            source_ids = post.get("sourceIds", [])
            existing_source = post.get("sourceId", "")
            if existing_source and existing_source not in source_ids:
                source_ids.append(existing_source)
            if new_event.source_id not in source_ids:
                source_ids.append(new_event.source_id)
                post["sourceIds"] = source_ids
                changes.append(f"Added source ID: {new_event.source_id}")

        # Update lastCrawled timestamp
        post["lastCrawled"] = datetime.now().isoformat()

        if changes:
            try:
                with open(existing_file, "w", encoding="utf-8") as f:
                    f.write(frontmatter.dumps(post))
                logger.info(f"Merged event data into {existing_file}: {changes}")
                return MergeResult(updated=True, changes=changes)
            except Exception as e:
                logger.error(f"Failed to write merged event to {existing_file}: {e}")
                return MergeResult(updated=False)

        return MergeResult(updated=False, changes=[])

    def refresh_index(self) -> None:
        """Rebuild the event index from content directory."""
        self.event_index = {
            "by_url": {},
            "by_date_location": {},
            "by_name": {},
        }
        self._build_index()

    def get_stats(self) -> dict[str, int]:
        """Get index statistics."""
        return {
            "total_urls": len(self.event_index["by_url"]),
            "total_date_locations": len(self.event_index["by_date_location"]),
            "total_names": len(self.event_index["by_name"]),
        }

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        url = url.lower().strip()
        # Remove protocol
        url = re.sub(r"^https?://", "", url)
        # Remove www.
        url = re.sub(r"^www\.", "", url)
        # Remove trailing slash
        url = url.rstrip("/")
        # Remove common tracking parameters
        url = re.sub(r"\?utm_.*$", "", url)
        url = re.sub(r"\?ref=.*$", "", url)
        return url

    def _normalize_name(self, name: str) -> str:
        """Normalize event name for indexing."""
        name = name.lower().strip()
        # Remove punctuation
        name = re.sub(r"[^\w\s]", "", name)
        # Normalize whitespace
        name = " ".join(name.split())
        return name

    def _date_location_key(self, date: str, time: str, location: str) -> str:
        """Generate key for date + time + location lookup."""
        # Normalize location
        loc_norm = self._normalize_name(location) if location else ""
        # Include time in key for precision
        return f"{date}|{time}|{loc_norm}"

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two event names."""
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)
        return SequenceMatcher(None, n1, n2).ratio()

    def _same_date(self, date1: str, date2: str) -> bool:
        """Check if two dates are the same."""
        # Compare just the date portion (YYYY-MM-DD)
        return date1[:10] == date2[:10] if date1 and date2 else False
