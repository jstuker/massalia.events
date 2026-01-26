"""Image downloader with optimization."""

import hashlib
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

from PIL import Image

from ..logger import get_logger

if TYPE_CHECKING:
    from .http import HTTPClient

logger = get_logger(__name__)


class ImageDownloader:
    """
    Download and optimize images for Hugo static site.

    Features:
    - Download images from URLs
    - Resize to max width while preserving aspect ratio
    - Convert to WebP format for optimal file size
    - Generate unique filenames based on content hash
    """

    def __init__(
        self,
        output_dir: Path,
        max_width: int = 1200,
        quality: int = 85,
        format: str = "webp",
        http_client: Optional["HTTPClient"] = None,
        dry_run: bool = False,
    ):
        """
        Initialize the image downloader.

        Args:
            output_dir: Directory to save images
            max_width: Maximum image width (height scales proportionally)
            quality: Output quality (1-100)
            format: Output format (webp, jpg, png)
            http_client: HTTP client for downloading
            dry_run: If True, only log actions without downloading
        """
        self.output_dir = Path(output_dir)
        self.max_width = max_width
        self.quality = quality
        self.format = format.lower()
        self.http_client = http_client
        self.dry_run = dry_run

    def download(self, url: str, event_slug: str = "") -> str | None:
        """
        Download and optimize an image.

        Args:
            url: URL of the image to download
            event_slug: Optional slug to use in filename

        Returns:
            Relative path to saved image (for Hugo front matter),
            or None if download failed
        """
        if not url:
            return None

        logger.debug(f"Downloading image: {url}")

        if self.dry_run:
            # Generate what the path would be
            filename = self._generate_filename(url, event_slug)
            relative_path = f"/images/events/{filename}"
            logger.info(f"[DRY RUN] Would download: {url} -> {relative_path}")
            return relative_path

        try:
            # Download image bytes
            if self.http_client:
                image_bytes = self.http_client.get_bytes(url)
            else:
                import httpx
                response = httpx.get(url, follow_redirects=True)
                response.raise_for_status()
                image_bytes = response.content

            # Process image
            output_bytes, filename = self._process_image(image_bytes, url, event_slug)

            # Save to file
            output_path = self.output_dir / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                f.write(output_bytes)

            # Return relative path for Hugo
            relative_path = f"/images/events/{filename}"
            logger.info(f"Saved image: {relative_path}")
            return relative_path

        except Exception as e:
            logger.error(f"Failed to download image {url}: {e}")
            return None

    def _process_image(
        self, image_bytes: bytes, url: str, event_slug: str
    ) -> tuple[bytes, str]:
        """
        Process image: resize and convert format.

        Args:
            image_bytes: Raw image data
            url: Original URL (for filename generation)
            event_slug: Event slug for filename

        Returns:
            Tuple of (processed bytes, filename)
        """
        # Open image
        img = Image.open(BytesIO(image_bytes))

        # Convert to RGB if necessary (for WebP/JPEG)
        if img.mode in ("RGBA", "P") and self.format in ("webp", "jpg", "jpeg"):
            # Create white background for transparency
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB" and self.format in ("jpg", "jpeg"):
            img = img.convert("RGB")

        # Resize if needed
        if img.width > self.max_width:
            ratio = self.max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((self.max_width, new_height), Image.Resampling.LANCZOS)
            logger.debug(f"Resized image to {self.max_width}x{new_height}")

        # Generate filename
        filename = self._generate_filename(url, event_slug, image_bytes)

        # Convert to bytes
        output = BytesIO()
        save_format = "JPEG" if self.format in ("jpg", "jpeg") else self.format.upper()
        img.save(output, format=save_format, quality=self.quality, optimize=True)

        return output.getvalue(), filename

    def _generate_filename(
        self, url: str, event_slug: str, content: bytes = b""
    ) -> str:
        """
        Generate unique filename for image.

        Args:
            url: Image URL
            event_slug: Event slug
            content: Image content for hashing

        Returns:
            Filename with extension
        """
        # Use content hash if available, otherwise URL hash
        if content:
            hash_source = content
        else:
            hash_source = url.encode()

        content_hash = hashlib.md5(hash_source).hexdigest()[:8]

        # Build filename
        if event_slug:
            base_name = f"{event_slug}-{content_hash}"
        else:
            # Extract original filename from URL
            parsed = urlparse(url)
            original_name = Path(parsed.path).stem or "image"
            base_name = f"{original_name}-{content_hash}"

        # Add extension
        extension = self.format if self.format != "jpeg" else "jpg"
        return f"{base_name}.{extension}"
