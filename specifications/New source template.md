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
- [ ] Identify events types and map them to the taxnonomy
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
  parser: "[parser-name]"  # Use existing parser or create new one
  enabled: true
  rate_limit:
    requests_per_second: # according to research
    delay_between_pages: # according to research
  selectors:  # If using configurable parser
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
- [ ] All CSS selectors are validated against live HTML
- [ ] Category mapping covers all source categories
- [ ] Rate limiting is configured to respect the website

#### Tests
- [ ] Configuration loads without errors
- [ ] Source appears in `python crawl.py list-sources`
- [ ] Validation passes: `python crawl.py validate`

---

### Task 2: Create Crawler

**File:** `crawler/src/crawlers/[source_id].py` (if custom crawler needed)

If the configurable parser is insufficient, create a dedicated crawler class.

#### Implementation Checklist
- [ ] Inherit from `BaseCrawler` abstract class
- [ ] Implement `parse_events()` method
- [ ] Handle pagination if needed
- [ ] Extract event URLs from listing page
- [ ] Fetch and parse individual event detail pages
- [ ] Handle French date/time formats
- [ ] Map categories to standard taxonomy
- [ ] Handle edge cases (missing fields, malformed data)
- [ ] Add proper error handling and logging

#### Code Structure
```python
class [SourceName]Crawler(BaseCrawler):
    """Crawler for [Website Name] events."""

    source_name = "[Website Display Name]"
    source_id = "[unique-source-id]"
    base_url = "[website-base-url]"

    def parse_events(self, html: str) -> list[Event]:
        """Parse events from the agenda page HTML."""
        pass

    def _parse_detail_page(self, url: str) -> Event | None:
        """Parse a single event detail page."""
        pass
```

#### Acceptance Criteria
- [ ] Crawler extracts all required fields: name, date, time, location, description, image, categories
- [ ] Crawler handles missing optional fields gracefully
- [ ] Crawler respects rate limiting configuration
- [ ] Crawler logs progress and any issues encountered
- [ ] All extracted events have valid dates in the future

#### Tests
Create `crawler/tests/test_[source_id]_crawler.py`:

- [ ] Test event URL extraction from listing page
- [ ] Test detail page parsing with sample HTML
- [ ] Test French date/time parsing
- [ ] Test category mapping
- [ ] Test handling of missing fields
- [ ] Test handling of malformed HTML
- [ ] Test pagination handling (if applicable)
- [ ] Mock HTTP requests for consistent testing

---

### Task 3: Create Parser

**File:** `crawler/src/parsers/[source_id].py`

Create a dedicated parser if the HTML structure requires special handling.

#### Implementation Checklist
- [ ] Extract event data from HTML using BeautifulSoup
- [ ] Parse French dates with multiple format support
- [ ] Handle relative URLs and convert to absolute
- [ ] Extract and clean description text
- [ ] Extract image URLs with fallback handling
- [ ] Parse tags and categories
- [ ] Register parser in `crawler/src/parsers/__init__.py`

#### Code Structure
```python
class [SourceName]Parser:
    """Parser for [Website Name] HTML structure."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def parse_listing(self, html: str) -> list[str]:
        """Extract event URLs from listing page."""
        pass

    def parse_event(self, html: str, url: str) -> ParsedEvent | None:
        """Parse a single event from detail page HTML."""
        pass

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse French date string to datetime."""
        pass
```

#### Acceptance Criteria
- [ ] Parser handles all variations of HTML structure on the source website
- [ ] Parser correctly extracts all available event fields
- [ ] Parser converts relative URLs to absolute URLs
- [ ] Parser is registered in the parser factory
- [ ] Parser returns `None` for unparseable events (not exceptions)

#### Tests
Create `crawler/tests/test_[source_id]_parser.py`:

- [ ] Test listing page parsing with real HTML samples
- [ ] Test event detail parsing with multiple HTML samples
- [ ] Test date parsing with various French date formats
- [ ] Test URL resolution for relative links
- [ ] Test handling of missing elements
- [ ] Test image URL extraction
- [ ] Test category and tag extraction

---

### Task 4: Improve Deduplicator

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

### Task 5: Improve Selection Criteria

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