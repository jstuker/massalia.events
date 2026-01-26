"""HTTP client with rate limiting and retries."""

import time
from typing import Optional

import httpx

from ..logger import get_logger

logger = get_logger(__name__)


class HTTPClient:
    """
    HTTP client with rate limiting and automatic retries.

    Features:
    - Configurable timeout
    - Retry logic with exponential backoff
    - Rate limiting between requests
    - Custom User-Agent
    """

    def __init__(
        self,
        timeout: int = 30,
        retry_count: int = 3,
        retry_delay: float = 1.0,
        rate_limit_delay: float = 1.0,
        user_agent: str = "MassaliaEventsCrawler/1.0",
    ):
        """
        Initialize HTTP client.

        Args:
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
            retry_delay: Base delay between retries (exponential backoff)
            rate_limit_delay: Delay between successful requests
            user_agent: User-Agent header value
        """
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.rate_limit_delay = rate_limit_delay
        self.user_agent = user_agent

        self._last_request_time: Optional[float] = None
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    def _wait_for_rate_limit(self):
        """Wait if needed to respect rate limiting."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit_delay:
                wait_time = self.rate_limit_delay - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                time.sleep(wait_time)

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

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
