"""Hugo markdown file generator."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from ..logger import get_logger
from ..utils.sanitize import sanitize_description

if TYPE_CHECKING:
    from ..deduplicator import EventDeduplicator
    from ..models.event import Event

logger = get_logger(__name__)


@dataclass
class GeneratorStats:
    """Statistics for generator operations."""

    created: int = 0
    updated: int = 0
    skipped_duplicate: int = 0
    skipped_exists: int = 0
    failed: int = 0

    def reset(self):
        """Reset all counters."""
        self.created = 0
        self.updated = 0
        self.skipped_duplicate = 0
        self.skipped_exists = 0
        self.failed = 0

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_exists": self.skipped_exists,
            "failed": self.failed,
        }

    @property
    def total_processed(self) -> int:
        """Total events processed."""
        return (
            self.created
            + self.updated
            + self.skipped_duplicate
            + self.skipped_exists
            + self.failed
        )


@dataclass
class GenerateResult:
    """Result of a single generate operation."""

    success: bool
    file_path: Path | None
    action: str  # "created", "updated", "skipped", "failed"
    reason: str = ""


class MarkdownGenerator:
    """
    Generate Hugo-compatible markdown files for events.

    Creates files following the Hugo content structure:
    - YAML front matter with event metadata
    - Date-based folder structure (YYYY/MM/DD)
    - French language suffix (.fr.md)

    Features:
    - Duplicate detection integration
    - Statistics tracking
    - Batch processing
    - Multi-day event support
    - Dry-run mode
    """

    def __init__(
        self,
        output_dir: Path,
        dry_run: bool = False,
        deduplicator: "EventDeduplicator | None" = None,
        skip_existing: bool = True,
    ):
        """
        Initialize the markdown generator.

        Args:
            output_dir: Base output directory for content files
            dry_run: If True, only log actions without writing files
            deduplicator: Optional deduplicator for duplicate checking
            skip_existing: If True, skip events that already have files
        """
        self.output_dir = Path(output_dir)
        self.dry_run = dry_run
        self.deduplicator = deduplicator
        self.skip_existing = skip_existing
        self.stats = GeneratorStats()

    def generate(
        self,
        event: "Event",
        check_duplicate: bool = True,
    ) -> GenerateResult:
        """
        Generate a markdown file for an event.

        Args:
            event: Event model instance
            check_duplicate: Whether to check for duplicates first

        Returns:
            GenerateResult with status and file path
        """
        file_path = self.output_dir / event.file_path
        logger.debug(f"Processing event: {event.name}")

        # Check for duplicates if deduplicator is available
        if check_duplicate and self.deduplicator:
            dup_result = self.deduplicator.check_duplicate(event)
            if dup_result.is_duplicate:
                if dup_result.should_merge:
                    # Merge into existing file
                    merge_result = self.deduplicator.merge_event(
                        dup_result.existing_file, event
                    )
                    if merge_result.updated:
                        self.stats.updated += 1
                        logger.info(
                            f"Merged duplicate: {event.name} -> {dup_result.existing_file}"
                        )
                        return GenerateResult(
                            success=True,
                            file_path=dup_result.existing_file,
                            action="updated",
                            reason=f"Merged: {', '.join(dup_result.match_reasons)}",
                        )
                # Skip duplicate
                self.stats.skipped_duplicate += 1
                logger.info(f"Skipped duplicate: {event.name}")
                return GenerateResult(
                    success=True,
                    file_path=dup_result.existing_file,
                    action="skipped",
                    reason=f"Duplicate: {', '.join(dup_result.match_reasons)}",
                )

        # Check if file already exists
        if self.skip_existing and file_path.exists():
            self.stats.skipped_exists += 1
            logger.debug(f"File already exists: {file_path}")
            return GenerateResult(
                success=True,
                file_path=file_path,
                action="skipped",
                reason="File already exists",
            )

        # Generate front matter
        front_matter = event.to_front_matter()

        # Sanitize description in front matter and body
        description = sanitize_description(event.description)
        if "description" in front_matter:
            front_matter["description"] = sanitize_description(
                front_matter["description"]
            )

        # Build file content
        content = self._build_content(front_matter, description)

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create: {file_path}")
            logger.debug(f"Content:\n{content}")
            self.stats.created += 1
            return GenerateResult(
                success=True,
                file_path=file_path,
                action="created",
                reason="Dry run",
            )

        try:
            self._write_file(file_path, content)
            self.stats.created += 1
            logger.info(f"Created: {file_path}")
            return GenerateResult(
                success=True,
                file_path=file_path,
                action="created",
            )
        except Exception as e:
            self.stats.failed += 1
            logger.error(f"Failed to create {file_path}: {e}")
            return GenerateResult(
                success=False,
                file_path=file_path,
                action="failed",
                reason=str(e),
            )

    def generate_batch(
        self,
        events: list["Event"],
        check_duplicate: bool = True,
    ) -> list[GenerateResult]:
        """
        Generate markdown files for multiple events.

        Args:
            events: List of Event instances
            check_duplicate: Whether to check for duplicates

        Returns:
            List of GenerateResult for each event
        """
        results = []
        for event in events:
            result = self.generate(event, check_duplicate=check_duplicate)
            results.append(result)

        self._log_summary()
        return results

    def generate_multi_day(
        self,
        base_event: "Event",
        dates: list[datetime],
        group_id: str | None = None,
    ) -> list[GenerateResult]:
        """
        Generate linked markdown files for a multi-day event.

        Creates separate files for each day with eventGroupId linking them.

        Args:
            base_event: Base event with common information
            dates: List of dates for the event
            group_id: Optional group ID (auto-generated if not provided)

        Returns:
            List of GenerateResult for each day
        """
        from ..models.event import Event, slugify

        if not dates:
            return []

        # Generate group ID if not provided
        if not group_id:
            group_id = f"{slugify(base_event.name)}-{dates[0].strftime('%Y%m')}"

        total_days = len(dates)
        results = []

        for i, event_date in enumerate(sorted(dates), start=1):
            # Create event for this day
            day_event = Event(
                name=base_event.name,
                event_url=base_event.event_url,
                start_datetime=datetime.combine(
                    event_date.date(),
                    base_event.start_datetime.time(),
                    tzinfo=base_event.start_datetime.tzinfo,
                ),
                description=base_event.description,
                image=base_event.image,
                categories=base_event.categories,
                locations=base_event.locations,
                tags=base_event.tags,
                event_group_id=group_id,
                day_of=f"Jour {i} sur {total_days}",
                source_id=f"{base_event.source_id}:day{i}"
                if base_event.source_id
                else None,
                draft=base_event.draft,
            )

            result = self.generate(day_event, check_duplicate=True)
            results.append(result)

        logger.info(
            f"Generated {len(results)} files for multi-day event: {base_event.name}"
        )
        return results

    def _build_content(self, front_matter: dict, body_content: str = "") -> str:
        """
        Build markdown file content with YAML front matter.

        Args:
            front_matter: Dictionary of front matter fields
            body_content: Optional markdown body content

        Returns:
            Complete markdown file content
        """
        # Use block style for lists, default flow style for simple values
        yaml_content = yaml.dump(
            front_matter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=1000,  # Prevent line wrapping
        )

        # Build final content
        content = f"---\n{yaml_content}---\n"

        # Add body content if provided
        if body_content:
            content += f"\n{body_content}\n"

        return content

    def _write_file(self, file_path: Path, content: str):
        """
        Write content to file, creating directories as needed.

        Args:
            file_path: Path to write to
            content: Content to write
        """
        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _log_summary(self):
        """Log a summary of generation statistics."""
        logger.info(
            f"Generation complete: "
            f"{self.stats.created} created, "
            f"{self.stats.updated} updated, "
            f"{self.stats.skipped_duplicate} duplicate, "
            f"{self.stats.skipped_exists} existing, "
            f"{self.stats.failed} failed"
        )

    def check_exists(self, event: "Event") -> bool:
        """
        Check if an event file already exists.

        Args:
            event: Event to check

        Returns:
            True if file exists
        """
        file_path = self.output_dir / event.file_path
        return file_path.exists()

    def find_by_source_id(self, source_id: str) -> list[Path]:
        """
        Find existing files with a given source ID.

        This can be used for duplicate detection.

        Args:
            source_id: Source ID to search for

        Returns:
            List of matching file paths
        """
        matches = []
        for file_path in self.output_dir.rglob("*.fr.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                if f"sourceId: {source_id}" in content:
                    matches.append(file_path)
            except Exception:
                continue
        return matches

    def get_stats(self) -> dict[str, int]:
        """
        Get generation statistics.

        Returns:
            Dictionary with generation counts
        """
        return self.stats.to_dict()

    def reset_stats(self):
        """Reset generation statistics."""
        self.stats.reset()
