"""HTTP client with rate limiting, retries, and caching."""

import hashlib
import ipaddress
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..logger import get_logger

logger = get_logger(__name__)


class SSRFError(ValueError):
    """Raised when a URL targets a private/reserved network address."""


def validate_url(url: str) -> str:
    """Validate a URL is safe to fetch (防SSRF).

    Rejects:
    - Non-HTTP(S) schemes
    - Private/reserved IP ranges (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12,
      192.168.0.0/16, 169.254.0.0/16, ::1, etc.)
    - Localhost hostnames

    Args:
        url: The URL to validate.

    Returns:
        The validated URL string.

    Raises:
        SSRFError: If the URL targets a disallowed destination.
    """
    if not url or not isinstance(url, str):
        raise SSRFError("Empty or invalid URL")

    parsed = urlparse(url)

    # 1. Scheme must be http or https
    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Blocked non-HTTP scheme: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError(f"No hostname in URL: {url}")

    # 2. Reject localhost hostnames
    _lower = hostname.lower()
    if _lower in ("localhost", "localhost.localdomain") or _lower.endswith(
        ".localhost"
    ):
        raise SSRFError(f"Blocked localhost URL: {url}")

    # 3. Check if hostname is an IP literal and reject private/reserved ranges
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # Not an IP literal — it's a regular hostname, which is fine
        addr = None

    if addr is not None:
        if addr.is_private or addr.is_reserved or addr.is_loopback:
            raise SSRFError(f"Blocked private/reserved IP: {hostname}")
        if addr.is_link_local:
            raise SSRFError(f"Blocked link-local IP: {hostname}")

    return url


@dataclass
class FetchResult:
    """
    Structured result from a fetch operation.

    Contains all relevant information about the request/response,
    including any errors that occurred.
    """

    url: str
    status_code: int
    html: str | None
    headers: dict[str, str] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    error: str | None = None
    from_cache: bool = False

    @property
    def success(self) -> bool:
        """Check if the fetch was successful."""
        return self.status_code >= 200 and self.status_code < 400 and self.error is None


class RateLimiter:
    """
    Per-source rate limiter.

    Tracks the last request time for each source and enforces
    minimum delays between requests to the same source.
    """

    def __init__(self, default_delay: float = 1.0):
        """
        Initialize rate limiter.

        Args:
            default_delay: Default delay between requests in seconds
        """
        self.default_delay = default_delay
        self._last_request: dict[str, float] = {}
        self._source_delays: dict[str, float] = {}

    def set_delay(self, source_id: str, delay: float):
        """
        Set custom delay for a specific source.

        Args:
            source_id: Source identifier
            delay: Delay in seconds between requests
        """
        self._source_delays[source_id] = delay

    def wait(self, source_id: str):
        """
        Wait if needed to respect rate limiting for a source.

        Args:
            source_id: Source identifier
        """
        delay = self._source_delays.get(source_id, self.default_delay)
        now = time.time()

        if source_id in self._last_request:
            elapsed = now - self._last_request[source_id]
            if elapsed < delay:
                wait_time = delay - elapsed
                logger.debug(f"Rate limiting [{source_id}]: waiting {wait_time:.2f}s")
                time.sleep(wait_time)

        self._last_request[source_id] = time.time()


class ResponseCache:
    """
    Simple file-based response cache for development/testing.

    Caches responses to disk to avoid repeated requests during development.
    """

    def __init__(self, cache_dir: Path, ttl_seconds: int = 3600):
        """
        Initialize response cache.

        Args:
            cache_dir: Directory to store cached responses
            ttl_seconds: Cache time-to-live in seconds
        """
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cache_path(self, url: str) -> Path:
        """Get cache file path for URL."""
        return self.cache_dir / f"{self._get_cache_key(url)}.json"

    def get(self, url: str) -> FetchResult | None:
        """
        Get cached response if available and not expired.

        Args:
            url: URL to look up

        Returns:
            Cached FetchResult or None if not cached/expired
        """
        cache_path = self._get_cache_path(url)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)

            # Check TTL
            cached_at = data.get("cached_at", 0)
            if time.time() - cached_at > self.ttl_seconds:
                logger.debug(f"Cache expired for {url}")
                cache_path.unlink()
                return None

            logger.debug(f"Cache hit for {url}")
            return FetchResult(
                url=data["url"],
                status_code=data["status_code"],
                html=data["html"],
                headers=data.get("headers", {}),
                elapsed_ms=data.get("elapsed_ms", 0),
                from_cache=True,
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Invalid cache file for {url}: {e}")
            cache_path.unlink(missing_ok=True)
            return None

    def set(self, result: FetchResult):
        """
        Cache a fetch result.

        Args:
            result: FetchResult to cache
        """
        if not result.success:
            return  # Don't cache failures

        cache_path = self._get_cache_path(result.url)

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "url": result.url,
                        "status_code": result.status_code,
                        "html": result.html,
                        "headers": result.headers,
                        "elapsed_ms": result.elapsed_ms,
                        "cached_at": time.time(),
                    },
                    f,
                )
            logger.debug(f"Cached response for {result.url}")
        except OSError as e:
            logger.warning(f"Failed to cache response for {result.url}: {e}")

    def clear(self):
        """Clear all cached responses."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
        logger.info("Cache cleared")


class HTTPClient:
    """
    HTTP client with rate limiting, automatic retries, and optional caching.

    Features:
    - Configurable timeout
    - Retry logic with exponential backoff
    - Per-source rate limiting
    - Custom User-Agent
    - Optional response caching for development
    - Cookie handling
    - Proxy support
    - SSL error handling
    """

    def __init__(
        self,
        timeout: int = 30,
        retry_count: int = 3,
        retry_delay: float = 1.0,
        rate_limit_delay: float = 1.0,
        user_agent: str = "MassaliaEventsCrawler/1.0",
        cache_dir: Path | None = None,
        cache_ttl: int = 3600,
        proxy: str | None = None,
        verify_ssl: bool = True,
    ):
        """
        Initialize HTTP client.

        Args:
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
            retry_delay: Base delay between retries (exponential backoff)
            rate_limit_delay: Default delay between requests to same source
            user_agent: User-Agent header value
            cache_dir: Directory for response caching (None to disable)
            cache_ttl: Cache time-to-live in seconds
            proxy: Proxy URL (e.g., "http://proxy:8080")
            verify_ssl: Whether to verify SSL certificates
        """
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.user_agent = user_agent
        self.verify_ssl = verify_ssl

        # Per-source rate limiter
        self.rate_limiter = RateLimiter(default_delay=rate_limit_delay)

        # Response cache (optional)
        self.cache: ResponseCache | None = None
        if cache_dir:
            self.cache = ResponseCache(cache_dir, ttl_seconds=cache_ttl)

        # Build client options
        client_kwargs = {
            "timeout": timeout,
            "headers": {"User-Agent": user_agent},
            "follow_redirects": True,
            "verify": verify_ssl,
        }

        if proxy:
            client_kwargs["proxy"] = proxy

        self._client = httpx.Client(**client_kwargs)

        # Legacy compatibility
        self._last_request_time: float | None = None
        self.rate_limit_delay = rate_limit_delay

    def _wait_for_rate_limit(self):
        """Wait if needed to respect rate limiting (legacy method)."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit_delay:
                wait_time = self.rate_limit_delay - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                time.sleep(wait_time)

    def fetch(self, url: str, source_id: str | None = None) -> FetchResult:
        """
        Fetch a URL with rate limiting, retries, and optional caching.

        Args:
            url: URL to fetch
            source_id: Optional source identifier for per-source rate limiting

        Returns:
            FetchResult with response data or error information
        """
        # Validate URL before any network access
        try:
            validate_url(url)
        except SSRFError as e:
            logger.warning(f"URL validation failed: {e}")
            return FetchResult(
                url=url,
                status_code=0,
                html=None,
                headers={},
                elapsed_ms=0,
                error=str(e),
            )

        # Check cache first
        if self.cache:
            cached = self.cache.get(url)
            if cached:
                return cached

        # Apply rate limiting
        if source_id:
            self.rate_limiter.wait(source_id)
        else:
            self._wait_for_rate_limit()

        last_error: str | None = None

        for attempt in range(self.retry_count + 1):
            start_time = time.time()

            try:
                logger.debug(f"GET {url} (attempt {attempt + 1})")
                response = self._client.get(url)
                elapsed_ms = (time.time() - start_time) * 1000

                self._last_request_time = time.time()

                # Check for server errors (5xx) - these should be retried
                if response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}"
                    logger.warning(
                        f"HTTP {response.status_code} for {url}, retrying..."
                    )
                    # Fall through to retry logic
                else:
                    result = FetchResult(
                        url=url,
                        status_code=response.status_code,
                        html=response.text if response.is_success else None,
                        headers=dict(response.headers),
                        elapsed_ms=elapsed_ms,
                    )

                    # Cache successful responses
                    if self.cache and result.success:
                        self.cache.set(result)

                    # Log non-success status codes
                    if not response.is_success:
                        logger.warning(f"HTTP {response.status_code} for {url}")

                    return result

            except httpx.HTTPStatusError as e:
                elapsed_ms = (time.time() - start_time) * 1000
                status = e.response.status_code
                last_error = f"HTTP {status}: {str(e)}"

                # Don't retry client errors (4xx) except 429 Too Many Requests
                if 400 <= status < 500 and status != 429:
                    logger.error(f"HTTP {status} for {url}: {e}")
                    return FetchResult(
                        url=url,
                        status_code=status,
                        html=None,
                        headers=dict(e.response.headers) if e.response else {},
                        elapsed_ms=elapsed_ms,
                        error=last_error,
                    )

                logger.warning(f"HTTP {status} for {url}, retrying...")

            except httpx.SSLError as e:
                elapsed_ms = (time.time() - start_time) * 1000
                last_error = f"SSL error: {str(e)}"
                logger.error(f"SSL error for {url}: {e}")

                # SSL errors are typically not recoverable with retries
                return FetchResult(
                    url=url,
                    status_code=0,
                    html=None,
                    headers={},
                    elapsed_ms=elapsed_ms,
                    error=last_error,
                )

            except httpx.RequestError as e:
                elapsed_ms = (time.time() - start_time) * 1000
                last_error = f"Request error: {str(e)}"
                logger.warning(f"Request error for {url}: {e}, retrying...")

            # Exponential backoff before retry
            if attempt < self.retry_count:
                delay = self.retry_delay * (2**attempt)
                logger.debug(f"Waiting {delay:.2f}s before retry")
                time.sleep(delay)

        # All retries exhausted
        logger.error(f"All retries failed for {url}")
        return FetchResult(
            url=url,
            status_code=0,
            html=None,
            headers={},
            elapsed_ms=0,
            error=last_error,
        )

    def get(self, url: str) -> httpx.Response:
        """
        Make a GET request with retries.

        Args:
            url: URL to fetch

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPError: If all retries fail
        """
        validate_url(url)  # raises SSRFError for disallowed URLs

        self._wait_for_rate_limit()

        last_error = None
        for attempt in range(self.retry_count + 1):
            try:
                logger.debug(f"GET {url} (attempt {attempt + 1})")
                response = self._client.get(url)
                response.raise_for_status()
                self._last_request_time = time.time()
                return response

            except httpx.HTTPStatusError as e:
                last_error = e
                status = e.response.status_code
                # Don't retry client errors (4xx) except 429
                if 400 <= status < 500 and status != 429:
                    logger.error(f"HTTP {status} for {url}: {e}")
                    raise
                logger.warning(f"HTTP {status} for {url}, retrying...")

            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"Request error for {url}: {e}, retrying...")

            # Exponential backoff
            if attempt < self.retry_count:
                delay = self.retry_delay * (2**attempt)
                logger.debug(f"Waiting {delay:.2f}s before retry")
                time.sleep(delay)

        logger.error(f"All retries failed for {url}")
        raise last_error

    def get_text(self, url: str) -> str:
        """
        Fetch URL and return response text.

        Args:
            url: URL to fetch

        Returns:
            Response body as string
        """
        response = self.get(url)
        return response.text

    def get_bytes(self, url: str) -> bytes:
        """
        Fetch URL and return response bytes.

        Args:
            url: URL to fetch

        Returns:
            Response body as bytes
        """
        response = self.get(url)
        return response.content

    def set_source_rate_limit(self, source_id: str, delay: float):
        """
        Set custom rate limit for a specific source.

        Args:
            source_id: Source identifier
            delay: Delay in seconds between requests
        """
        self.rate_limiter.set_delay(source_id, delay)

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
