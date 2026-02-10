"""Image downloader with optimization for Blowfish theme."""

import hashlib
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from PIL import Image

from ..logger import get_logger

if TYPE_CHECKING:
    from .http import HTTPClient

logger = get_logger(__name__)


class ImageDownloader:
    """
    Download and optimize images for Hugo static site with Blowfish theme.

    Features:
    - Download images from URLs
    - Resize to max width/height while preserving aspect ratio
    - Generate card thumbnails (383x215) cropped to 16:9 aspect ratio
    - Convert to WebP format for optimal file size
    - Organize images in date-based directories (YYYY/MM/)
    - Cache images to avoid re-downloading
    - Provide placeholder for missing images
    """

    # Default placeholder path (relative to static folder)
    DEFAULT_PLACEHOLDER = "/images/placeholder-event.webp"

    # Card thumbnail dimensions (16:9 aspect ratio)
    CARD_THUMBNAIL_WIDTH = 383
    CARD_THUMBNAIL_HEIGHT = 215

    def __init__(
        self,
        output_dir: Path,
        max_width: int = 1200,
        max_height: int = 800,
        quality: int = 85,
        format: str = "webp",
        http_client: "HTTPClient | None" = None,
        dry_run: bool = False,
        placeholder: str | None = DEFAULT_PLACEHOLDER,
        use_date_dirs: bool = True,
        generate_thumbnails: bool = True,
    ):
        """
        Initialize the image downloader.

        Args:
            output_dir: Directory to save images
            max_width: Maximum image width (height scales proportionally)
            max_height: Maximum image height (width scales proportionally)
            quality: Output quality (1-100)
            format: Output format (webp, jpg, png)
            http_client: HTTP client for downloading
            dry_run: If True, only log actions without downloading
            placeholder: Path to placeholder image for missing images
            use_date_dirs: If True, organize images in YYYY/MM/ subdirectories
            generate_thumbnails: If True, generate card thumbnails (383x215)
        """
        self.output_dir = Path(output_dir)
        self.max_width = max_width
        self.max_height = max_height
        self.quality = quality
        self.format = format.lower()
        self.http_client = http_client
        self.dry_run = dry_run
        self.placeholder = placeholder  # None means no placeholder
        self.use_date_dirs = use_date_dirs
        self.generate_thumbnails = generate_thumbnails

        # Statistics tracking
        self.stats = {
            "downloaded": 0,
            "cached": 0,
            "failed": 0,
            "placeholders": 0,
        }

    def download(
        self,
        url: str,
        event_slug: str = "",
        event_date: datetime | str | None = None,
    ) -> str | None:
        """
        Download and optimize an image.

        Args:
            url: URL of the image to download
            event_slug: Optional slug to use in filename
            event_date: Event date for organizing into subdirectories

        Returns:
            Relative path to saved image (for Hugo front matter),
            or None if download failed
        """
        if not url:
            logger.debug("No image URL provided")
            self.stats["placeholders"] += 1
            return self.placeholder if self.placeholder else None

        logger.debug(f"Processing image: {url}")

        # Determine output path
        subdir = self._get_date_subdir(event_date) if self.use_date_dirs else ""
        filename = self._generate_filename(url, event_slug)
        relative_path = (
            f"/images/events/{subdir}{filename}"
            if subdir
            else f"/images/events/{filename}"
        )
        output_path = (
            self.output_dir / subdir / filename
            if subdir
            else self.output_dir / filename
        )

        # Check cache - skip if image already exists
        if output_path.exists() and not self.dry_run:
            logger.debug(f"Image already exists (cached): {relative_path}")
            self.stats["cached"] += 1
            return relative_path

        if self.dry_run:
            logger.info(f"[DRY RUN] Would download: {url} -> {relative_path}")
            return relative_path

        try:
            # Download image bytes
            if self.http_client:
                image_bytes = self.http_client.get_bytes(url)
            else:
                import httpx

                from .http import validate_url

                validate_url(url)
                response = httpx.get(url, timeout=30, follow_redirects=True)
                response.raise_for_status()
                image_bytes = response.content

            # Process image
            output_bytes = self._process_image(image_bytes)

            # Save to file
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                f.write(output_bytes)

            file_size_kb = len(output_bytes) / 1024
            logger.info(f"Saved image: {relative_path} ({file_size_kb:.1f}KB)")

            # Generate thumbnail for card display
            if self.generate_thumbnails:
                self._generate_thumbnail(image_bytes, output_path)

            self.stats["downloaded"] += 1
            return relative_path

        except Exception as e:
            logger.error(f"Failed to download image {url}: {e}")
            self.stats["failed"] += 1
            return self.placeholder if self.placeholder else None

    def save_from_bytes(
        self,
        image_bytes: bytes,
        image_url: str = "",
        event_slug: str = "",
        event_date: datetime | str | None = None,
    ) -> str | None:
        """
        Save and optimize an image from raw bytes, skipping HTTP download.

        Uses the same processing pipeline as download() (resize, WebP
        conversion, thumbnail generation) but accepts pre-fetched bytes.

        Args:
            image_bytes: Raw image data
            image_url: Original URL (used for filename generation)
            event_slug: Optional slug to use in filename
            event_date: Event date for organizing into subdirectories

        Returns:
            Relative path to saved image (for Hugo front matter),
            or None if processing failed
        """
        if not image_bytes:
            self.stats["placeholders"] += 1
            return self.placeholder if self.placeholder else None

        # Determine output path
        subdir = self._get_date_subdir(event_date) if self.use_date_dirs else ""
        filename = self._generate_filename(image_url or "image", event_slug)
        relative_path = (
            f"/images/events/{subdir}{filename}"
            if subdir
            else f"/images/events/{filename}"
        )
        output_path = (
            self.output_dir / subdir / filename
            if subdir
            else self.output_dir / filename
        )

        # Check cache
        if output_path.exists() and not self.dry_run:
            logger.debug(f"Image already exists (cached): {relative_path}")
            self.stats["cached"] += 1
            return relative_path

        if self.dry_run:
            logger.info(f"[DRY RUN] Would save: {relative_path}")
            return relative_path

        try:
            output_bytes = self._process_image(image_bytes)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                f.write(output_bytes)

            file_size_kb = len(output_bytes) / 1024
            logger.info(
                f"Saved image from bytes: {relative_path} ({file_size_kb:.1f}KB)"
            )

            if self.generate_thumbnails:
                self._generate_thumbnail(image_bytes, output_path)

            self.stats["downloaded"] += 1
            return relative_path

        except Exception as e:
            logger.error(f"Failed to process image from bytes: {e}")
            self.stats["failed"] += 1
            return self.placeholder if self.placeholder else None

    def _get_date_subdir(self, event_date: datetime | str | None) -> str:
        """
        Get date-based subdirectory path.

        Args:
            event_date: Event date (datetime or ISO string)

        Returns:
            Subdirectory path like "2025/01/" or empty string
        """
        if not event_date:
            return ""

        try:
            if isinstance(event_date, str):
                # Parse ISO date string (YYYY-MM-DD)
                if len(event_date) >= 7:
                    year = event_date[:4]
                    month = event_date[5:7]
                    return f"{year}/{month}/"
            elif isinstance(event_date, datetime):
                return f"{event_date.year}/{event_date.month:02d}/"
        except (ValueError, IndexError):
            logger.warning(f"Could not parse date for directory: {event_date}")

        return ""

    def _process_image(self, image_bytes: bytes) -> bytes:
        """
        Process image: resize and convert format.

        Args:
            image_bytes: Raw image data

        Returns:
            Processed image bytes
        """
        # Open image
        img = Image.open(BytesIO(image_bytes))

        # Convert to RGB if necessary (for WebP/JPEG)
        img = self._convert_mode(img)

        # Resize if needed
        img = self._resize(img)

        # Convert to bytes
        output = BytesIO()
        save_format = "JPEG" if self.format in ("jpg", "jpeg") else self.format.upper()
        img.save(output, format=save_format, quality=self.quality, optimize=True)

        return output.getvalue()

    def _convert_mode(self, img: Image.Image) -> Image.Image:
        """
        Convert image mode for output format compatibility.

        Args:
            img: PIL Image

        Returns:
            Converted image
        """
        if img.mode in ("RGBA", "P") and self.format in ("webp", "jpg", "jpeg"):
            # Create white background for transparency
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            return background
        elif img.mode != "RGB" and self.format in ("jpg", "jpeg"):
            return img.convert("RGB")
        return img

    def _resize(self, img: Image.Image) -> Image.Image:
        """
        Resize image maintaining aspect ratio.

        Fits image within max_width x max_height bounds.

        Args:
            img: PIL Image

        Returns:
            Resized image
        """
        width, height = img.size

        # Check if resize is needed
        if width <= self.max_width and height <= self.max_height:
            return img

        # Calculate scale ratio to fit within bounds
        width_ratio = self.max_width / width
        height_ratio = self.max_height / height
        ratio = min(width_ratio, height_ratio)

        new_width = int(width * ratio)
        new_height = int(height * ratio)

        logger.debug(
            f"Resizing image from {width}x{height} to {new_width}x{new_height}"
        )
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def _generate_thumbnail(self, image_bytes: bytes, original_path: Path) -> None:
        """
        Generate a card thumbnail image (383x215) with center crop.

        The thumbnail is saved alongside the original with a '-thumb' suffix.
        Uses center crop to fill the exact dimensions without distortion.

        Args:
            image_bytes: Raw image data
            original_path: Path to the original image file
        """
        try:
            img = Image.open(BytesIO(image_bytes))
            img = self._convert_mode(img)

            # Target dimensions for card thumbnail
            target_width = self.CARD_THUMBNAIL_WIDTH
            target_height = self.CARD_THUMBNAIL_HEIGHT
            target_ratio = target_width / target_height

            # Get current dimensions
            width, height = img.size
            current_ratio = width / height

            # Calculate crop box to achieve target aspect ratio (center crop)
            if current_ratio > target_ratio:
                # Image is wider than target - crop sides
                new_width = int(height * target_ratio)
                left = (width - new_width) // 2
                crop_box = (left, 0, left + new_width, height)
            else:
                # Image is taller than target - crop top/bottom
                new_height = int(width / target_ratio)
                top = (height - new_height) // 2
                crop_box = (0, top, width, top + new_height)

            img = img.crop(crop_box)

            # Resize to exact target dimensions
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # Generate thumbnail path
            thumb_path = original_path.with_stem(original_path.stem + "-thumb")

            # Save thumbnail
            output = BytesIO()
            save_format = (
                "JPEG" if self.format in ("jpg", "jpeg") else self.format.upper()
            )
            img.save(output, format=save_format, quality=self.quality, optimize=True)

            with open(thumb_path, "wb") as f:
                f.write(output.getvalue())

            thumb_size_kb = len(output.getvalue()) / 1024
            logger.debug(
                f"Generated thumbnail: {thumb_path.name} ({thumb_size_kb:.1f}KB)"
            )

        except Exception as e:
            logger.warning(f"Failed to generate thumbnail: {e}")

    def _generate_filename(
        self,
        url: str,
        event_slug: str,
        content: bytes = b"",
    ) -> str:
        """
        Generate unique filename for image.

        Args:
            url: Image URL
            event_slug: Event slug
            content: Image content for hashing (optional)

        Returns:
            Filename with extension
        """
        # Use URL hash for uniqueness (content not always available at this point)
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        # Build filename
        if event_slug:
            # Sanitize slug
            safe_slug = self._sanitize_slug(event_slug)
            base_name = f"{safe_slug}-{url_hash}"
        else:
            # Extract original filename from URL
            parsed = urlparse(url)
            original_name = Path(parsed.path).stem or "image"
            safe_name = self._sanitize_slug(original_name)
            base_name = f"{safe_name}-{url_hash}"

        # Add extension
        extension = self.format if self.format != "jpeg" else "jpg"
        return f"{base_name}.{extension}"

    def _sanitize_slug(self, slug: str) -> str:
        """
        Sanitize slug for use in filename.

        Args:
            slug: Raw slug

        Returns:
            URL-safe slug
        """
        import re

        # Convert to lowercase
        slug = slug.lower()
        # Replace spaces and underscores with hyphens
        slug = re.sub(r"[\s_]+", "-", slug)
        # Remove non-alphanumeric characters except hyphens
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        # Remove multiple consecutive hyphens
        slug = re.sub(r"-+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        # Limit length
        return slug[:50] if len(slug) > 50 else slug

    def get_stats(self) -> dict[str, int]:
        """
        Get image processing statistics.

        Returns:
            Dictionary with download/cache/fail counts
        """
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = {
            "downloaded": 0,
            "cached": 0,
            "failed": 0,
            "placeholders": 0,
        }


def create_placeholder_image(
    output_path: Path,
    width: int = 1200,
    height: int = 800,
    quality: int = 85,
):
    """
    Create a placeholder image for events without images.

    Args:
        output_path: Path to save placeholder
        width: Image width
        height: Image height
        quality: Output quality
    """
    # Create a simple gray placeholder with text
    img = Image.new("RGB", (width, height), (200, 200, 200))

    # Add "No Image" text if PIL has font support
    try:
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(img)

        # Try to use a basic font
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        except OSError:
            font = ImageFont.load_default()

        text = "No Image"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (width - text_width) // 2
        y = (height - text_height) // 2

        draw.text((x, y), text, fill=(150, 150, 150), font=font)

    except ImportError:
        pass  # Skip text if PIL doesn't have drawing support

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="WEBP", quality=quality)
    logger.info(f"Created placeholder image: {output_path}")
