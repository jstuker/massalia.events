---
name: Add New Event Source
about: Template for crawling an additional website into Massalia Events
title: "[NEW SOURCE] Add [Website Name] crawler"
labels: enhancement, crawler
assignees: ''
---

## Overview

Add **[Website Name]** as a new event source for Massalia Events.

**Website URL:**
**Website name:**
**Website id:**
**Rate_limit:** requests_per_second: 0.5, delay_between_pages: 3.0

---

## Pre-Implementation Research

Before starting implementation, complete the following research:

- [ ] Analyze the website structure and identify the agenda/events page
- [ ] Document the HTML structure of event listings
- [ ] Document the HTML structure of individual event detail pages
- [ ] Identify all available data fields (title, date, time, location, description, image, categories, etc.)
- [ ] Identify events types and map them to the taxonomy
- [ ] Check for pagination or infinite scroll
- [ ] Verify robots.txt compliance and terms of service
- [ ] Identify rate limiting requirements
- [ ] List all unique venues/locations that appear on the website

---

## Tasks

### Task 1: Add Website to sources.yaml

**File:** `crawler/config/sources.yaml`

Add the new source configuration with appropriate settings:

```yaml
- name: "[Website Display Name]"
  id: "[unique-source-id]"
  url: "[agenda-page-url]"
  parser: "[parser-name]"  # Must match the key registered in PARSERS dict
  enabled: true
  rate_limit:
    requests_per_second: # according to research
    delay_between_pages: # according to research
  selectors:  # Only needed if using parser: "generic" (ConfigurableEventParser)
    event_list: "[css-selector]"
    event_item: "[css-selector]"
    name: "[css-selector]"
    date: "[css-selector]"
    time: "[css-selector]"
    location: "[css-selector]"
    description: "[css-selector]"
    category: "[css-selector]"
    image: "[css-selector]"
    link: "[css-selector]"
    tags: "[css-selector]"
  categories_map:
    "[Source Category 1]": "danse"
    "[Source Category 2]": "musique"
    "[Source Category 3]": "theatre"
    "[Source Category 4]": "art"
    "[Source Category 5]": "communaute"
```

#### Acceptance Criteria
- [ ] Source ID is unique and follows kebab-case convention
- [ ] All CSS selectors are validated against live HTML (if using generic parser)
- [ ] Category mapping covers all source categories
- [ ] Rate limiting is configured to respect the website

#### Tests
- [ ] Configuration loads without errors
- [ ] Source appears in `python crawl.py list-sources`
- [ ] Validation passes: `python crawl.py validate`

---

### Task 2: Create Parser

**File:** `crawler/src/parsers/[source_id].py`

Create a dedicated parser class that inherits from `BaseCrawler` and implements the `parse_events()` method.

> **Note:** In this codebase, "parser" and "crawler" are the same thing. Each parser is a `BaseCrawler` subclass in `crawler/src/parsers/`. There is no separate `crawler/src/crawlers/` directory.

#### Architecture Overview

The framework handles instantiation and orchestration automatically:

1. `crawl.py` reads `sources.yaml`, creates an instance of your parser class, and injects shared dependencies (`http_client`, `image_downloader`, `markdown_generator`)
2. The framework calls your parser's `crawl()` method (inherited from `BaseCrawler`)
3. `crawl()` fetches the source URL, wraps the HTML in an `HTMLParser` instance, and calls your `parse_events(parser)` method
4. Your `parse_events()` returns a list of `Event` objects
5. The framework then handles selection filtering, image downloading, and markdown generation via `process_event()` -- you do NOT need to do this yourself

#### Implementation Checklist
- [ ] Inherit from `BaseCrawler` (from `..crawler`)
- [ ] Set `source_name` class attribute
- [ ] Call `super().__init__(*args, **kwargs)` if overriding `__init__`
- [ ] Implement `parse_events(self, parser: HTMLParser) -> list[Event]`
- [ ] Handle pagination if needed (use `self.fetch_page()` or `self.fetch_pages()`)
- [ ] Handle French date/time formats
- [ ] Map categories using `self.map_category()`
- [ ] Map locations using `self.map_location()`
- [ ] Handle edge cases (missing fields, malformed data)
- [ ] Add proper error handling and logging
- [ ] Register parser in `crawler/src/parsers/__init__.py`

#### Code Structure — HTML Scraping Pattern

Use this pattern when the source is a standard website with HTML event listings:

```python
from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.parser import HTMLParser
from ..utils.sanitize import sanitize_description

logger = get_logger(__name__)


class [SourceName]Parser(BaseCrawler):
    """Parser for [Website Name] events."""

    source_name = "[Website Display Name]"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from [Website Name].

        Args:
            parser: HTMLParser instance wrapping the fetched page HTML.
                    Provides CSS selection, text extraction, link/image
                    resolution, and French date parsing utilities.

        Returns:
            List of Event objects (framework handles selection,
            image download, and markdown generation)
        """
        events = []

        # Example: extract event URLs from listing page
        event_links = parser.select(".event-card a")
        event_urls = [parser.get_link(link) for link in event_links]

        # Fetch detail pages concurrently (respects rate limiting)
        pages = self.fetch_pages(event_urls)

        for url, html in pages.items():
            if not html:
                continue
            event = self._parse_detail_page(url, html)
            if event:
                events.append(event)

        return events

    def _parse_detail_page(self, url: str, html: str) -> Event | None:
        """Parse a single event detail page."""
        detail = HTMLParser(html, url)

        name = detail.get_text(detail.soup, "h1")
        if not name:
            return None

        date = detail.parse_date(
            detail.get_text(detail.soup, ".date")
        )
        if not date:
            return None

        return Event(
            name=name,
            event_url=url,
            start_datetime=date,
            description=detail.get_text(detail.soup, ".description"),
            image=detail.get_image(detail.soup, ".event-image img"),
            categories=[self.map_category(
                detail.get_text(detail.soup, ".category")
            )],
            locations=[self.map_location("[venue-name]")],
            source_id=f"[source-id]:{some_unique_id}",
        )
```

#### Code Structure — REST API Pattern

Use this pattern when the source exposes a REST API (e.g. WordPress REST API, Tribe Events Calendar). Several existing parsers (Le Makeda, Journal Zébuline) use this approach. The key difference is that `parse_events()` fetches JSON from the API directly using `self.http_client.fetch()`, ignoring the HTMLParser argument from the base class.

```python
import json
from datetime import datetime

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import PARIS_TZ
from ..utils.parser import HTMLParser
from ..utils.sanitize import sanitize_description

logger = get_logger(__name__)

# API configuration
API_BASE = "https://[website]/wp-json/[api-path]"
PER_PAGE = 50


class [SourceName]Parser(BaseCrawler):
    """Parser for [Website Name] events via REST API."""

    source_name = "[Website Display Name]"

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Parse events from [Website Name] REST API.

        The HTMLParser argument is ignored since we fetch structured
        JSON from the API directly.

        Args:
            parser: HTMLParser (unused, required by base class interface)

        Returns:
            List of Event objects
        """
        events = []
        api_events = self._fetch_api_events()

        for event_data in api_events:
            try:
                event = self._parse_event(event_data)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event: {e}")

        return events

    def _fetch_api_events(self) -> list[dict]:
        """Fetch all events from the API with pagination."""
        all_events = []
        page = 1
        delay = self.config.get("rate_limit", {}).get("delay_between_pages", 3.0)

        while True:
            url = f"{API_BASE}/events?per_page={PER_PAGE}&page={page}"

            try:
                result = self.http_client.fetch(url, source_id=self.source_id)
            except Exception as e:
                logger.error(f"Failed to fetch API page {page}: {e}")
                break

            if not result.success:
                if result.status_code in (400, 404):
                    break  # End of pagination
                logger.error(f"API error on page {page}: HTTP {result.status_code}")
                break

            try:
                data = json.loads(result.html)
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse API response: {e}")
                break

            events = data.get("events", [])
            if not events:
                break

            all_events.extend(events)

            # Check pagination (adapt to the specific API)
            total_pages = data.get("total_pages", 1)
            if page >= total_pages:
                break

            page += 1
            import time
            time.sleep(delay)

        return all_events

    def _parse_event(self, data: dict) -> Event | None:
        """Parse a single event from API data."""
        name = sanitize_description(data.get("title", ""))
        if not name:
            return None

        # Parse datetime (adapt format to the specific API)
        start_date_str = data.get("start_date", "")
        if not start_date_str:
            return None
        try:
            dt = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S")
            start_datetime = dt.replace(tzinfo=PARIS_TZ)
        except ValueError:
            return None

        event_url = data.get("url", "")
        if not event_url:
            return None

        description = sanitize_description(data.get("description", ""))
        if len(description) > 160:
            description = description[:157] + "..."

        return Event(
            name=name,
            event_url=event_url,
            start_datetime=start_datetime,
            description=description,
            image=data.get("image", {}).get("url"),
            categories=[self.map_category(
                data.get("category", "")
            )],
            locations=[self.map_location("[venue-name]")],
            source_id=f"[source-id]:{data.get('id', '')}",
        )
```

#### Available BaseCrawler Helper Methods

Your parser inherits these from `BaseCrawler` (`crawler/src/crawler.py`):

| Method | Description |
|--------|-------------|
| `self.fetch_page(url)` | Fetch a single page, returns HTML string (empty on failure) |
| `self.fetch_pages(urls)` | Fetch multiple pages concurrently with thread pool, returns `dict[url, html]` |
| `self.http_client.fetch(url, source_id=self.source_id)` | Low-level HTTP fetch returning a result object with `.success`, `.status_code`, `.html`, `.headers`. Use this for API-based parsers that need status codes or response headers (e.g. pagination). For simple HTML fetches, prefer `fetch_page`/`fetch_pages`. |
| `self.map_category(raw)` | Map a source category string to standard taxonomy using `categories_map` from config |
| `self.map_location(raw)` | Map a location name to a known venue slug (delegates to `VenueManager`) |
| `self.venue_manager` | `VenueManager` instance for advanced venue matching (fuzzy matching, alias resolution). Available on `self` when provided during init. For simple lookups, prefer `self.map_location()`. |
| `self.config` | Source configuration dict from `sources.yaml`. Useful for reading rate limits (`self.config.get("rate_limit", {})`) and other source-specific settings. |
| `self.source_id` | Source ID from config (e.g. `"lemakeda"`) |
| `self.base_url` | Source URL from config |
| `self.category_map` | Category mapping dict from config. **Note:** In `sources.yaml` this key is `categories_map` (plural), but `crawl.py` translates it to `category_map` (singular) when constructing the config dict passed to the parser. |
| `self.http_client` | Shared HTTP client instance (see `http_client.fetch()` above) |

#### Available Utilities

| Utility | Import | Description |
|---------|--------|-------------|
| `sanitize_description(text)` | `from ..utils.sanitize import sanitize_description` | Strip HTML tags, decode entities, and normalize whitespace in description text. Recommended for cleaning API responses or HTML-rich content. |
| `PARIS_TZ` | `from ..utils.french_date import PARIS_TZ` | Paris timezone object for constructing timezone-aware datetimes |
| `FRENCH_MONTHS` | `from ..utils.french_date import FRENCH_MONTHS` | Dict mapping French month names to month numbers |

#### Available HTMLParser Methods

The `parser` argument in `parse_events()` is an `HTMLParser` instance (`crawler/src/utils/parser.py`):

| Method | Description |
|--------|-------------|
| `parser.select(selector)` | CSS select, returns `list[Tag]` |
| `parser.select_one(selector)` | CSS select first match, returns `Tag \| None` |
| `parser.get_text(element, selector="")` | Extract text from element or child |
| `parser.get_attr(element, attr, selector="")` | Extract attribute value |
| `parser.get_link(element, selector="a")` | Extract and resolve href to absolute URL |
| `parser.get_image(element, selector="img")` | Extract and resolve image src (handles lazy loading) |
| `parser.parse_date(text)` | Parse French dates (e.g. "26 janvier 2026", "26/01/2026") |
| `parser.parse_time(text)` | Extract time as "HH:MM" (e.g. from "19h30") |
| `parser.clean_text(text)` | Normalize whitespace |
| `parser.truncate(text, max_length=160)` | Truncate at word boundary |
| `parser.soup` | Direct access to underlying `BeautifulSoup` object |
| `parser.base_url` | Base URL for resolving relative links |

#### Event Model Fields

The `Event` dataclass (`crawler/src/models/event.py`):

```python
Event(
    # Required
    name: str,                      # Event title
    event_url: str,                 # Link to source page
    start_datetime: datetime,       # Date and time (use PARIS_TZ from utils.french_date)

    # Optional
    description: str = "",          # Short description (aim for ~160 chars)
    image: str | None = None,       # Image URL (framework downloads and converts to WebP)
    categories: list[str] = [],     # Standard slugs: danse, musique, theatre, art, communaute
    locations: list[str] = [],      # Venue slugs (use self.map_location())
    tags: list[str] = [],           # Free-form tags
    event_group_id: str | None = None,  # For multi-day events (shared across days)
    day_of: str | None = None,      # e.g. "Jour 1 sur 3"
    source_id: str | None = None,   # Unique ID for dedup, e.g. "lemakeda:12345"
    draft: bool = False,
)
```

#### Registration

Add the parser to `crawler/src/parsers/__init__.py`:

```python
# Add import at top
from .[source_id] import [SourceName]Parser

# Add entry to PARSERS dict
PARSERS = {
    ...
    "[source-id]": [SourceName]Parser,
}

# Add to __all__ list
__all__ = [
    ...
    "[SourceName]Parser",
]
```

#### Acceptance Criteria
- [ ] Parser inherits from `BaseCrawler` and implements `parse_events(self, parser: HTMLParser)`
- [ ] Parser extracts all required fields: name, event_url, start_datetime
- [ ] Parser extracts optional fields where available: description, image, categories, locations, tags
- [ ] Parser handles missing optional fields gracefully
- [ ] Parser respects rate limiting (uses `self.fetch_page()`/`self.fetch_pages()`)
- [ ] Parser logs progress and any issues encountered
- [ ] All extracted events have valid dates in the future
- [ ] Parser is registered in `crawler/src/parsers/__init__.py`

#### Tests
Create `crawler/tests/test_[source_id]_parser.py`:

- [ ] Test event URL extraction from listing page
- [ ] Test detail page parsing with sample HTML
- [ ] Test French date/time parsing
- [ ] Test category mapping
- [ ] Test handling of missing fields
- [ ] Test handling of malformed HTML
- [ ] Test pagination handling (if applicable)
- [ ] Mock HTTP requests for consistent testing

---

### Task 3: Improve Deduplicator

**File:** `crawler/src/deduplicator.py`

Update the deduplicator to handle new source patterns.

#### Implementation Checklist
- [ ] Analyze duplicate patterns specific to new source
- [ ] Add source-specific URL normalization if needed
- [ ] Consider venue name variations for matching
- [ ] Update merge strategy if new source provides better data for certain fields
- [ ] Add any new matching signals relevant to the source

#### Potential Improvements
```python
# Example: Add source-specific URL normalization
def _normalize_url(self, url: str) -> str:
    # Handle [source] specific URL patterns
    # e.g., remove tracking parameters, normalize paths
    pass

# Example: Improve venue matching
def _normalize_location(self, location: str) -> str:
    # Handle venue name variations from new source
    pass
```

#### Acceptance Criteria
- [ ] Events from new source are correctly deduplicated against existing events
- [ ] Events from new source are correctly deduplicated against themselves
- [ ] Merge strategy preserves the best quality data from all sources
- [ ] No false positives (different events marked as duplicates)
- [ ] No false negatives (same events not detected as duplicates)

#### Tests
Update `crawler/tests/test_deduplicator.py`:

- [ ] Test URL normalization for new source URLs
- [ ] Test cross-source duplicate detection with new source
- [ ] Test merge behavior when new source has better/worse data
- [ ] Test venue name matching with new source variations
- [ ] Test confidence scores for new source matches

---

### Task 4: Improve Selection Criteria

**File:** `crawler/config/selection-criteria.yaml`

Update selection criteria to properly filter events from the new source.

#### Implementation Checklist
- [ ] Add any new venue locations from the source to geography config
- [ ] Add source-specific positive keywords if relevant
- [ ] Add source-specific negative keywords if needed
- [ ] Update category mapping for any new categories
- [ ] Add location aliases for venue name variations

#### Configuration Updates
```yaml
geography:
  included_locations:
    # Add new venues from source
    - "[New Venue Name]"

  local_keywords:
    # Add venue-specific keywords
    - "[venue-nickname]"

keywords:
  positive:
    # Add source-specific positive keywords
    - "[keyword]"

  negative:
    # Add source-specific negative keywords
    - "[keyword]"

event_types:
  included:
    # Add new event types from source
    - "[event-type]"
```

#### Acceptance Criteria
- [ ] Events from Marseille area are correctly accepted
- [ ] Events outside Marseille area are correctly rejected
- [ ] Private/cancelled/sold-out events are correctly rejected
- [ ] Professional training events are correctly rejected
- [ ] Source-specific event types are properly categorized

#### Tests
Update `crawler/tests/test_selection.py`:

- [ ] Test geographic filtering with new venue locations
- [ ] Test keyword filtering with source-specific keywords
- [ ] Test event type filtering with source-specific types
- [ ] Test edge cases specific to new source

---

## Integration Testing

After all tasks are complete, perform full integration testing:

- [ ] Run full crawl: `python crawl.py run --source [source-id]`
- [ ] Verify events are created in `content/events/`
- [ ] Verify images are downloaded to `assets/images/events/`
- [ ] Verify no duplicate events are created
- [ ] Run Hugo build: `hugo --minify`
- [ ] Check generated HTML for new events
- [ ] Verify event pages display correctly
- [ ] Verify location pages display correctly
- [ ] Verify events appear in category listings
- [ ] Verify events appear in date listings
- [ ] Test search functionality with new events

---

## Definition of Done

This issue is complete when ALL of the following criteria are met:

### Code Quality
- [ ] All code follows existing project patterns and conventions
- [ ] All code has appropriate error handling and logging
- [ ] No linting errors or warnings
- [ ] Code is documented with docstrings and comments where needed

### Testing
- [ ] All new tests pass: `pytest crawler/tests/`
- [ ] Test coverage for new code is at least 80%
- [ ] Integration test crawl completes successfully
- [ ] No regressions in existing tests

### Functionality
- [ ] Crawler successfully extracts events from the source
- [ ] All event fields are correctly populated
- [ ] Events are correctly deduplicated
- [ ] Selection criteria correctly filter events
- [ ] Location pages exist for all venues
- [ ] Hugo site builds without errors

### Documentation
- [ ] Source is documented in sources.yaml with complete configuration
- [ ] Any special handling is documented in code comments
- [ ] Location pages have meaningful content

### Verification
- [ ] Manual review of 10+ crawled events for accuracy
- [ ] Spot check that dates, times, and locations are correct
- [ ] Verify images are displayed correctly
- [ ] Verify links to source website work

---

## Notes
- none

### Technical Considerations
- none

### Known Limitations
- none

### Future Improvements
- none
