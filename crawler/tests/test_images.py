"""Tests for image downloader."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.utils.images import ImageDownloader


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
            quality=80,
            format="webp",
            http_client=None,
            dry_run=False,
        )

    def test_dry_run_returns_path(self, temp_dir):
        """Test that dry run returns expected path without downloading."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            dry_run=True,
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
            b"test content",
        )

        assert filename.startswith("concert-jazz-")
        assert filename.endswith(".webp")

    def test_generate_filename_without_slug(self, downloader):
        """Test filename generation without event slug."""
        filename = downloader._generate_filename(
            "https://example.com/photo.jpg",
            "",
            b"test content",
        )

        assert filename.startswith("photo-")
        assert filename.endswith(".webp")

    def test_generate_filename_unique(self, downloader):
        """Test that different content generates different filenames."""
        filename1 = downloader._generate_filename(
            "https://example.com/photo.jpg",
            "event",
            b"content 1",
        )
        filename2 = downloader._generate_filename(
            "https://example.com/photo.jpg",
            "event",
            b"content 2",
        )

        assert filename1 != filename2

    def test_download_empty_url(self, downloader):
        """Test that empty URL returns None."""
        result = downloader.download("")
        assert result is None

    def test_download_handles_error(self, temp_dir):
        """Test that download errors are handled gracefully."""
        # Create a mock HTTP client that raises an exception
        mock_client = Mock()
        mock_client.get_bytes.side_effect = Exception("Network error")

        downloader = ImageDownloader(
            output_dir=temp_dir,
            http_client=mock_client,
            dry_run=False,
        )

        result = downloader.download("https://example.com/image.jpg")

        assert result is None

    def test_format_jpg(self, temp_dir):
        """Test JPEG output format."""
        downloader = ImageDownloader(
            output_dir=temp_dir,
            format="jpg",
            dry_run=True,
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
        )

        result = downloader.download(
            "https://example.com/image.jpg",
            event_slug="test",
        )

        assert result.endswith(".png")
