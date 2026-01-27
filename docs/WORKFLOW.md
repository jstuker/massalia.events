# Content Publishing Workflow

This document describes the complete workflow for updating massalia.events with new event content.

## Overview

The publishing workflow consists of six steps:

1. **Prepare** - Ensure local environment is ready
2. **Crawl** - Run crawler to fetch new events
3. **Review** - Check crawler output and logs
4. **Commit** - Stage and commit new content
5. **Push** - Push to GitHub to trigger deployment
6. **Verify** - Check live site for new content

## Prerequisites

Before starting, ensure you have:

- Git installed and configured
- Python 3.11+ installed
- Access to the massalia.events repository
- The crawler virtual environment set up (see [Crawler README](../crawler/README.md))

## Step 1: Prepare Environment

```bash
# Navigate to project directory
cd /path/to/massalia.events

# Get latest changes from main
git checkout main
git pull origin main

# Activate crawler virtual environment
cd crawler
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### First-Time Setup

If this is your first time, complete the initial setup:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Validate configuration
python crawl.py validate
```

## Step 2: Run Crawler

### Preview Mode (Recommended First)

```bash
# Preview what would be created without writing files
python crawl.py run --dry-run
```

Expected output:
```
DRY RUN MODE - No files will be written

[1/3] Processing: La Friche la Belle de Mai (lafriche)
    -> 8 accepted, 2 rejected
[2/3] Processing: KLAP Maison pour la danse (klap)
    -> 5 accepted, 1 rejected
[3/3] Processing: Shotgun (shotgun)
    -> 12 accepted, 3 rejected

==================================================
CRAWL SUMMARY
==================================================
  Sources processed:  3/3
  Events accepted:    25
  Events rejected:    6
  Errors:             0
==================================================

DRY RUN - No files were written
```

### Execute Crawl

Once preview looks good, run the actual crawl:

```bash
# Run full crawl
python crawl.py run
```

### Single Source Crawl

To crawl only one source:

```bash
# Crawl specific source
python crawl.py run --source lafriche
```

### View Last Crawl Status

```bash
python crawl.py status
```

## Step 3: Review Results

### Check Git Status

```bash
# Return to project root
cd ..

# See what files were created/modified
git status
```

Expected output:
```
On branch main
Untracked files:
  (use "git add <file>..." to include in what will be committed)
        content/events/2026/01/27/
        content/events/2026/01/28/
        static/images/events/

no changes added to commit (use "git add" and/or "git commit -a")
```

### Review File Count

```bash
# Count new event files
git status --short | grep -c "^??"

# View specific changes
git diff --stat
```

### Preview Locally (Optional)

```bash
# Start Hugo development server
hugo server -D

# Visit http://localhost:1313
```

### Check Crawler Logs

If there were errors:

```bash
# View log file
cat crawler/logs/crawler.log

# Search for errors
grep ERROR crawler/logs/crawler.log
```

## Step 4: Commit Changes

### Stage Files

```bash
# Stage new event files
git add content/events/

# Stage new images
git add static/images/events/

# Or stage all changes at once
git add -A
```

### Create Commit

```bash
# Commit with descriptive message
git commit -m "Add events from 2026-01-27 crawl

- 25 new events from 3 sources
- La Friche: 8 events
- KLAP: 5 events
- Shotgun: 12 events"
```

### Commit Message Guidelines

Good commit messages include:
- Date of the crawl
- Number of events added
- Sources processed
- Any notable issues or exclusions

Examples:
```
Add events from 2026-01-27 crawl

- 18 new events from La Friche
- 12 events from KLAP
- Skipped 3 private events
```

## Step 5: Push to GitHub

```bash
# Push to main branch
git push origin main
```

This triggers the GitHub Actions deployment workflow automatically.

## Step 6: Verify Deployment

### Check GitHub Actions

1. Go to https://github.com/jstuker/massalia.events/actions
2. Find the latest workflow run
3. Verify it completes successfully (green checkmark)

### Check Live Site

1. Wait 2-3 minutes for deployment
2. Visit https://massalia.events
3. Navigate to the events page
4. Verify new events appear correctly

### Troubleshoot Failed Deployment

If deployment fails:
1. Check GitHub Actions logs for errors
2. Fix any build errors locally
3. Push a fix commit

See [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues.

---

## Daily Operations Checklist

Use this checklist for routine content updates:

- [ ] `cd massalia.events && git pull origin main`
- [ ] `cd crawler && source venv/bin/activate`
- [ ] `python crawl.py run --dry-run` (preview)
- [ ] `python crawl.py run` (execute)
- [ ] `python crawl.py status` (verify success)
- [ ] `cd .. && git status` (review changes)
- [ ] `git add -A && git commit -m "Add events from [date] crawl"`
- [ ] `git push origin main`
- [ ] Check GitHub Actions for successful deployment
- [ ] Verify new events on live site

---

## Quick Reference

### Essential Commands

```bash
# Daily crawl workflow
cd /path/to/massalia.events
git pull origin main
cd crawler && source venv/bin/activate
python crawl.py run --dry-run    # Preview
python crawl.py run              # Execute
cd .. && hugo server             # Preview locally
git add -A
git commit -m "Add events from $(date +%Y-%m-%d) crawl"
git push origin main             # Deploy
```

### Useful Commands

```bash
# List configured sources
python crawl.py list-sources

# Validate configuration
python crawl.py validate

# Show last crawl status
python crawl.py status

# Clean expired events
python crawl.py clean

# Verbose debugging
python crawl.py run --log-level DEBUG

# View log file
cat logs/crawler.log | tail -50
```

### Keyboard Shortcuts

- `Ctrl+C` - Stop crawler gracefully (partial results are saved)

---

## Weekly Maintenance

### Clean Expired Events

Remove events that have already passed:

```bash
cd crawler
source venv/bin/activate

# Preview what would be cleaned
python crawl.py clean --dry-run

# Mark expired events
python crawl.py clean

# Or delete old files entirely
python crawl.py clean --delete --before 2026-01-01
```

### Update Dependencies

```bash
cd crawler
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Check for Source Website Changes

If a source stops returning events:

1. Visit the source website manually
2. Check if the page structure changed
3. Update CSS selectors in `config/sources.yaml`
4. Run `python crawl.py validate` to check configuration

---

## Related Documentation

- [Crawler README](../crawler/README.md) - Detailed crawler documentation
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues and solutions
- [Product Specification](../specifications/Product%20specification%20v1.md) - Project requirements
