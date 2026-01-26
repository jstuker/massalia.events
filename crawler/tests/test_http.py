"""Tests for HTTP client module."""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.utils.http import FetchResult, HTTPClient, RateLimiter, ResponseCache


class TestFetchResult:
    """Tests for FetchResult dataclass."""

    def test_successful_result(self):
        result = FetchResult(
            url="https://example.com",
            status_code=200,
            html="<html></html>",
            headers={"content-type": "text/html"},
            elapsed_ms=100.5,
        )
        assert result.success is True
        assert result.url == "https://example.com"
        assert result.html == "<html></html>"
        assert result.from_cache is False

    def test_failed_result_with_error(self):
        result = FetchResult(
            url="https://example.com",
            status_code=0,
            html=None,
            error="Connection refused",
        )
        assert result.success is False
        assert result.error == "Connection refused"

    def test_failed_result_with_4xx(self):
        result = FetchResult(
            url="https://example.com",
            status_code=404,
            html=None,
        )
        assert result.success is False

    def test_failed_result_with_5xx(self):
        result = FetchResult(
            url="https://example.com",
            status_code=500,
            html=None,
        )
        assert result.success is False

    def test_redirect_is_success(self):
        result = FetchResult(
            url="https://example.com",
            status_code=301,
            html="<html></html>",
        )
        assert result.success is True

    def test_cached_result(self):
        result = FetchResult(
            url="https://example.com",
            status_code=200,
            html="<html></html>",
            from_cache=True,
        )
        assert result.success is True
        assert result.from_cache is True


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_no_delay_on_first_request(self):
        limiter = RateLimiter(default_delay=1.0)
        start = time.time()
        limiter.wait("source1")
        elapsed = time.time() - start
        assert elapsed < 0.1  # Should be nearly instant

    def test_delay_on_second_request(self):
        limiter = RateLimiter(default_delay=0.2)
        limiter.wait("source1")
        start = time.time()
        limiter.wait("source1")
        elapsed = time.time() - start
        assert elapsed >= 0.15  # Allow some tolerance

    def test_custom_delay_per_source(self):
        limiter = RateLimiter(default_delay=1.0)
        limiter.set_delay("fast_source", 0.1)
        limiter.wait("fast_source")
        start = time.time()
        limiter.wait("fast_source")
        elapsed = time.time() - start
        assert elapsed >= 0.08
        assert elapsed < 0.5  # Much less than default

    def test_different_sources_independent(self):
        limiter = RateLimiter(default_delay=0.5)
        limiter.wait("source1")
        start = time.time()
        limiter.wait("source2")  # Different source
        elapsed = time.time() - start
        assert elapsed < 0.1  # Should be nearly instant


class TestResponseCache:
    """Tests for ResponseCache class."""

    @pytest.fixture
    def temp_cache_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_cache_miss(self, temp_cache_dir):
        cache = ResponseCache(temp_cache_dir)
        result = cache.get("https://example.com/not-cached")
        assert result is None

    def test_cache_hit(self, temp_cache_dir):
        cache = ResponseCache(temp_cache_dir)
        original = FetchResult(
            url="https://example.com",
            status_code=200,
            html="<html>cached</html>",
            headers={"content-type": "text/html"},
            elapsed_ms=100.0,
        )
        cache.set(original)

        cached = cache.get("https://example.com")
        assert cached is not None
        assert cached.url == original.url
        assert cached.status_code == original.status_code
        assert cached.html == original.html
        assert cached.from_cache is True

    def test_cache_ttl_expiry(self, temp_cache_dir):
        cache = ResponseCache(temp_cache_dir, ttl_seconds=0)  # Immediate expiry
        result = FetchResult(
            url="https://example.com",
            status_code=200,
            html="<html></html>",
        )
        cache.set(result)
        time.sleep(0.1)  # Wait for TTL
        cached = cache.get("https://example.com")
        assert cached is None

    def test_cache_does_not_store_failures(self, temp_cache_dir):
        cache = ResponseCache(temp_cache_dir)
        result = FetchResult(
            url="https://example.com",
            status_code=500,
            html=None,
            error="Server error",
        )
        cache.set(result)
        cached = cache.get("https://example.com")
        assert cached is None

    def test_cache_clear(self, temp_cache_dir):
        cache = ResponseCache(temp_cache_dir)
        result = FetchResult(
            url="https://example.com",
            status_code=200,
            html="<html></html>",
        )
        cache.set(result)
        assert cache.get("https://example.com") is not None

        cache.clear()
        assert cache.get("https://example.com") is None

    def test_cache_handles_invalid_json(self, temp_cache_dir):
        cache = ResponseCache(temp_cache_dir)
        # Write invalid JSON to cache file
        cache_key = cache._get_cache_key("https://example.com")
        cache_path = temp_cache_dir / f"{cache_key}.json"
        cache_path.write_text("invalid json {")

        result = cache.get("https://example.com")
        assert result is None
        assert not cache_path.exists()  # Should be cleaned up


class TestHTTPClient:
    """Tests for HTTPClient class."""

    def test_initialization_defaults(self):
        client = HTTPClient()
        assert client.timeout == 30
        assert client.retry_count == 3
        assert client.retry_delay == 1.0
        assert client.user_agent == "MassaliaEventsCrawler/1.0"
        assert client.verify_ssl is True
        assert client.cache is None
        client.close()

    def test_initialization_custom_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            client = HTTPClient(
                timeout=60,
                retry_count=5,
                retry_delay=2.0,
                rate_limit_delay=0.5,
                user_agent="TestBot/1.0",
                cache_dir=Path(tmpdir),
                cache_ttl=7200,
                verify_ssl=False,
            )
            assert client.timeout == 60
            assert client.retry_count == 5
            assert client.user_agent == "TestBot/1.0"
            assert client.verify_ssl is False
            assert client.cache is not None
            client.close()

    def test_set_source_rate_limit(self):
        client = HTTPClient(rate_limit_delay=1.0)
        client.set_source_rate_limit("fast_source", 0.1)
        assert client.rate_limiter._source_delays["fast_source"] == 0.1
        client.close()

    def test_context_manager(self):
        with HTTPClient() as client:
            assert client is not None

    @patch("httpx.Client")
    def test_fetch_success(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>content</html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.is_success = True

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HTTPClient()
        result = client.fetch("https://example.com")

        assert result.success is True
        assert result.status_code == 200
        assert result.html == "<html>content</html>"
        assert result.error is None
        client.close()

    @patch("httpx.Client")
    def test_fetch_with_source_id(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html></html>"
        mock_response.headers = {}
        mock_response.is_success = True

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HTTPClient()
        result = client.fetch("https://example.com", source_id="test_source")

        assert result.success is True
        client.close()

    @patch("httpx.Client")
    def test_fetch_404_error(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.is_success = False

        mock_error = httpx.HTTPStatusError(
            "Not found",
            request=MagicMock(),
            response=mock_response,
        )
        mock_response.raise_for_status.side_effect = mock_error

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HTTPClient(retry_count=0)
        result = client.fetch("https://example.com/notfound")

        assert result.success is False
        assert result.status_code == 404
        client.close()

    @patch("httpx.Client")
    def test_fetch_retries_on_5xx(self, mock_client_class):
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_fail.headers = {}
        mock_response_fail.is_success = False

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.text = "<html></html>"
        mock_response_success.headers = {}
        mock_response_success.is_success = True

        mock_client = MagicMock()
        mock_client.get.side_effect = [
            mock_response_fail,
            mock_response_success,
        ]
        mock_client_class.return_value = mock_client

        client = HTTPClient(retry_count=2, retry_delay=0.01)
        result = client.fetch("https://example.com")

        assert mock_client.get.call_count == 2
        assert result.success is True
        client.close()

    @patch("httpx.Client")
    def test_fetch_with_cache(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>content</html>"
        mock_response.headers = {}
        mock_response.is_success = True

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            client = HTTPClient(cache_dir=Path(tmpdir))

            # First fetch - should hit the network
            result1 = client.fetch("https://example.com")
            assert result1.success is True
            assert result1.from_cache is False
            assert mock_client.get.call_count == 1

            # Second fetch - should hit the cache
            result2 = client.fetch("https://example.com")
            assert result2.success is True
            assert result2.from_cache is True
            assert mock_client.get.call_count == 1  # No additional network call

            client.close()

    @patch("httpx.Client")
    def test_get_text(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Hello</html>"

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HTTPClient()
        text = client.get_text("https://example.com")

        assert text == "<html>Hello</html>"
        client.close()

    @patch("httpx.Client")
    def test_get_bytes(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"binary data"

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = HTTPClient()
        data = client.get_bytes("https://example.com/image.png")

        assert data == b"binary data"
        client.close()


class TestHTTPClientIntegration:
    """Integration tests for HTTPClient (require network)."""

    @pytest.mark.skip(reason="Integration test - requires network")
    def test_real_fetch(self):
        client = HTTPClient()
        result = client.fetch("https://httpbin.org/get")
        assert result.success is True
        assert result.status_code == 200
        assert "httpbin.org" in result.html
        client.close()

    @pytest.mark.skip(reason="Integration test - requires network")
    def test_real_fetch_404(self):
        client = HTTPClient()
        result = client.fetch("https://httpbin.org/status/404")
        assert result.success is False
        assert result.status_code == 404
        client.close()
