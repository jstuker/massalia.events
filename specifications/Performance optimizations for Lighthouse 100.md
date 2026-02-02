# Performance Optimizations for Lighthouse Score of 100

**Issue:** #14 - Optimize site for Google Lighthouse performance score of 100
**Date:** 2026-02-02

## Summary

This document describes the performance optimizations applied to massalia.events to achieve a Google Lighthouse performance score of 100.

## Optimizations Applied

### 1. Image Dimension Attributes (CLS Prevention)

**Files modified:** `layouts/events/single.html`, `layouts/partials/event-card.html`

All `<img>` tags now include explicit `width` and `height` attributes derived from Hugo's image processing pipeline. This prevents Cumulative Layout Shift (CLS) by allowing browsers to reserve space before images load.

- Hero images: dimensions from `Resize "1200x"` operation
- Card images: dimensions from thumbnail or `Resize "400x"` fallback

### 2. Image Loading Prioritization

**Files modified:** `layouts/events/single.html`, `layouts/partials/event-card.html`

- Hero images (above the fold): `fetchpriority="high"` and `decoding="async"`
- Card images (below the fold): `loading="lazy"` and `decoding="async"` (pre-existing)

### 3. Responsive Images with srcset

**Files modified:** `layouts/events/single.html`, `layouts/partials/event-card.html`

Generated multiple image sizes using Hugo's image processing:

- **Hero images:** 600w, 900w, 1200w with viewport-aware `sizes` attribute
  - `sizes="(max-width: 640px) 100vw, (max-width: 1024px) 90vw, 900px"`
- **Card images:** 200w, 400w when fallback resize is used
  - `sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 400px"`
- Thumbnail images skip srcset (already pre-optimized at target size)

This allows browsers to select the optimal image resolution based on viewport width and device pixel ratio.

### 4. External JavaScript with Defer Loading

**Files created:** `assets/js/day-selector.js`, `assets/js/event-filter.js`
**Files modified:** `layouts/partials/day-selector.html`, `layouts/partials/home/custom.html`

Extracted two large inline `<script>` blocks (~280 lines total) into external JavaScript files processed through Hugo's asset pipeline:

- Files are minified and fingerprinted with SHA-512
- Loaded with `defer` attribute to prevent render blocking
- Include `integrity` attributes for security (Subresource Integrity)
- Browsers can cache JS separately from HTML

### 5. Preconnect Hints

**Files created:** `layouts/partials/extend-head.html`

Added resource hints to the document head:

- `<link rel="preconnect">` to Google Tag Manager (analytics)
- `<link rel="dns-prefetch">` as fallback for older browsers
- `<meta name="color-scheme" content="light dark">` to help browsers render with correct color scheme before CSS loads

### 6. Hugo Imaging Configuration

**Files modified:** `config/_default/hugo.toml`

Enhanced Hugo's image processing settings:

- **Quality:** Set to 80 for optimal quality/size balance
- **Resampling:** Lanczos filter for sharper resized images
- **EXIF stripping:** Disabled date and GPS metadata to reduce file size
- **HTML minification:** Aggressive whitespace removal
- **CSS minification:** Modern CSS output (dropped CSS2 compatibility)

## Pre-existing Optimizations (Already in Place)

These optimizations were already configured before this work:

- WebP format for all event images
- Dual image strategy (full + thumbnails)
- CSS bundled, minified, and fingerprinted with SHA-512 integrity
- JS deferred and bundled (Blowfish theme)
- Lazy loading on card images
- Async decoding on card images
- JSON-LD structured data for SEO
- Hugo `--gc --minify` production build flags
- `fingerprintAlgorithm = "sha512"` for cache busting

## Impact

| Metric | Before | After |
|--------|--------|-------|
| Processed images | 177 | 531 (multiple sizes) |
| Inline JS on homepage | ~280 lines | ~4 lines (GA config) |
| External JS files | 5 | 7 (+day-selector, event-filter) |
| Image width/height | Not set | Set on all images |
| Responsive images | None | srcset on hero + fallback cards |
| Preconnect hints | None | Google Tag Manager |

## Files Changed

| File | Change |
|------|--------|
| `layouts/events/single.html` | Image dimensions, fetchpriority, srcset |
| `layouts/partials/event-card.html` | Image dimensions, srcset |
| `layouts/partials/day-selector.html` | External JS reference |
| `layouts/partials/home/custom.html` | External JS reference |
| `layouts/partials/extend-head.html` | New: preconnect hints |
| `assets/js/day-selector.js` | New: extracted from inline |
| `assets/js/event-filter.js` | New: extracted from inline |
| `config/_default/hugo.toml` | Imaging and minification config |
