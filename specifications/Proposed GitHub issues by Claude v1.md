# massalia.events - GitHub Issues Specification

**Product:** massalia.events - Event Aggregator for Marseille
**Version:** 1.0
**Author:** Jürg Stuker
**Date:** 25 January 2025

---

## Summary

| Epic | Issues | Count |
|------|--------|-------|
| 1. Project Setup | #1-#4 | 4 |
| 2. Data Model & Taxonomy | #5-#10 | 6 |
| 3. User Interface | #11-#18 | 8 |
| 4. Crawler System | #19-#28 | 10 |
| 5. Administrative Features | #29-#31 | 3 |
| 6. Localization | #32-#33 | 2 |
| 7. Deployment & Publishing | #34-#36 | 3 |
| **TOTAL** | | **36** |

---

## Epic 1: Project Setup & Infrastructure

### Issue #1: Initialize Project Repository
**Labels:** `setup`, `infrastructure`, `priority:high`

**Description:**
Create the Git repository structure for massalia.events with proper organization for Hugo site and crawler components.

**Tasks:**
- [ ] Create Git repository named `massalia-events`
- [ ] Add .gitignore for Hugo, Python, Node.js, and IDE files
- [ ] Create directory structure:
  ```
  /
  ├── hugo/              # Hugo site
  ├── crawler/           # Crawler application
  ├── config/            # Configuration files (sources, selection criteria)
  ├── docs/              # Documentation
  └── scripts/           # Utility scripts
  ```
- [ ] Create initial README.md with project overview
- [ ] Set up .editorconfig for consistent formatting

**Acceptance Criteria:**
- [ ] Repository is created and cloneable
- [ ] .gitignore excludes: public/, resources/, node_modules/, __pycache__/, .env, *.log
- [ ] All directories exist with placeholder README files
- [ ] Repository can be cloned and structure is clear

---

### Issue #2: Install and Configure Hugo Extended
**Labels:** `setup`, `hugo`, `priority:high`

**Description:**
Install Hugo extended version (required for Blowfish theme SCSS) and create the base site structure.

**Tasks:**
- [ ] Document Hugo extended installation for macOS/Linux/Windows
- [ ] Run `hugo new site hugo` to create site in /hugo directory
- [ ] Configure `hugo.toml` with base settings:
  - baseURL (placeholder for production URL)
  - languageCode = "fr"
  - title = "Événements Marseille"
  - defaultContentLanguage = "fr"
- [ ] Set up development server script
- [ ] Verify `hugo server` runs without errors

**Acceptance Criteria:**
- [ ] Hugo extended version ≥ 0.112.0 is installed
- [ ] `hugo version` shows "extended"
- [ ] Site builds with `hugo` command
- [ ] `hugo server` launches local preview at localhost:1313

---

### Issue #3: Install and Configure Blowfish Theme
**Labels:** `setup`, `hugo`, `theme`, `priority:high`

**Description:**
Install Blowfish theme as Hugo module and configure base theme settings for the event calendar.

**Tasks:**
- [ ] Initialize Hugo modules: `hugo mod init github.com/[user]/massalia-events`
- [ ] Add Blowfish to hugo.toml:
  ```toml
  [module]
    [[module.imports]]
      path = "github.com/nunocoracao/blowfish/v2"
  ```
- [ ] Run `hugo mod get -u` to download theme
- [ ] Copy Blowfish example config files to /hugo/config/_default/
- [ ] Configure languages.fr.toml for French
- [ ] Configure params.toml with site branding
- [ ] Verify theme renders with `hugo server`

**Acceptance Criteria:**
- [ ] Blowfish theme loads without errors
- [ ] Site displays with Blowfish styling
- [ ] French is the default language
- [ ] No JavaScript console errors

---

### Issue #4: Configure Hugo Taxonomies
**Labels:** `setup`, `hugo`, `taxonomy`, `priority:high`

**Description:**
Configure Hugo's taxonomy system for categories, locations, and dates as specified in the product requirements.

**Tasks:**
- [ ] Add taxonomy configuration to hugo.toml:
  ```toml
  [taxonomies]
    category = "categories"
    location = "locations"
    date = "dates"
  ```
- [ ] Create taxonomy list templates in /layouts/taxonomies/
- [ ] Create taxonomy term templates
- [ ] Configure taxonomy URL structure
- [ ] Test with sample content

**Acceptance Criteria:**
- [ ] Three taxonomies configured: categories, locations, dates
- [ ] Taxonomy pages generate at /categories/, /locations/, /dates/
- [ ] Events can be assigned to multiple taxonomy terms
- [ ] Taxonomy archives list all tagged events

---

## Epic 2: Data Model & Taxonomy

### Issue #5: Define Event Content Type and Archetype
**Labels:** `data-model`, `hugo`, `priority:high`

**Description:**
Create the event content type with complete front matter schema matching the specification examples.

**Tasks:**
- [ ] Create `/hugo/archetypes/events.md` with template:
  ```yaml
  ---
  title: "{{ replace .Name "-" " " | title }}"
  name: ""
  date: {{ .Date }}
  categories: []
  locations: []
  dates: []
  startTime: ""
  url: ""
  description: ""
  image: ""
  expired: false
  sourceId: ""
  lastCrawled: {{ .Date }}
  ---
  ```
- [ ] Document each field's purpose and format
- [ ] Create 5 sample events from specification examples
- [ ] Verify events render correctly

**Acceptance Criteria:**
- [ ] Archetype creates events with all required fields
- [ ] Sample events from spec render on site
- [ ] Front matter validates without errors
- [ ] Fields match specification: name, categories, locations, dates, startTime, url

---

### Issue #6: Create Content Folder Structure by Date
**Labels:** `data-model`, `hugo`, `priority:high`

**Description:**
Implement date-based folder structure for storing events: /content/events/YYYY/MM/DD/

**Tasks:**
- [ ] Create /hugo/content/events/ directory
- [ ] Create _index.md for events section with French title
- [ ] Define folder structure pattern: `/events/YYYY/MM/DD/event-slug.md`
- [ ] Configure permalinks in hugo.toml for clean URLs
- [ ] Create script to generate folder structure for new events
- [ ] Test with events on different dates

**Acceptance Criteria:**
- [ ] Events are stored in date-based folders
- [ ] Folder structure: /content/events/2025/01/25/event-name.md
- [ ] Events are accessible via clean URLs
- [ ] Date folders are created automatically when needed

---

### Issue #7: Define Category Taxonomy Values
**Labels:** `data-model`, `taxonomy`, `priority:medium`

**Description:**
Define the complete list of event categories with French labels based on specification examples.

**Tasks:**
- [ ] Create category taxonomy terms from examples:
  - Dance (Danse)
  - Music (Musique)
  - Théâtre
  - Art
  - Community (Communauté)
- [ ] Consider additional categories: Cinema, Festival, Sport, Conférence, Enfants
- [ ] Create /hugo/content/categories/_index.md
- [ ] Create individual category pages with descriptions
- [ ] Add category icons or colors for visual distinction

**Acceptance Criteria:**
- [ ] Minimum 5 categories defined from specification
- [ ] Each category has French label
- [ ] Category archive pages work
- [ ] Categories can be extended without code changes

---

### Issue #8: Define Location Taxonomy Values
**Labels:** `data-model`, `taxonomy`, `priority:medium`

**Description:**
Define Marseille venue locations as taxonomy terms based on specification examples.

**Tasks:**
- [ ] Create location taxonomy terms from examples:
  - KLAP Maison pour la danse
  - La Friche
  - La Criée
  - Galerie Château de Servières
  - Notre-Dame de la Garde
- [ ] Create /hugo/content/locations/_index.md
- [ ] Create individual location pages
- [ ] Consider storing address/coordinates for future map feature
- [ ] Allow new locations to be added dynamically

**Acceptance Criteria:**
- [ ] Initial venues from spec are configured
- [ ] Location archive pages show all events at venue
- [ ] New locations can be added via content files
- [ ] Location names display correctly with French characters

---

### Issue #9: Implement Multi-Day Event Handling
**Labels:** `data-model`, `feature`, `priority:medium`

**Description:**
When an event spans multiple days, create separate event pages for each day so the event appears in each day's listing.

**Tasks:**
- [ ] Define multi-day event detection logic (date range in source)
- [ ] Create script to generate multiple .md files from single source event
- [ ] Add `eventGroupId` field to link related pages
- [ ] Add `dayOf` field (e.g., "Jour 2 sur 5")
- [ ] Ensure each page has correct date in folder path
- [ ] Handle recurring events (weekly, monthly)
- [ ] Set reasonable limit (max 30 days)

**Acceptance Criteria:**
- [ ] Multi-day events create N separate pages (one per day)
- [ ] Each page appears in correct day's event listing
- [ ] Pages are linked via eventGroupId
- [ ] Events spanning >30 days are capped or flagged

---

### Issue #10: Implement Event Expiration System
**Labels:** `data-model`, `feature`, `priority:high`

**Description:**
Implement the expired metadata flag to hide past events from the public site while keeping them in the repository.

**Tasks:**
- [ ] Add `expired: boolean` field to front matter schema
- [ ] Create Hugo template logic to exclude expired events:
  ```go
  {{ $events := where .Pages "Params.expired" "!=" true }}
  ```
- [ ] Create script to batch-update expired status daily
- [ ] Define expiration rule: midnight Europe/Paris after event date
- [ ] Ensure expired events return 404 or redirect
- [ ] Keep expired events in Git history for reference

**Acceptance Criteria:**
- [ ] Events with `expired: true` don't appear in listings
- [ ] Events with `expired: true` don't appear in search
- [ ] Direct URLs to expired events show 404
- [ ] Script can mark all past events as expired
- [ ] Expired events remain in /content/ folder

---

## Epic 3: User Interface

### Issue #11: Create Landing Page Layout
**Labels:** `ui`, `template`, `priority:high`

**Description:**
Build the main landing page displaying today's events with the 7-day navigation component.

**Tasks:**
- [ ] Create /hugo/layouts/events/list.html template
- [ ] Implement page structure:
  - Header with site title
  - 7-day navigation bar
  - Event cards grid
  - Footer
- [ ] Set "today" as default view on page load
- [ ] Add French page title: "Événements à Marseille"
- [ ] Configure as site homepage or /events/

**Acceptance Criteria:**
- [ ] Landing page loads at configured URL
- [ ] Today's events display by default
- [ ] Navigation bar is visible and centered
- [ ] Event cards render below navigation
- [ ] Page is fully in French

---

### Issue #12: Build 7-Day Navigation Component
**Labels:** `ui`, `component`, `priority:high`

**Description:**
Create the day selector showing "Aujourd'hui" (today) plus 6 following days with French day names.

**Tasks:**
- [ ] Create /hugo/layouts/partials/day-navigation.html
- [ ] Display "Aujourd'hui" as primary/centered element
- [ ] Generate next 6 days dynamically with French names:
  - Lundi, Mardi, Mercredi, Jeudi, Vendredi, Samedi, Dimanche
- [ ] Format each day: "Lundi 27 janvier"
- [ ] Implement active state styling for selected day
- [ ] Add click/tap handlers to filter events
- [ ] Handle week boundary (Samedi → Dimanche → Lundi)

**Acceptance Criteria:**
- [ ] Navigation shows 7 days starting from today
- [ ] "Aujourd'hui" is highlighted as default selection
- [ ] Day names are in French
- [ ] Clicking a day shows that day's events
- [ ] Active day has distinct visual style
- [ ] Navigation works with keyboard (accessibility)

---

### Issue #13: Create Event Card Component
**Labels:** `ui`, `component`, `priority:high`

**Description:**
Build the event card displaying: category, location, name, date, start time. Card links to detail page.

**Tasks:**
- [ ] Create /hugo/layouts/partials/event-card.html
- [ ] Display required fields:
  - Category (with color/icon)
  - Location name
  - Event name (title)
  - Date in French format
  - Start time (HH:MM)
- [ ] Make entire card clickable (link to detail page)
- [ ] Add hover state with visual feedback
- [ ] Handle long event names (truncation with ellipsis)
- [ ] Add subtle shadow or border for card definition

**Acceptance Criteria:**
- [ ] Card displays all 5 required fields
- [ ] Category has visual distinction (color badge or icon)
- [ ] Clicking card navigates to event detail
- [ ] Hover provides visual feedback
- [ ] Long titles truncate gracefully
- [ ] Card renders correctly on all viewports

---

### Issue #14: Create Event Detail Page
**Labels:** `ui`, `template`, `priority:high`

**Description:**
Build the single event page showing all event information plus description, image, and source link.

**Tasks:**
- [ ] Create /hugo/layouts/events/single.html
- [ ] Display card fields prominently at top:
  - Category, Location, Name, Date, Time
- [ ] Add description section below
- [ ] Display hero image if available:
  - Use placeholder image if none exists
  - Optimize image loading (lazy load)
- [ ] Add prominent source link: "Voir l'événement original →"
  - Link opens in new tab
  - Style as button or prominent link
- [ ] Add back navigation: "← Retour aux événements"

**Acceptance Criteria:**
- [ ] All card fields visible at top of page
- [ ] Description renders with proper formatting
- [ ] Image displays or shows placeholder
- [ ] Source URL link is prominent and works
- [ ] Back link returns to event list
- [ ] Page is fully in French

---

### Issue #15: Implement Event Filtering by Day
**Labels:** `ui`, `feature`, `priority:high`

**Description:**
Implement the logic to filter and display events for the selected day from the 7-day navigation.

**Tasks:**
- [ ] Create Hugo template logic to filter events by date
- [ ] Match events where `dates` taxonomy includes selected day
- [ ] Handle page reload approach (static site)
- [ ] Consider URL structure: /events/, /events/demain/, /events/2025-01-27/
- [ ] Show "Aucun événement" message if no events for day
- [ ] Sort events by startTime within each day

**Acceptance Criteria:**
- [ ] Clicking day shows only that day's events
- [ ] Events are sorted by start time
- [ ] Empty days show friendly French message
- [ ] URL reflects selected day (optional but nice)
- [ ] Filter works with browser back button

---

### Issue #16: Implement Search Functionality
**Labels:** `ui`, `feature`, `priority:medium`

**Description:**
Configure Hugo/Blowfish search to find events within the 7-day window only.

**Tasks:**
- [ ] Enable Blowfish search in params.toml
- [ ] Configure search index to include events
- [ ] Filter search index to exclude expired events
- [ ] Limit search to 7-day window (today + 6 days)
- [ ] Add search input to landing page
- [ ] Style search results to match event cards
- [ ] Add French placeholder: "Rechercher un événement..."

**Acceptance Criteria:**
- [ ] Search input visible on landing page
- [ ] Search finds events by name, description, location
- [ ] Results exclude expired events
- [ ] Results limited to 7-day window
- [ ] "Aucun résultat" message displays in French
- [ ] Search is fast (< 500ms)

---

### Issue #17: Implement Responsive Design
**Labels:** `ui`, `responsive`, `priority:high`

**Description:**
Ensure UI works correctly on mobile, tablet, and desktop viewports as specified.

**Tasks:**
- [ ] Define breakpoints:
  - Mobile: < 768px
  - Tablet: 768px - 1024px
  - Desktop: > 1024px
- [ ] Adjust day navigation:
  - Mobile: horizontal scroll or stacked
  - Tablet/Desktop: full row
- [ ] Adjust event card grid:
  - Mobile: 1 column
  - Tablet: 2 columns
  - Desktop: 3-4 columns
- [ ] Ensure touch targets ≥ 44x44px
- [ ] Test on actual devices or emulators
- [ ] Verify text readable without zooming

**Acceptance Criteria:**
- [ ] Site works on mobile viewport (iPhone SE size)
- [ ] Site works on tablet viewport (iPad size)
- [ ] Site works on desktop viewport (1920px)
- [ ] No horizontal scrolling on page body
- [ ] All interactive elements are tappable on touch
- [ ] Text readable on all sizes

---

### Issue #18: Optimize for Lighthouse Performance Score 100
**Labels:** `ui`, `performance`, `priority:medium`

**Description:**
Optimize the site to achieve Google Lighthouse performance score of 100.

**Tasks:**
- [ ] Run initial Lighthouse audit and document baseline
- [ ] Optimize images:
  - Use WebP format
  - Implement responsive images (srcset)
  - Lazy load below-fold images
- [ ] Optimize CSS:
  - Inline critical CSS
  - Remove unused styles
- [ ] Optimize JavaScript:
  - Minimize bundle size
  - Defer non-critical scripts
- [ ] Configure caching headers
- [ ] Minimize Cumulative Layout Shift (CLS)
- [ ] Optimize Largest Contentful Paint (LCP)
- [ ] Run final Lighthouse audit

**Acceptance Criteria:**
- [ ] Lighthouse Performance score = 100
- [ ] First Contentful Paint < 1.8s
- [ ] Largest Contentful Paint < 2.5s
- [ ] Cumulative Layout Shift < 0.1
- [ ] Time to Interactive < 3.8s

---

## Epic 4: Crawler System

### Issue #19: Set Up Crawler Project Structure
**Labels:** `crawler`, `setup`, `priority:high`

**Description:**
Create the crawler application with proper structure for local execution.

**Tasks:**
- [ ] Create /crawler directory with structure:
  ```
  crawler/
  ├── src/               # Source code
  ├── tests/             # Unit tests
  ├── output/            # Generated Hugo content
  └── logs/              # Log files
  ```
- [ ] Choose technology: Python (recommended) or Node.js
- [ ] Create requirements.txt or package.json
- [ ] Set up virtual environment (Python) or package management
- [ ] Create main entry point: `crawler.py` or `index.js`
- [ ] Add .env.example for configuration
- [ ] Create Makefile with common commands

**Acceptance Criteria:**
- [ ] Crawler runs with single command
- [ ] Dependencies install via `pip install -r requirements.txt`
- [ ] Main script executes without errors (empty run)
- [ ] Logs are created in /logs directory

---

### Issue #20: Create Source Sites Configuration
**Labels:** `crawler`, `config`, `priority:high`

**Description:**
Create configuration file defining event source websites to crawl, stored in local files as specified.

**Tasks:**
- [ ] Create /config/sources.yaml with schema:
  ```yaml
  sources:
    - name: "Kelemenis"
      url: "https://www.kelemenis.fr/..."
      enabled: true
      selectors:
        eventList: ".event-list"
        eventItem: ".event"
        title: ".event-title"
        date: ".event-date"
        # etc.
  ```
- [ ] Add initial sources from specification examples:
  - kelemenis.fr
  - shotgun.live
  - theatre-lacriee.com
  - sortiramarseille.fr
  - madeinmarseille.net
- [ ] Implement config loader with validation
- [ ] Support enabling/disabling individual sources
- [ ] Document configuration format

**Acceptance Criteria:**
- [ ] sources.yaml exists with documented schema
- [ ] At least 5 sources configured from spec examples
- [ ] Config validation catches errors
- [ ] Sources can be enabled/disabled individually
- [ ] Documentation explains all options

---

### Issue #21: Create Selection Criteria Configuration
**Labels:** `crawler`, `config`, `priority:high`

**Description:**
Create the selection criteria document that determines which events to include, stored locally as specified.

**Tasks:**
- [ ] Create /config/selection-criteria.yaml:
  ```yaml
  version: "1.0"
  lastUpdated: "2025-01-25"

  include:
    locations:
      - "Marseille"
      - "13*"  # Bouches-du-Rhône postal codes
    categories:
      - all

  exclude:
    keywords:
      - "annulé"
      - "complet"
    venues: []

  dateRange:
    future: true
    maxDaysAhead: 90
  ```
- [ ] Implement criteria evaluation logic
- [ ] Log events that are rejected with reason
- [ ] Make criteria easily editable
- [ ] Document each criterion with examples

**Acceptance Criteria:**
- [ ] selection-criteria.yaml exists and is valid
- [ ] Criteria filter events correctly
- [ ] Rejected events are logged with reason
- [ ] Criteria can be updated without code changes
- [ ] Documentation includes examples

---

### Issue #22: Implement Web Page Fetcher
**Labels:** `crawler`, `core`, `priority:high`

**Description:**
Build the component that fetches web pages from configured sources.

**Tasks:**
- [ ] Create HTTP client with:
  - Configurable User-Agent
  - Timeout handling (30s default)
  - Retry logic (3 attempts, exponential backoff)
- [ ] Handle HTTP errors: 404, 500, timeout
- [ ] Implement rate limiting (1 request/second per domain)
- [ ] Support both static HTML and JavaScript-rendered pages
- [ ] Log all requests with status
- [ ] Handle character encoding (UTF-8, Latin-1)

**Acceptance Criteria:**
- [ ] Fetcher retrieves pages from configured URLs
- [ ] Retries work on transient failures
- [ ] Rate limiting prevents server overload
- [ ] All requests logged with timestamp and status
- [ ] Encoding handled correctly for French characters

---

### Issue #23: Implement Event Data Extractor
**Labels:** `crawler`, `extraction`, `priority:high`

**Description:**
Build the component that extracts event data from HTML pages using configurable selectors.

**Tasks:**
- [ ] Implement HTML parser (BeautifulSoup for Python)
- [ ] Create extraction logic using CSS selectors from config
- [ ] Extract all required fields:
  - name (event title)
  - date (parse to ISO format)
  - startTime (parse to HH:MM)
  - location (venue name)
  - description (text content)
  - url (source page URL)
  - imageUrl (hero image)
- [ ] Handle missing optional fields gracefully
- [ ] Clean extracted data (trim, normalize whitespace)
- [ ] Parse French dates ("Samedi 24 janvier" → 2025-01-24)

**Acceptance Criteria:**
- [ ] Extractor parses HTML and extracts all fields
- [ ] Different source formats supported via selectors
- [ ] French dates parsed correctly
- [ ] Missing fields don't cause errors
- [ ] Data is cleaned and normalized

---

### Issue #24: Implement Hero Image Downloader
**Labels:** `crawler`, `images`, `priority:medium`

**Description:**
Download and process event hero images to Blowfish-optimized format.

**Tasks:**
- [ ] Detect image URL from:
  - og:image meta tag
  - Main content image
  - Event-specific image selector
- [ ] Download image to local storage
- [ ] Resize to Blowfish feature image dimensions
- [ ] Convert to WebP format for performance
- [ ] Generate unique filename: `{event-slug}-hero.webp`
- [ ] Store in /hugo/static/images/events/
- [ ] Handle missing images (use default placeholder)
- [ ] Skip re-download if image exists and unchanged

**Acceptance Criteria:**
- [ ] Images downloaded from event pages
- [ ] Images resized to consistent dimensions
- [ ] Output format is WebP
- [ ] Unique filenames prevent conflicts
- [ ] Missing images use placeholder
- [ ] Existing images not re-downloaded

---

### Issue #25: Implement Selection Criteria Engine
**Labels:** `crawler`, `selection`, `priority:high`

**Description:**
Build the component that evaluates events against selection criteria to include or exclude.

**Tasks:**
- [ ] Load selection criteria from /config/selection-criteria.yaml
- [ ] Implement filters:
  - Location filter (Marseille area)
  - Date filter (future events only)
  - Keyword filter (exclude "annulé", etc.)
  - Category filter (if specified)
- [ ] Return include/exclude decision with reason
- [ ] Log all exclusions with specific reason
- [ ] Support updating criteria without restart

**Acceptance Criteria:**
- [ ] Events evaluated against all criteria
- [ ] Past events automatically excluded
- [ ] Excluded keywords filter works
- [ ] Location filter restricts to Marseille
- [ ] Each rejection logged with reason
- [ ] Criteria reloadable without restart

---

### Issue #26: Implement Category Classifier
**Labels:** `crawler`, `classification`, `priority:medium`

**Description:**
Automatically assign categories to events based on content analysis.

**Tasks:**
- [ ] Create keyword-to-category mapping:
  ```yaml
  Music: [concert, musique, DJ, live, festival]
  Dance: [danse, ballet, chorégraphie]
  Théâtre: [théâtre, pièce, comédie, spectacle]
  Art: [exposition, art, galerie, vernissage]
  Community: [atelier, rencontre, conférence]
  ```
- [ ] Analyze event name, description, and venue
- [ ] Handle events matching multiple categories (pick primary)
- [ ] Default to "Autre" if no match
- [ ] Allow manual override in source config
- [ ] Log classification decisions

**Acceptance Criteria:**
- [ ] Events assigned categories automatically
- [ ] Classification based on text content
- [ ] Unmatched events get "Autre" category
- [ ] Multiple matches resolved to single category
- [ ] Classification logic is configurable

---

### Issue #27: Implement Duplicate Detection
**Labels:** `crawler`, `deduplication`, `priority:high`

**Description:**
Detect duplicate events from different sources using booking link and date-time-location matching.

**Tasks:**
- [ ] Check for exact URL match (same source page)
- [ ] Check for same booking/ticket link
- [ ] Check for same date + time + location combination
- [ ] Implement fuzzy title matching (similarity > 85%)
- [ ] Strategy for duplicates:
  - Skip if exact duplicate
  - Merge if partial match (combine info from both)
- [ ] Log duplicate detection decisions
- [ ] Prefer source with more complete information

**Acceptance Criteria:**
- [ ] Same URL detected as duplicate
- [ ] Same booking link detected as duplicate
- [ ] Same date-time-location detected as duplicate
- [ ] Similar titles flagged for review
- [ ] Duplicates merged or skipped
- [ ] Most complete information preserved

---

### Issue #28: Implement Hugo Content Generator
**Labels:** `crawler`, `output`, `priority:high`

**Description:**
Generate Hugo markdown files from processed events in the correct folder structure.

**Tasks:**
- [ ] Create markdown template matching archetype
- [ ] Generate front matter with all fields
- [ ] Generate content body with description
- [ ] Create correct folder path: /hugo/content/events/YYYY/MM/DD/
- [ ] Generate URL-safe slugs for filenames
- [ ] Copy processed images to correct location
- [ ] Handle updates to existing events
- [ ] Output to /crawler/output/ for review before integration

**Acceptance Criteria:**
- [ ] Valid Hugo markdown files generated
- [ ] Front matter matches defined schema
- [ ] Files in correct date-based folders
- [ ] Filenames are URL-safe slugs
- [ ] Images copied to Hugo static folder
- [ ] Existing events can be updated

---

## Epic 5: Administrative Features

### Issue #29: Implement Logging System
**Labels:** `admin`, `logging`, `priority:high`

**Description:**
Create comprehensive logging with configurable levels (critical, warning, info) as specified.

**Tasks:**
- [ ] Set up logging framework (Python: logging module)
- [ ] Implement log levels: CRITICAL, ERROR, WARNING, INFO, DEBUG
- [ ] Configure log output:
  - File: /crawler/logs/crawler-YYYY-MM-DD.log
  - Console: for interactive use
- [ ] Implement log rotation (keep 30 days)
- [ ] Add LOG_LEVEL environment variable
- [ ] Include context in log entries:
  - Timestamp
  - Level
  - Source/module
  - Message
- [ ] Create separate logs for different concerns if needed

**Acceptance Criteria:**
- [ ] Logging active for all operations
- [ ] Log level configurable via LOG_LEVEL env var
- [ ] Logs written to files with rotation
- [ ] Timestamps in ISO format
- [ ] DEBUG mode provides verbose output
- [ ] CRITICAL errors clearly visible

---

### Issue #30: Create Crawler CLI Interface
**Labels:** `admin`, `cli`, `priority:high`

**Description:**
Build command-line interface for running and managing the crawler locally.

**Tasks:**
- [ ] Create CLI with argument parser (argparse/click)
- [ ] Implement commands:
  - `crawl` - run full crawl of all enabled sources
  - `crawl --source NAME` - crawl single source
  - `validate` - validate configuration files
  - `status` - show last crawl statistics
  - `expire` - mark past events as expired
- [ ] Add flags:
  - `--dry-run` - preview without writing files
  - `--verbose` - detailed output
  - `--log-level LEVEL` - override log level
- [ ] Display progress during crawl
- [ ] Return appropriate exit codes (0=success, 1=error)

**Acceptance Criteria:**
- [ ] CLI invokable: `python crawler.py crawl`
- [ ] Help text: `python crawler.py --help`
- [ ] Single source crawl works
- [ ] Dry run shows what would be created
- [ ] Exit codes indicate success/failure

---

### Issue #31: Document Manual Crawl and Publish Workflow
**Labels:** `admin`, `documentation`, `priority:medium`

**Description:**
Document the complete workflow for crawling locally and publishing to GitHub as specified.

**Tasks:**
- [ ] Document prerequisites:
  - Python/Node.js installation
  - Hugo installation
  - Git configuration
- [ ] Document crawl execution:
  ```bash
  cd crawler
  python crawler.py crawl
  # Review output in /crawler/output/
  cp -r output/* ../hugo/content/events/
  ```
- [ ] Document Hugo build and preview:
  ```bash
  cd hugo
  hugo server  # Preview locally
  hugo         # Build for production
  ```
- [ ] Document GitHub publishing:
  ```bash
  git add .
  git commit -m "Add events from crawl YYYY-MM-DD"
  git push origin main
  ```
- [ ] Document troubleshooting common issues
- [ ] Create quick reference command sheet

**Acceptance Criteria:**
- [ ] Complete workflow documented in README
- [ ] Commands are copy-pasteable
- [ ] Troubleshooting guide exists
- [ ] New administrator can follow process

---

## Epic 6: Localization

### Issue #32: Implement French UI Labels
**Labels:** `localization`, `ui`, `priority:high`

**Description:**
Translate all user interface text to French.

**Tasks:**
- [ ] Create /hugo/i18n/fr.yaml with translations:
  ```yaml
  today: "Aujourd'hui"
  search: "Rechercher"
  searchPlaceholder: "Rechercher un événement..."
  noResults: "Aucun résultat"
  noEvents: "Aucun événement ce jour"
  viewOriginal: "Voir l'événement original"
  back: "Retour aux événements"
  category: "Catégorie"
  location: "Lieu"
  time: "Heure"
  ```
- [ ] Apply translations in all templates
- [ ] Translate error messages
- [ ] Translate meta descriptions
- [ ] Review for hardcoded English strings

**Acceptance Criteria:**
- [ ] All UI text in French
- [ ] No English strings visible to users
- [ ] French accented characters display correctly
- [ ] i18n file complete and organized

---

### Issue #33: Implement French Date and Time Formatting
**Labels:** `localization`, `formatting`, `priority:high`

**Description:**
Configure French date and time display throughout the application.

**Tasks:**
- [ ] Configure Hugo date format for French:
  ```toml
  [params]
    dateFormat = "2 January 2006"
  ```
- [ ] Create date formatting partial with French output:
  - "Lundi 27 janvier 2025"
  - Day names: Lundi, Mardi, Mercredi, Jeudi, Vendredi, Samedi, Dimanche
  - Month names: janvier, février, mars, avril, mai, juin, juillet, août, septembre, octobre, novembre, décembre
- [ ] Format times in 24-hour format: "19:00"
- [ ] Set timezone to Europe/Paris
- [ ] Test date formatting across all templates

**Acceptance Criteria:**
- [ ] Dates display in French format
- [ ] Day names in French (lowercase)
- [ ] Month names in French (lowercase)
- [ ] 24-hour time format
- [ ] Consistent across all pages

---

## Epic 7: Deployment & Publishing

### Issue #34: Configure GitHub Repository for Publishing
**Labels:** `deployment`, `github`, `priority:medium`

**Description:**
Set up GitHub repository for hosting the built Hugo site.

**Tasks:**
- [ ] Create GitHub repository (if not exists)
- [ ] Configure repository settings for GitHub Pages or external hosting
- [ ] Set up branch strategy:
  - `main` - source code
  - `gh-pages` - built site (if using GitHub Pages)
- [ ] Add GitHub Actions workflow for automatic builds (optional)
- [ ] Configure custom domain (if applicable)
- [ ] Add repository description and topics

**Acceptance Criteria:**
- [ ] Repository accessible on GitHub
- [ ] Built site can be deployed
- [ ] Deployment process documented
- [ ] Site accessible at production URL

---

### Issue #35: Create Build and Deploy Scripts
**Labels:** `deployment`, `scripts`, `priority:medium`

**Description:**
Create scripts to build Hugo site and prepare for GitHub publishing.

**Tasks:**
- [ ] Create /scripts/build.sh:
  ```bash
  #!/bin/bash
  cd hugo
  hugo --minify
  ```
- [ ] Create /scripts/deploy.sh (if manual):
  ```bash
  #!/bin/bash
  ./scripts/build.sh
  cd hugo/public
  git add .
  git commit -m "Deploy $(date +%Y-%m-%d)"
  git push
  ```
- [ ] Create pre-commit hook to run Hugo build test
- [ ] Document deployment process

**Acceptance Criteria:**
- [ ] Build script generates site in /hugo/public
- [ ] Deploy script pushes to GitHub
- [ ] Scripts are executable
- [ ] Process documented in README

---

### Issue #36: Create Maintenance Scripts
**Labels:** `deployment`, `scripts`, `priority:low`

**Description:**
Create utility scripts for ongoing maintenance tasks.

**Tasks:**
- [ ] Create /scripts/expire-events.sh:
  - Find events with past dates
  - Update expired: true in front matter
- [ ] Create /scripts/cleanup-images.sh:
  - Remove orphaned images
  - Optimize image sizes
- [ ] Create /scripts/validate-content.sh:
  - Check all events have required fields
  - Validate front matter format
- [ ] Document each script's purpose and usage

**Acceptance Criteria:**
- [ ] Expire script marks past events correctly
- [ ] Cleanup script removes unused images
- [ ] Validation script catches errors
- [ ] Scripts documented in README

---

## Dependencies

| Issue | Depends On |
|-------|-----------|
| #3 Blowfish Theme | #2 Hugo |
| #4 Taxonomies | #2 Hugo |
| #5-#10 Data Model | #3 Theme, #4 Taxonomies |
| #11-#18 UI | #5 Content Type, #7-#8 Taxonomies |
| #19-#28 Crawler | #5 Content Type, #6 Folder Structure |
| #32-#33 Localization | #11-#18 UI |
| #34-#36 Deployment | #19-#28 Crawler, #11-#18 UI |

---

## Suggested Implementation Order

### Phase 1: Foundation (Week 1)
```
#1 → #2 → #3 → #4 → #5 → #6 → #7 → #8
```

### Phase 2: User Interface (Week 2)
```
#11 → #12 → #13 → #14 → #15 → #32 → #33
```

### Phase 3: Crawler Core (Week 3)
```
#19 → #20 → #21 → #22 → #23 → #29
```

### Phase 4: Crawler Intelligence (Week 4)
```
#24 → #25 → #26 → #27 → #28 → #30
```

### Phase 5: Polish & Deploy (Week 5)
```
#9 → #10 → #16 → #17 → #18 → #31 → #34 → #35 → #36
```

---

## Labels Reference

| Label | Description |
|-------|-------------|
| `setup` | Initial project setup |
| `hugo` | Hugo CMS related |
| `theme` | Blowfish theme related |
| `taxonomy` | Taxonomy configuration |
| `data-model` | Content structure and schema |
| `ui` | User interface |
| `component` | UI component |
| `template` | Hugo template |
| `responsive` | Responsive design |
| `performance` | Performance optimization |
| `feature` | New feature |
| `crawler` | Crawler system |
| `config` | Configuration |
| `core` | Core functionality |
| `extraction` | Data extraction |
| `images` | Image handling |
| `selection` | Event selection |
| `classification` | Category classification |
| `deduplication` | Duplicate detection |
| `output` | Content generation |
| `admin` | Administrative features |
| `logging` | Logging system |
| `cli` | Command line interface |
| `localization` | French language |
| `formatting` | Date/time formatting |
| `deployment` | Build and deploy |
| `scripts` | Utility scripts |
| `documentation` | Documentation |
| `priority:high` | Must have |
| `priority:medium` | Should have |
| `priority:low` | Nice to have |
