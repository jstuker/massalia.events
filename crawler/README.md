# Massalia Events Crawler

A command-line tool for crawling Marseille cultural event websites and generating Hugo-compatible content.

## Overview

The crawler fetches events from configured sources, extracts event data, downloads and optimizes hero images, and generates markdown files for the Hugo static site.

## Installation

### Prerequisites

- Python 3.11 or higher
- pip (Python package installer)

### Setup

1. Navigate to the crawler directory:
   ```bash
   cd crawler
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage

Run all enabled sources:
```bash
python crawl.py
```

### Command Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--config PATH` | `-c` | Path to configuration file (default: config.yaml) |
| `--source NAME` | `-s` | Run only the specified source by parser name |
| `--dry-run` | `-n` | Preview actions without writing files |
| `--log-level LEVEL` | `-l` | Override log level (DEBUG, INFO, WARNING, ERROR) |

### Examples

```bash
# Run only La Friche parser
python crawl.py --source lafriche

# Preview what would be created
python crawl.py --dry-run

# Verbose output for debugging
python crawl.py --log-level DEBUG

# Use custom config file
python crawl.py --config /path/to/config.yaml
```

## Configuration

The crawler is configured via `config.yaml`. Key settings:

### Output Directories

```yaml
output_dir: "../content/events"    # Hugo content directory
image_dir: "../static/images/events"  # Image storage
```

### HTTP Settings

```yaml
http:
  timeout: 30              # Request timeout in seconds
  retry_count: 3           # Number of retries on failure
  retry_delay: 1.0         # Base delay between retries
  rate_limit_delay: 1.0    # Delay between requests
  user_agent: "MassaliaEventsCrawler/1.0"
```

### Image Processing

```yaml
image_settings:
  max_width: 1200     # Maximum width in pixels
  quality: 85         # Output quality (1-100)
  format: "webp"      # Output format (webp, jpg, png)
```

### Event Sources

```yaml
sources:
  - name: "La Friche"
    url: "https://lafriche.org/agenda"
    parser: "lafriche"
    enabled: true
    category_map:
      "Spectacle": "theatre"
      "Concert": "musique"
```

## Adding New Parsers

To add support for a new event source:

1. Create a new parser in `src/parsers/`:
   ```python
   # src/parsers/mysite.py
   from ..crawler import BaseCrawler
   from ..models.event import Event
   from ..utils.parser import HTMLParser

   class MySiteParser(BaseCrawler):
       source_name = "My Site"

       def parse_events(self, parser: HTMLParser) -> list[Event]:
           events = []
           for card in parser.select(".event-card"):
               event = Event(
                   name=parser.get_text(card, ".title"),
                   event_url=parser.get_link(card, "a"),
                   start_datetime=...,
                   categories=[...],
                   locations=[...],
               )
               events.append(event)
           return events
   ```

2. Register the parser in `src/parsers/__init__.py`:
   ```python
   from .mysite import MySiteParser

   PARSERS = {
       "lafriche": LaFricheParser,
       "mysite": MySiteParser,
   }
   ```

3. Add configuration to `config.yaml`:
   ```yaml
   sources:
     - name: "My Site"
       url: "https://mysite.com/events"
       parser: "mysite"
       enabled: true
   ```

## Output Format

The crawler generates Hugo markdown files with YAML front matter:

```yaml
---
title: "Event Name"
date: 2026-01-26T19:00:00+01:00
draft: false
expiryDate: 2026-01-27T00:00:00+01:00
name: "Event Name"
eventURL: "https://source.com/event"
startTime: "19:00"
description: "Short description for SEO..."
categories:
  - "danse"
locations:
  - "la-friche"
dates:
  - "lundi-26-janvier"
tags:
  - "spectacle"
image: "/images/events/event-abc123.webp"
sourceId: "lafriche:event-123"
lastCrawled: 2026-01-26T12:00:00+01:00
expired: false
---
```

Files are saved in the date-based folder structure:
```
content/events/2026/01/26/event-name.fr.md
```

## Development

### Running Tests

```bash
pytest
```

With coverage:
```bash
pytest --cov=src --cov-report=html
```

### Linting

```bash
ruff check src/
ruff format src/
```

## Troubleshooting

### "No events found"

- Check that the source URL is accessible
- Verify CSS selectors match the current website structure
- Run with `--log-level DEBUG` to see detailed extraction info

### "Failed to download image"

- Check network connectivity
- Verify image URLs are valid
- Some sites may block automated downloads

### "Config file not found"

- Ensure you're running from the crawler directory
- Or specify config path with `--config`

## License

Part of the Massalia Events project.
