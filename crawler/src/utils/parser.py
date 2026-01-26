"""HTML parser utilities for event extraction."""

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..logger import get_logger

logger = get_logger(__name__)


class HTMLParser:
    """
    HTML parsing utilities for extracting event data.

    Wraps BeautifulSoup with convenience methods for common
    event extraction patterns.
    """

    def __init__(self, html: str, base_url: str = ""):
        """
        Initialize parser with HTML content.

        Args:
            html: HTML content to parse
            base_url: Base URL for resolving relative links
        """
        self.soup = BeautifulSoup(html, "lxml")
        self.base_url = base_url

    def select(self, selector: str) -> list[Tag]:
        """
        Select elements using CSS selector.

        Args:
            selector: CSS selector string

        Returns:
            List of matching elements
        """
        return self.soup.select(selector)

    def select_one(self, selector: str) -> Optional[Tag]:
        """
        Select first matching element.

        Args:
            selector: CSS selector string

        Returns:
            First matching element or None
        """
        return self.soup.select_one(selector)

    def get_text(self, element: Tag, selector: str = "", strip: bool = True) -> str:
        """
        Extract text content from element or its child.

        Args:
            element: Parent element
            selector: Optional CSS selector for child element
            strip: Whether to strip whitespace

        Returns:
            Text content or empty string
        """
        target = element
        if selector:
            target = element.select_one(selector)
        if target is None:
            return ""
        text = target.get_text()
        return text.strip() if strip else text

    def get_attr(
        self, element: Tag, attr: str, selector: str = "", default: str = ""
    ) -> str:
        """
        Extract attribute value from element or its child.

        Args:
            element: Parent element
            attr: Attribute name to extract
            selector: Optional CSS selector for child element
            default: Default value if not found

        Returns:
            Attribute value or default
        """
        target = element
        if selector:
            target = element.select_one(selector)
        if target is None:
            return default
        value = target.get(attr)
        if value is None:
            return default
        if isinstance(value, list):
            return " ".join(value)
        return str(value)

    def get_link(self, element: Tag, selector: str = "a") -> str:
        """
        Extract and resolve href link.

        Args:
            element: Parent element
            selector: CSS selector for link element

        Returns:
            Absolute URL or empty string
        """
        href = self.get_attr(element, "href", selector)
        if href and self.base_url:
            return urljoin(self.base_url, href)
        return href

    def get_image(self, element: Tag, selector: str = "img") -> str:
        """
        Extract and resolve image src.

        Args:
            element: Parent element
            selector: CSS selector for image element

        Returns:
            Absolute URL or empty string
        """
        # Try src first, then data-src (lazy loading)
        src = self.get_attr(element, "src", selector)
        if not src or src.startswith("data:"):
            src = self.get_attr(element, "data-src", selector)
        if not src:
            src = self.get_attr(element, "data-lazy-src", selector)

        if src and self.base_url:
            return urljoin(self.base_url, src)
        return src

    @staticmethod
    def parse_date(
        text: str,
        formats: Optional[list[str]] = None,
    ) -> Optional[datetime]:
        """
        Parse date from text using various formats.

        Args:
            text: Text containing date
            formats: List of strptime format strings to try

        Returns:
            Parsed datetime or None
        """
        if not text:
            return None

        # Clean text
        text = text.strip()

        # Default formats to try
        if formats is None:
            formats = [
                "%d/%m/%Y",
                "%d-%m-%Y",
                "%Y-%m-%d",
                "%d %B %Y",  # French: "26 janvier 2026"
                "%d %b %Y",
                "%A %d %B %Y",  # "Lundi 26 janvier 2026"
            ]

        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue

        logger.debug(f"Could not parse date: {text}")
        return None

    @staticmethod
    def parse_time(text: str) -> Optional[str]:
        """
        Extract time in HH:MM format from text.

        Args:
            text: Text containing time

        Returns:
            Time string in HH:MM format or None
        """
        if not text:
            return None

        # Match various time formats
        patterns = [
            r"(\d{1,2})[hH:](\d{2})",  # 19h30, 19:30
            r"(\d{1,2})\s*[hH]",  # 19h, 19 h
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if len(match.groups()) > 1 else 0
                return f"{hour:02d}:{minute:02d}"

        return None

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean and normalize text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        if not text:
            return ""
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def truncate(text: str, max_length: int = 160) -> str:
        """
        Truncate text to max length at word boundary.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= max_length:
            return text
        truncated = text[: max_length - 3].rsplit(" ", 1)[0]
        return truncated + "..."
