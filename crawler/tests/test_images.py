"""Tests for image downloader."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

from src.utils.images import ImageDownloader, create_placeholder_image


class TestImageDownloader:
    """Tests for ImageDownloader class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def downloader(self, temp_dir):
        """Create an ImageDownloader instance."""
        return ImageDownloader(
            output_dir=temp_dir,
            max_width=800,
            max_height=600,
            quality=80,
            format="webp",
            http_client=None,
            dry_run=False,
            use_date_dirs=False,
        )

    def test_initialization_defaults(self, temp_dir):
        """Test default initialization values."""
        downloader = ImageDownloader(output_dir=temp_dir)
        assert downloader.max_width == 1200
        assert downloader.max_height == 800
        assert downloader.quality == 85
        assert downloader.format == "webp"
        assert downloader.use_date_dirs is True
        assert downloader.placeholder == "/images/placeholder-event.webp"

    def test_initialization_custom(self, temp_dir):
        """Test custom initialization values."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            max_width=600,
            max_height=400,
            quality=70,
            format="jpg",
            placeholder="/custom/placeholder.jpg",
            use_date_dirs=False,
        )
        assert downloader.max_width == 600
        assert downloader.max_height == 400
        assert downloader.quality == 70
        assert downloader.format == "jpg"
        assert downloader.placeholder == "/custom/placeholder.jpg"
        assert downloader.use_date_dirs is False

    def test_dry_run_returns_path(self, temp_dir):
        """Test that dry run returns expected path without downloading."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            dry_run=True,
            use_date_dirs=False,
        )

        result = downloader.download(
            "https://example.com/image.jpg",
            event_slug="test-event",
        )

        assert result is not None
        assert result.startswith("/images/events/")
        assert "test-event" in result

    def test_dry_run_no_file_created(self, temp_dir):
        """Test that dry run doesn't create files."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            dry_run=True,
        )

        downloader.download(
            "https://example.com/image.jpg",
            event_slug="test-event",
        )

        # Directory should be empty
        assert list(temp_dir.iterdir()) == []

    def test_generate_filename_with_slug(self, downloader):
        """Test filename generation with event slug."""
        filename = downloader._generate_filename(
            "https://example.com/photo.jpg",
            "concert-jazz",
        )

        assert filename.startswith("concert-jazz-")
        assert filename.endswith(".webp")

    def test_generate_filename_without_slug(self, downloader):
        """Test filename generation without event slug."""
        filename = downloader._generate_filename(
            "https://example.com/photo.jpg",
            "",
        )

        assert filename.startswith("photo-")
        assert filename.endswith(".webp")

    def test_generate_filename_unique(self, downloader):
        """Test that different URLs generate different filenames."""
        filename1 = downloader._generate_filename(
            "https://example.com/photo1.jpg",
            "event",
        )
        filename2 = downloader._generate_filename(
            "https://example.com/photo2.jpg",
            "event",
        )

        assert filename1 != filename2

    def test_download_empty_url_returns_placeholder(self, temp_dir):
        """Test that empty URL returns placeholder."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            placeholder="/images/placeholder.webp",
        )
        result = downloader.download("")
        assert result == "/images/placeholder.webp"
        assert downloader.stats["placeholders"] == 1

    def test_download_empty_url_no_placeholder(self, temp_dir):
        """Test that empty URL returns None when no placeholder."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            placeholder=None,
        )
        result = downloader.download("")
        assert result is None

    def test_download_handles_error_returns_placeholder(self, temp_dir):
        """Test that download errors return placeholder."""
        mock_client = Mock()
        mock_client.get_bytes.side_effect = Exception("Network error")

        downloader = ImageDownloader(
            output_dir=temp_dir,
            http_client=mock_client,
            dry_run=False,
            placeholder="/images/placeholder.webp",
        )

        result = downloader.download("https://example.com/image.jpg")

        assert result == "/images/placeholder.webp"
        assert downloader.stats["failed"] == 1

    def test_format_jpg(self, temp_dir):
        """Test JPEG output format."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            format="jpg",
            dry_run=True,
            use_date_dirs=False,
        )

        result = downloader.download(
            "https://example.com/image.png",
            event_slug="test",
        )

        assert result.endswith(".jpg")

    def test_format_png(self, temp_dir):
        """Test PNG output format."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            format="png",
            dry_run=True,
            use_date_dirs=False,
        )

        result = downloader.download(
            "https://example.com/image.jpg",
            event_slug="test",
        )

        assert result.endswith(".png")


class TestDateBasedDirectories:
    """Tests for date-based directory organization."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_date_subdir_from_datetime(self, temp_dir):
        """Test date subdirectory from datetime object."""
        downloader = ImageDownloader(output_dir=temp_dir, use_date_dirs=True)

        event_date = datetime(2025, 1, 26)
        subdir = downloader._get_date_subdir(event_date)

        assert subdir == "2025/01/"

    def test_date_subdir_from_string(self, temp_dir):
        """Test date subdirectory from ISO string."""
        downloader = ImageDownloader(output_dir=temp_dir, use_date_dirs=True)

        subdir = downloader._get_date_subdir("2025-01-26")
        assert subdir == "2025/01/"

    def test_date_subdir_none(self, temp_dir):
        """Test date subdirectory with None date."""
        downloader = ImageDownloader(output_dir=temp_dir, use_date_dirs=True)

        subdir = downloader._get_date_subdir(None)
        assert subdir == ""

    def test_download_with_date_creates_subdir(self, temp_dir):
        """Test that download with date creates date subdirectory."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            dry_run=True,
            use_date_dirs=True,
        )

        result = downloader.download(
            "https://example.com/image.jpg",
            event_slug="test-event",
            event_date=datetime(2025, 3, 15),
        )

        assert "/2025/03/" in result

    def test_download_without_date_no_subdir(self, temp_dir):
        """Test download without date has no subdirectory."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            dry_run=True,
            use_date_dirs=True,
        )

        result = downloader.download(
            "https://example.com/image.jpg",
            event_slug="test-event",
            event_date=None,
        )

        assert "/2025/" not in result
        assert result == "/images/events/test-event-"[:25] or "test-event" in result


class TestImageCaching:
    """Tests for image caching behavior."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_cached_image_not_redownloaded(self, temp_dir):
        """Test that existing images are not re-downloaded."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            use_date_dirs=False,
        )

        # Create a dummy image file
        filename = downloader._generate_filename(
            "https://example.com/image.jpg",
            "cached-event",
        )
        cached_path = temp_dir / filename
        cached_path.write_bytes(b"dummy image content")

        # Mock HTTP client should not be called
        mock_client = Mock()
        downloader.http_client = mock_client

        result = downloader.download(
            "https://example.com/image.jpg",
            event_slug="cached-event",
        )

        assert result is not None
        assert "cached-event" in result
        mock_client.get_bytes.assert_not_called()
        assert downloader.stats["cached"] == 1


class TestImageProcessing:
    """Tests for image processing functionality."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_resize_large_image(self, temp_dir):
        """Test that large images are resized."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            max_width=800,
            max_height=600,
        )

        # Create a large test image
        img = Image.new("RGB", (1600, 1200), color="red")
        resized = downloader._resize(img)

        assert resized.width <= 800
        assert resized.height <= 600

    def test_resize_preserves_aspect_ratio(self, temp_dir):
        """Test that resize preserves aspect ratio."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            max_width=800,
            max_height=600,
        )

        # Create a wide image (2:1 ratio)
        img = Image.new("RGB", (2000, 1000), color="blue")
        resized = downloader._resize(img)

        # Aspect ratio should be preserved
        original_ratio = 2000 / 1000
        new_ratio = resized.width / resized.height
        assert abs(original_ratio - new_ratio) < 0.01

    def test_resize_small_image_unchanged(self, temp_dir):
        """Test that small images are not resized."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            max_width=800,
            max_height=600,
        )

        img = Image.new("RGB", (400, 300), color="green")
        resized = downloader._resize(img)

        assert resized.width == 400
        assert resized.height == 300

    def test_convert_rgba_to_rgb(self, temp_dir):
        """Test RGBA to RGB conversion."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            format="webp",
        )

        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        converted = downloader._convert_mode(img)

        assert converted.mode == "RGB"

    def test_convert_palette_to_rgb(self, temp_dir):
        """Test palette mode to RGB conversion."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            format="jpg",
        )

        img = Image.new("P", (100, 100))
        converted = downloader._convert_mode(img)

        assert converted.mode == "RGB"


class TestSlugSanitization:
    """Tests for slug sanitization."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_sanitize_basic_slug(self, temp_dir):
        """Test basic slug sanitization."""
        downloader = ImageDownloader(output_dir=temp_dir)
        result = downloader._sanitize_slug("Concert Jazz")
        assert result == "concert-jazz"

    def test_sanitize_special_characters(self, temp_dir):
        """Test removal of special characters."""
        downloader = ImageDownloader(output_dir=temp_dir)
        result = downloader._sanitize_slug("Événement spécial!")
        assert result == "vnement-spcial"

    def test_sanitize_underscores(self, temp_dir):
        """Test underscore replacement."""
        downloader = ImageDownloader(output_dir=temp_dir)
        result = downloader._sanitize_slug("event_name_here")
        assert result == "event-name-here"

    def test_sanitize_multiple_hyphens(self, temp_dir):
        """Test multiple hyphen reduction."""
        downloader = ImageDownloader(output_dir=temp_dir)
        result = downloader._sanitize_slug("event---name")
        assert result == "event-name"

    def test_sanitize_long_slug_truncated(self, temp_dir):
        """Test long slug truncation."""
        downloader = ImageDownloader(output_dir=temp_dir)
        long_slug = "a" * 100
        result = downloader._sanitize_slug(long_slug)
        assert len(result) == 50


class TestStatistics:
    """Tests for statistics tracking."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_initial_stats(self, temp_dir):
        """Test initial statistics are zero."""
        downloader = ImageDownloader(output_dir=temp_dir)
        stats = downloader.get_stats()

        assert stats["downloaded"] == 0
        assert stats["cached"] == 0
        assert stats["failed"] == 0
        assert stats["placeholders"] == 0

    def test_stats_after_placeholder(self, temp_dir):
        """Test statistics after placeholder return."""
        downloader = ImageDownloader(output_dir=temp_dir)
        downloader.download("")

        stats = downloader.get_stats()
        assert stats["placeholders"] == 1

    def test_stats_reset(self, temp_dir):
        """Test statistics reset."""
        downloader = ImageDownloader(output_dir=temp_dir)
        downloader.download("")  # Increment placeholders
        downloader.reset_stats()

        stats = downloader.get_stats()
        assert stats["placeholders"] == 0


class TestCreatePlaceholderImage:
    """Tests for placeholder image creation."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_create_placeholder(self, temp_dir):
        """Test placeholder image creation."""
        output_path = temp_dir / "placeholder.webp"
        create_placeholder_image(output_path, width=800, height=600)

        assert output_path.exists()

        # Verify it's a valid image
        img = Image.open(output_path)
        assert img.width == 800
        assert img.height == 600

    def test_create_placeholder_creates_dirs(self, temp_dir):
        """Test that placeholder creation creates parent directories."""
        output_path = temp_dir / "subdir" / "deep" / "placeholder.webp"
        create_placeholder_image(output_path)

        assert output_path.exists()
