# Troubleshooting Guide

This guide covers common issues and their solutions when working with the massalia.events crawler and publishing workflow.

## Table of Contents

- [Crawler Issues](#crawler-issues)
- [Configuration Issues](#configuration-issues)
- [Git and Deployment Issues](#git-and-deployment-issues)
- [Website Issues](#website-issues)
- [Getting Help](#getting-help)

---

## Crawler Issues

### "No events found" from a source

**Symptoms:**
```
[1/3] Processing: La Friche la Belle de Mai (lafriche)
    -> 0 accepted, 0 rejected
```

**Possible Causes:**
1. Source website structure changed
2. Source website is down
3. Rate limiting or blocking
4. CSS selectors are incorrect

**Solutions:**

1. **Check if website is accessible:**
   ```bash
   curl -I "https://www.lafriche.org/agenda"
   ```

2. **Run with debug logging:**
   ```bash
   python crawl.py run --source lafriche --log-level DEBUG
   ```

3. **Verify selectors in config:**
   ```bash
   # Check sources.yaml for correct selectors
   cat config/sources.yaml | grep -A 20 "id: lafriche"
   ```

4. **Test selectors manually:**
   - Open the source website in a browser
   - Use browser DevTools (F12)
   - Test CSS selectors in Console:
     ```javascript
     document.querySelectorAll('.event-card')
     ```

### "Failed to download image"

**Symptoms:**
```
ERROR [src.utils.images] Failed to download image: https://example.com/image.jpg
```

**Possible Causes:**
1. Image URL is invalid or broken
2. Network connectivity issues
3. Source site blocks image downloads
4. SSL certificate issues

**Solutions:**

1. **Check image URL directly:**
   ```bash
   curl -I "https://example.com/image.jpg"
   ```

2. **Verify network:**
   ```bash
   ping example.com
   ```

3. **Check for rate limiting:**
   - Increase `delay_between_pages` in `config/sources.yaml`
   - Reduce `requests_per_second`

4. **Skip problematic images:**
   - Events will still be created without images
   - Check logs for which images failed

### "Configuration error"

**Symptoms:**
```
Configuration error: Configuration validation failed at 'sources -> 1': Missing required field: url
```

**Solutions:**

1. **Run validation:**
   ```bash
   python crawl.py validate
   ```

2. **Check YAML syntax:**
   ```bash
   python -c "import yaml; yaml.safe_load(open('config/sources.yaml'))"
   ```

3. **Verify required fields:**
   Each source must have:
   - `name`: Display name
   - `id`: Unique identifier
   - `url`: Source URL
   - `parser`: Parser name

### "Parser not available"

**Symptoms:**
```
WARNING [src.crawl] Parser not available for My Source: Unknown parser 'myparser'
```

**Solutions:**

1. **List available parsers:**
   ```bash
   python crawl.py validate
   # Look for "Unknown parser" warnings
   ```

2. **Check parser name in sources.yaml:**
   Valid parsers: `lafriche`, `generic`

3. **Create custom parser if needed:**
   See [Adding New Parsers](../crawler/README.md#adding-new-parsers)

### Crawler stops responding

**Symptoms:**
- No output for extended period
- Process appears hung

**Solutions:**

1. **Graceful interrupt:**
   Press `Ctrl+C` to stop gracefully
   ```
   Interrupt received, finishing current task...
   ```

2. **Force quit:**
   Press `Ctrl+C` again or close terminal

3. **Check logs:**
   ```bash
   tail -f logs/crawler.log
   ```

4. **Increase timeouts:**
   In `config.yaml`:
   ```yaml
   http:
     timeout: 60  # Increase from 30
   ```

### "Rate limit exceeded" or "429 Too Many Requests"

**Solutions:**

1. **Slow down requests:**
   In `config/sources.yaml`:
   ```yaml
   rate_limit:
     requests_per_second: 0.5  # Reduce from 1.0
     delay_between_pages: 5.0  # Increase from 2.0
   ```

2. **Wait and retry:**
   Wait 5-10 minutes before running again

3. **Run single source:**
   ```bash
   python crawl.py run --source lafriche
   ```

---

## Configuration Issues

### "Config file not found"

**Symptoms:**
```
Error: Config file not found: /path/to/config.yaml
```

**Solutions:**

1. **Run from crawler directory:**
   ```bash
   cd crawler
   python crawl.py run
   ```

2. **Specify config path:**
   ```bash
   python crawl.py -c /full/path/to/config.yaml run
   ```

3. **Create config if missing:**
   ```bash
   cp config.yaml.example config.yaml
   ```

### Selection criteria excluding too many events

**Symptoms:**
```
CRAWL SUMMARY
  Events accepted:    2
  Events rejected:    50
```

**Solutions:**

1. **Review selection criteria:**
   ```bash
   cat config/selection-criteria.yaml
   ```

2. **Temporarily disable filtering:**
   ```bash
   python crawl.py run --skip-selection
   ```

3. **Adjust criteria:**
   Edit `config/selection-criteria.yaml`:
   ```yaml
   dates:
     max_days_ahead: 60  # Increase from 30
   ```

### Log file not created

**Symptoms:**
- No `logs/crawler.log` file
- No file logging

**Solutions:**

1. **Create logs directory:**
   ```bash
   mkdir -p logs
   ```

2. **Check config.yaml:**
   ```yaml
   logging:
     log_file: "logs/crawler.log"
   ```

3. **Check permissions:**
   ```bash
   ls -la logs/
   ```

---

## Git and Deployment Issues

### "Permission denied" when pushing

**Symptoms:**
```
Permission denied (publickey).
fatal: Could not read from remote repository.
```

**Solutions:**

1. **Check SSH key:**
   ```bash
   ssh -T git@github.com
   ```

2. **Use HTTPS instead:**
   ```bash
   git remote set-url origin https://github.com/jstuker/massalia.events.git
   ```

3. **Re-authenticate:**
   ```bash
   gh auth login
   ```

### Merge conflicts

**Symptoms:**
```
CONFLICT (content): Merge conflict in content/events/...
```

**Solutions:**

1. **Pull before crawling:**
   ```bash
   git pull origin main
   ```

2. **Resolve conflicts:**
   ```bash
   git status  # See conflicted files
   # Edit files to resolve
   git add .
   git commit -m "Resolve merge conflicts"
   ```

3. **Prefer remote changes:**
   ```bash
   git checkout --theirs content/events/
   git add .
   git commit -m "Accept remote changes"
   ```

### GitHub Actions deployment failed

**Symptoms:**
- Red X on GitHub Actions
- Site not updated

**Solutions:**

1. **Check Actions logs:**
   - Go to https://github.com/jstuker/massalia.events/actions
   - Click on failed workflow
   - Expand failed step

2. **Common failures:**
   - **Build error:** Check for invalid front matter in new files
   - **Deploy error:** Check GitHub Pages settings
   - **Network error:** Re-run the workflow

3. **Re-run workflow:**
   - Click "Re-run all jobs" button on GitHub

### Large files rejected

**Symptoms:**
```
remote: error: File ... is 123.45 MB; this exceeds GitHub's file size limit
```

**Solutions:**

1. **Reduce image quality:**
   In `config.yaml`:
   ```yaml
   image_settings:
     quality: 70  # Reduce from 85
     max_width: 800  # Reduce from 1200
   ```

2. **Remove large files:**
   ```bash
   git reset HEAD~1  # Undo last commit
   rm static/images/events/large-file.webp
   git add -A && git commit -m "..."
   ```

---

## Website Issues

### Events not appearing on site

**Symptoms:**
- Crawl succeeded
- Push succeeded
- Events not visible on live site

**Solutions:**

1. **Wait for deployment:**
   - GitHub Pages can take 2-5 minutes
   - Check Actions tab for deployment status

2. **Check event dates:**
   - Events with past dates may be filtered
   - Check `expiryDate` in front matter

3. **Check draft status:**
   - Ensure `draft: false` in front matter

4. **Clear browser cache:**
   - Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)

5. **Check Hugo build locally:**
   ```bash
   hugo server -D
   ```

### Images not loading

**Symptoms:**
- Event appears but image is broken
- 404 error for images

**Solutions:**

1. **Verify image exists:**
   ```bash
   ls static/images/events/
   ```

2. **Check image path in markdown:**
   ```bash
   grep "image:" content/events/2026/01/27/*.md
   ```

3. **Ensure images were committed:**
   ```bash
   git status static/images/
   git add static/images/events/
   ```

### Wrong dates displayed

**Solutions:**

1. **Check timezone in front matter:**
   ```yaml
   date: 2026-01-27T19:00:00+01:00  # Ensure timezone is +01:00 for Paris
   ```

2. **Check Hugo timezone config:**
   ```toml
   # hugo.toml
   timeZone = "Europe/Paris"
   ```

---

## Getting Help

### Collect Information

Before asking for help, gather:

1. **Error message:**
   ```bash
   python crawl.py run 2>&1 | tee crawl-output.txt
   ```

2. **Log file:**
   ```bash
   cat logs/crawler.log
   ```

3. **Configuration:**
   ```bash
   python crawl.py validate
   ```

4. **Environment:**
   ```bash
   python --version
   pip freeze
   ```

### Where to Get Help

1. **Check existing documentation:**
   - [Crawler README](../crawler/README.md)
   - [Workflow Guide](WORKFLOW.md)

2. **Open an issue:**
   - https://github.com/jstuker/massalia.events/issues
   - Include error messages and steps to reproduce

3. **Review recent changes:**
   ```bash
   git log --oneline -10
   ```

---

## Prevention Tips

### Before Each Crawl

1. Always pull latest changes first
2. Run `--dry-run` before actual crawl
3. Check `validate` for configuration issues

### Weekly Maintenance

1. Clean expired events: `python crawl.py clean`
2. Update dependencies: `pip install --upgrade -r requirements.txt`
3. Check source websites for structure changes

### Monitoring

1. Review crawler logs regularly
2. Set up GitHub notifications for failed deployments
3. Periodically check live site for missing events
