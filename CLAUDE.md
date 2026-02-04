# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Massalia Events is a static website that aggregates cultural events from multiple sources in Marseille, France. It consists of:

1. **Hugo Static Site** - French-language event listings at massalia.events
2. **Python Crawler** - Fetches events from 11+ venues, generates Hugo content

## Common Commands

### Development
```bash
make serve               # Start Hugo dev server at localhost:1313
make build               # Production build
make clean               # Remove build artifacts
```

### Crawler (from project root)
```bash
cd crawler && source venv/bin/activate
python crawl.py run --dry-run    # Preview crawl
python crawl.py run              # Execute crawl
python crawl.py run --source lafriche  # Single source
python crawl.py list-sources     # Show available sources
python crawl.py validate         # Check configuration
```

### Generate Venue Pages (after crawling)
```bash
python scripts/generate-venue-pages.py --dry-run
python scripts/generate-venue-pages.py
```

### Testing & Linting
```bash
cd crawler
pytest                   # Run tests
pytest --cov=src         # With coverage
ruff check .             # Lint
ruff format .            # Format
```

## Architecture

### Crawler Pipeline
```
Sources (YAML config) → Parsers → Selection Filter → Classifier → Deduplicator → Markdown Generator
```

- **Parsers** (`crawler/src/parsers/`): Site-specific extractors inheriting from `BaseCrawler`. Registered in `PARSERS` dict in `__init__.py`.
- **Selection** (`crawler/src/selection.py`): Filters by geography, dates, event types, keywords using `config/selection-criteria.yaml`
- **Classifier** (`crawler/src/classifier.py`): Maps source categories to site categories (danse, musique, theatre, art, communaute)
- **Deduplicator** (`crawler/src/deduplicator.py`): Cross-source duplicate detection using URL matching, date+location+name similarity

### Data Flow
- Event markdown files: `content/events/YYYY/MM/DD/event-slug.fr.md`
- Event images: `assets/images/events/` (WebP format, 1200px max width)
- Venue metadata: `crawler/data/venues.yaml`
- Location pages: `content/locations/[slug]/_index.fr.md`

### Key Models
- **Event** (`crawler/src/models/event.py`): Matches Hugo front matter schema exactly
- **Venue** (`crawler/src/models/venue.py`): Location metadata for venue pages

## Adding a New Event Source

1. Create parser in `crawler/src/parsers/newsite.py`:
```python
from ..crawler import BaseCrawler
from ..models.event import Event

class NewSiteParser(BaseCrawler):
    source_name = "New Site"

    def parse_events(self, parser) -> list[Event]:
        # Extract events from parsed HTML
        pass
```

2. Register in `crawler/src/parsers/__init__.py`:
```python
from .newsite import NewSiteParser
PARSERS["newsite"] = NewSiteParser
```

3. Add source config to `crawler/config/sources.yaml`

## Event Categories

| Slug | French |
|------|--------|
| danse | Danse |
| musique | Musique |
| theatre | Théâtre |
| art | Art |
| communaute | Communauté |

## Configuration Files

- `crawler/config.yaml` - Main crawler config (HTTP settings, image processing, paths)
- `crawler/config/sources.yaml` - Event sources with URLs, parsers, category mappings
- `crawler/config/selection-criteria.yaml` - Geographic/date/type filters
- `hugo.toml` - Hugo site configuration

## Deployment

Push to `main` triggers GitHub Actions deployment to GitHub Pages. Site URL: https://massalia.events
