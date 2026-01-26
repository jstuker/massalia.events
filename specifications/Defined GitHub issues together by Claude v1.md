# massalia.events - Implementation Roadmap

**Generated:** 26 January 2025
**Total Open Issues:** 33
**Note:** Issue #7 is missing (deleted or never created)

---

## Overview by Epic

### Epic 1: Data Model & Taxonomy (6 issues)

| # | Title | Status |
|---|-------|--------|
| 1 | Configure Hugo taxonomy system for categories, locations, and dates | Open |
| 2 | Create event content type with complete front matter schema | Open |
| 3 | Implement date-based folder structure for event storage | Open |
| 4 | Define event categories taxonomy with French labels | Open |
| 5 | Define Marseille venue locations as taxonomy terms | Open |
| 6 | Handle multi-day events with separate pages per day | Open |

### Epic 2: Event Lifecycle (1 issue)

| # | Title | Status |
|---|-------|--------|
| 32 | Implement event expiration system to hide past events from public display | Open |

### Epic 3: User Interface (7 issues)

| # | Title | Status |
|---|-------|--------|
| 8 | Create 7-day navigation selector with French day names | Open |
| 9 | Build event card component with category, location, name, date, and start time | Open |
| 10 | Build single event detail page with full information, image, and source link | Open |
| 11 | Implement event filtering logic for selected day from 7-day navigation | Open |
| 12 | Configure search to only find events within the 7-day window | Open |
| 13 | Ensure responsive UI across mobile, tablet, and desktop viewports | Open |
| 33 | Build landing page layout with today's events as default view | Open |

### Epic 4: Performance (1 issue)

| # | Title | Status |
|---|-------|--------|
| 14 | Optimize site for Google Lighthouse performance score of 100 | Open |

### Epic 5: Crawler System (10 issues)

| # | Title | Status |
|---|-------|--------|
| 15 | Create crawler application structure for local execution | Open |
| 16 | Create configuration file for event source websites to crawl | Open |
| 17 | Create selection criteria document for event inclusion decisions | Open |
| 18 | Build web page fetcher component for crawler | Open |
| 19 | Build HTML parser component with configurable selectors for event extraction | Open |
| 20 | Download and process event hero images to Blowfish-optimized format | Open |
| 21 | Build selection criteria evaluator to include or exclude events | Open |
| 22 | Automatically assign categories to events based on content analysis | Open |
| 23 | Detect duplicate events using booking link and date-time-location matching | Open |
| 24 | Generate Hugo markdown files from processed events in correct folder structure | Open |

### Epic 6: Administrative & Logging (3 issues)

| # | Title | Status |
|---|-------|--------|
| 25 | Create comprehensive logging system with configurable levels | Open |
| 26 | Build command-line interface for crawler management | Open |
| 27 | Document complete workflow for local crawling and GitHub publishing | Open |

### Epic 7: Localization (2 issues)

| # | Title | Status |
|---|-------|--------|
| 28 | Translate all user interface text to French | Open |
| 29 | Configure French date and time display throughout the application | Open |

### Epic 8: DevOps & Maintenance (2 issues)

| # | Title | Status |
|---|-------|--------|
| 30 | Create local build and development scripts for Hugo site | Open |
| 31 | Create utility scripts for ongoing maintenance tasks | Open |

---

## Proposed Implementation Order

### Phase 1: Foundation (Data Model)

**Goal:** Establish the data structure for events before building UI or crawler.

| Order | Issue | Title | Dependencies |
|-------|-------|-------|--------------|
| 1.1 | #1 | Configure Hugo taxonomy system | None |
| 1.2 | #2 | Create event content type with front matter schema | #1 |
| 1.3 | #3 | Implement date-based folder structure | #2 |
| 1.4 | #4 | Define event categories taxonomy | #1 |
| 1.5 | #5 | Define Marseille venue locations | #1 |
| 1.6 | #6 | Handle multi-day events | #2, #3 |
| 1.7 | #32 | Implement event expiration system | #2 |

**Deliverable:** Complete event data model with sample test events.

---

### Phase 2: Core UI Components

**Goal:** Build the visual components users will interact with.

| Order | Issue | Title | Dependencies |
|-------|-------|-------|--------------|
| 2.1 | #8 | Create 7-day navigation selector | None |
| 2.2 | #9 | Build event card component | #2 (schema) |
| 2.3 | #10 | Build single event detail page | #2, #9 |
| 2.4 | #28 | Translate all UI text to French | None |
| 2.5 | #29 | Configure French date/time display | None |

**Deliverable:** Reusable UI components with French localization.

---

### Phase 3: Landing Page & Interactivity

**Goal:** Assemble components into the functional landing page.

| Order | Issue | Title | Dependencies |
|-------|-------|-------|--------------|
| 3.1 | #33 | Build landing page layout | #8, #9 |
| 3.2 | #11 | Implement event filtering logic | #8, #9, #33 |
| 3.3 | #12 | Configure search within 7-day window | #32 |
| 3.4 | #13 | Ensure responsive UI | #33 |

**Deliverable:** Fully functional event calendar UI.

---

### Phase 4: Performance & Polish

**Goal:** Optimize for production deployment.

| Order | Issue | Title | Dependencies |
|-------|-------|-------|--------------|
| 4.1 | #14 | Optimize for Lighthouse score 100 | #33, #13 |
| 4.2 | #30 | Create local build/dev scripts | None |

**Deliverable:** Production-ready, performant website.

---

### Phase 5: Crawler Core

**Goal:** Build the event ingestion system.

| Order | Issue | Title | Dependencies |
|-------|-------|-------|--------------|
| 5.1 | #15 | Create crawler application structure | None |
| 5.2 | #16 | Create source websites configuration | #15 |
| 5.3 | #17 | Create selection criteria document | #15 |
| 5.4 | #18 | Build web page fetcher | #15 |
| 5.5 | #19 | Build HTML parser with selectors | #18 |
| 5.6 | #25 | Create logging system | #15 |

**Deliverable:** Crawler that can fetch and parse web pages.

---

### Phase 6: Crawler Intelligence

**Goal:** Add smart processing to the crawler.

| Order | Issue | Title | Dependencies |
|-------|-------|-------|--------------|
| 6.1 | #21 | Build selection criteria evaluator | #17, #19 |
| 6.2 | #22 | Automatically assign categories | #4, #19 |
| 6.3 | #23 | Detect duplicate events | #19 |
| 6.4 | #20 | Download and process hero images | #19 |
| 6.5 | #24 | Generate Hugo markdown files | #2, #3, #19 |

**Deliverable:** Crawler that intelligently processes and classifies events.

---

### Phase 7: CLI & Documentation

**Goal:** Make the system usable by administrators.

| Order | Issue | Title | Dependencies |
|-------|-------|-------|--------------|
| 7.1 | #26 | Build CLI for crawler management | #15, #24 |
| 7.2 | #27 | Document crawl and publish workflow | #26 |
| 7.3 | #31 | Create maintenance utility scripts | #32 |

**Deliverable:** Complete, documented system ready for daily operation.

---

## Dependency Graph

```
Phase 1: Foundation
#1 ─┬─► #2 ─► #3 ─┬─► #6
    │             │
    ├─► #4        └─► #32
    │
    └─► #5

Phase 2-3: UI
#8 ─────┬─► #33 ─► #11
        │
#9 ─────┤
        │
#10 ◄───┘

#28, #29 (parallel - localization)

Phase 4: Polish
#33 + #13 ─► #14

Phase 5-6: Crawler
#15 ─┬─► #16
     ├─► #17 ─► #21
     ├─► #18 ─► #19 ─┬─► #20
     │               ├─► #22
     └─► #25         ├─► #23
                     └─► #24

Phase 7: Finalization
#24 ─► #26 ─► #27
#32 ─► #31
```

---

## Quick Reference: All Open Issues

| # | Title |
|---|-------|
| 1 | Configure Hugo taxonomy system for categories, locations, and dates |
| 2 | Create event content type with complete front matter schema |
| 3 | Implement date-based folder structure for event storage |
| 4 | Define event categories taxonomy with French labels |
| 5 | Define Marseille venue locations as taxonomy terms |
| 6 | Handle multi-day events with separate pages per day |
| 8 | Create 7-day navigation selector with French day names |
| 9 | Build event card component with category, location, name, date, and start time |
| 10 | Build single event detail page with full information, image, and source link |
| 11 | Implement event filtering logic for selected day from 7-day navigation |
| 12 | Configure search to only find events within the 7-day window |
| 13 | Ensure responsive UI across mobile, tablet, and desktop viewports |
| 14 | Optimize site for Google Lighthouse performance score of 100 |
| 15 | Create crawler application structure for local execution |
| 16 | Create configuration file for event source websites to crawl |
| 17 | Create selection criteria document for event inclusion decisions |
| 18 | Build web page fetcher component for crawler |
| 19 | Build HTML parser component with configurable selectors for event extraction |
| 20 | Download and process event hero images to Blowfish-optimized format |
| 21 | Build selection criteria evaluator to include or exclude events |
| 22 | Automatically assign categories to events based on content analysis |
| 23 | Detect duplicate events using booking link and date-time-location matching |
| 24 | Generate Hugo markdown files from processed events in correct folder structure |
| 25 | Create comprehensive logging system with configurable levels |
| 26 | Build command-line interface for crawler management |
| 27 | Document complete workflow for local crawling and GitHub publishing |
| 28 | Translate all user interface text to French |
| 29 | Configure French date and time display throughout the application |
| 30 | Create local build and development scripts for Hugo site |
| 31 | Create utility scripts for ongoing maintenance tasks |
| 32 | Implement event expiration system to hide past events from public display |
| 33 | Build landing page layout with today's events as default view |

---

## Notes

- **Issue #7 is missing** - May need to be recreated if it contained important requirements
- **Phases can overlap** - UI work (Phase 2-3) can start while finishing Phase 1
- **Crawler is independent** - Phases 5-7 can be developed in parallel with UI polish
- **Test data needed** - Create sample events after Phase 1 to test UI components
