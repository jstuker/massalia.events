"""Hugo markdown file generator."""

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from ..logger import get_logger

if TYPE_CHECKING:
    from ..models.event import Event

logger = get_logger(__name__)


class MarkdownGenerator:
    """
    Generate Hugo-compatible markdown files for events.

    Creates files following the Hugo content structure:
    - YAML front matter with event metadata
    - Date-based folder structure (YYYY/MM/DD)
    - French language suffix (.fr.md)
    """

    def __init__(
        self,
        output_dir: Path,
        dry_run: bool = False,
    ):
        """
        Initialize the markdown generator.

        Args:
            output_dir: Base output directory for content files
            dry_run: If True, only log actions without writing files
        """
        self.output_dir = Path(output_dir)
        self.dry_run = dry_run

    def generate(self, event: "Event") -> Path:
        """
        Generate a markdown file for an event.

        Args:
            event: Event model instance

        Returns:
            Path to the generated file
        """
        # Determine output path
        file_path = self.output_dir / event.file_path
        logger.debug(f"Generating markdown: {file_path}")

        # Generate front matter
        front_matter = event.to_front_matter()

        # Build file content
        content = self._build_content(front_matter)

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create: {file_path}")
            logger.debug(f"Content:\n{content}")
        else:
            self._write_file(file_path, content)
            logger.info(f"Created: {file_path}")

        return file_path

    def _build_content(self, front_matter: dict) -> str:
        """
        Build markdown file content with YAML front matter.

        Args:
            front_matter: Dictionary of front matter fields

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
        return f"---\n{yaml_content}---\n"

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
