"""Parser for Journal Zébuline (journalzebuline.fr) events.

Journal Zébuline is a French cultural journalism magazine based in
Marseille/Provence. It publishes articles about cultural events — previews,
reviews, interviews — organized by artistic discipline. The site runs on
WordPress and exposes a full REST API.

Unlike other sources that have structured event listings, Zébuline embeds
practical event details (date, venue) inside article body content using
``<pre class="wp-block-verse">`` blocks with highlighted dates.

Strategy:
1. Fetch recent articles from the WordPress REST API filtered by relevant
   categories (Scènes, Musiques, Arts visuels, Cinéma, Cirque).
2. Parse the article HTML content to extract event details from
   ``wp-block-verse`` blocks.
3. Extract date from ``<mark>`` elements with orange highlight.
4. Extract venue from ``<a>`` links inside the verse block.
5. Use article metadata (tags, categories, featured image) for enrichment.
6. Filter for Marseille-area events.
"""

import json
import re
import time
from datetime import datetime

from ..crawler import BaseCrawler
from ..logger import get_logger
from ..models.event import Event
from ..utils.french_date import FRENCH_MONTHS, PARIS_TZ
from ..utils.parser import HTMLParser

logger = get_logger(__name__)

# WordPress REST API pagination - 100 is the WP maximum per page
WP_PER_PAGE = 100

# WordPress category IDs for event-related content
# Scènes (2876), Musiques (2877), Arts visuels (2884), Cinéma (2878), Cirque (5659)
WP_CATEGORY_IDS = [2876, 2877, 2884, 2878, 5659]

# WordPress REST API base URL
WP_API_BASE = "https://journalzebuline.fr/wp-json/wp/v2"

# WordPress category ID to our taxonomy mapping
WP_CATEGORY_MAP = {
    2876: "theatre",  # Scènes
    2877: "musique",  # Musiques
    2884: "art",  # Arts visuels
    2878: "art",  # Cinéma
    5659: "theatre",  # Cirque
    2881: "theatre",  # Critiques (parent)
    2883: "theatre",  # On y était
}

# Cities in the Marseille area (for geographic filtering)
MARSEILLE_AREA_CITIES = {
    "marseille",
    "aix-en-provence",
    "aix en provence",
    "aubagne",
    "cassis",
    "la ciotat",
    "martigues",
    "vitrolles",
    "istres",
    "salon-de-provence",
    "salon de provence",
}

# Keywords that indicate a Marseille-area venue
MARSEILLE_VENUE_KEYWORDS = {
    "la friche",
    "friche belle de mai",
    "mucem",
    "la criée",
    "la criee",
    "le zef",
    "théâtre de l'oeuvre",
    "theatre de l'oeuvre",
    "le merlan",
    "klap",
    "ballet national de marseille",
    "opéra de marseille",
    "opera de marseille",
    "le silo",
    "espace julien",
    "le moulin",
    "la canebière",
    "vieux-port",
    "vieux port",
    "le dôme",
    "le dome",
    "mac marseille",
    "musée cantini",
    "musee cantini",
    "bmvr",
    "alcazar",
    "la joliette",
    "frac",
    "théâtre joliette",
    "theatre joliette",
    "théâtre du lacydon",
    "theatre du lacydon",
    "le cepac silo",
    "cabaret aléatoire",
    "cabaret aleatoire",
    "l'alhambra",
    "théâtre nono",
    "theatre nono",
    "théâtre toursky",
    "theatre toursky",
    "théâtre de la minoterie",
    "theatre de la minoterie",
    "la minoterie",
    "3 bisf",
    "les bancs publics",
    "montévidéo",
    "montevideo",
    "gyptis",
    "théâtre gyptis",
    "theatre gyptis",
    "théâtre off",
    "theatre off",
    "le grand théâtre de provence",
    "le grand theatre de provence",
    "pavillon noir",
    "théâtre des bernardines",
    "theatre des bernardines",
    "bernardines",
}


def _parse_french_date(text, reference_year=None):
    """
    Parse a French date string from a wp-block-verse mark element.

    Handles formats:
    - "30 janvier" (single date, year implied)
    - "30 janvier 2026" (single date with year)
    - "Du 3 au 5 février" (date range, returns start date)
    - "23 et 24 janvier" (multiple days, returns first)
    - "Jusqu'au 31 janvier" (until date)

    Args:
        text: French date string
        reference_year: Year to use if not specified in the text

    Returns:
        datetime or None if parsing failed
    """
    dates = _parse_all_french_dates(text, reference_year)
    return dates[0] if dates else None


def _parse_all_french_dates(text, reference_year=None):
    """
    Parse a French date string and return ALL dates.

    Handles formats:
    - "30 janvier" (single date) -> [Jan 30]
    - "Du 3 au 5 février" (date range) -> [Feb 3, Feb 4, Feb 5]
    - "2, 3 et 5 février" (list of days) -> [Feb 2, Feb 3, Feb 5]
    - "23 et 24 janvier" (two days) -> [Jan 23, Jan 24]
    - "Jusqu'au 31 janvier" (until date) -> [Jan 31]

    Args:
        text: French date string
        reference_year: Year to use if not specified in the text

    Returns:
        List of datetime objects (empty if parsing failed)
    """
    if not text:
        return []

    if reference_year is None:
        reference_year = datetime.now().year

    text_clean = text.strip().lower()

    # Remove "a venir" prefix
    text_clean = re.sub(r"^[àa]\s+venir\s*", "", text_clean).strip()

    # Pattern: "Du DD au DD mois [YYYY]" - expand to all dates in range
    range_match = re.search(
        r"du\s+(\d{1,2})\s+(?:\w+\s+)?au\s+(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?",
        text_clean,
    )
    if range_match:
        start_day = int(range_match.group(1))
        end_day = int(range_match.group(2))
        month_name = range_match.group(3)
        year = int(range_match.group(4)) if range_match.group(4) else reference_year
        month = FRENCH_MONTHS.get(month_name)
        if month:
            dates = []
            for day in range(start_day, end_day + 1):
                try:
                    dates.append(datetime(year, month, day, 20, 0, tzinfo=PARIS_TZ))
                except ValueError:
                    pass
            if dates:
                return dates

    # Pattern: "DD, DD et DD mois [YYYY]" (list with commas and 'et')
    list_match = re.search(
        r"((?:\d{1,2}\s*,\s*)*\d{1,2})\s+et\s+(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?",
        text_clean,
    )
    if list_match:
        days_before_et = list_match.group(1)
        last_day = int(list_match.group(2))
        month_name = list_match.group(3)
        year = int(list_match.group(4)) if list_match.group(4) else reference_year
        month = FRENCH_MONTHS.get(month_name)
        if month:
            dates = []
            # Parse all days before 'et'
            for day_str in re.findall(r"\d{1,2}", days_before_et):
                try:
                    dates.append(
                        datetime(year, month, int(day_str), 20, 0, tzinfo=PARIS_TZ)
                    )
                except ValueError:
                    pass
            # Add the day after 'et'
            try:
                dates.append(datetime(year, month, last_day, 20, 0, tzinfo=PARIS_TZ))
            except ValueError:
                pass
            if dates:
                return dates

    # Pattern: "Jusqu'au DD mois [YYYY]"
    jusquau_match = re.search(
        r"jusqu[''']?\s*au\s+(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?",
        text_clean,
    )
    if jusquau_match:
        day = int(jusquau_match.group(1))
        month_name = jusquau_match.group(2)
        year = int(jusquau_match.group(3)) if jusquau_match.group(3) else reference_year
        month = FRENCH_MONTHS.get(month_name)
        if month:
            try:
                return [datetime(year, month, day, 20, 0, tzinfo=PARIS_TZ)]
            except ValueError:
                pass

    # Pattern: "DD mois [YYYY]" (single date)
    single_match = re.search(
        r"(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?",
        text_clean,
    )
    if single_match:
        day = int(single_match.group(1))
        month_name = single_match.group(2)
        year = int(single_match.group(3)) if single_match.group(3) else reference_year
        month = FRENCH_MONTHS.get(month_name)
        if month:
            try:
                return [datetime(year, month, day, 20, 0, tzinfo=PARIS_TZ)]
            except ValueError:
                pass

    return []


def _extract_verse_blocks(html_content, venue_manager=None):
    """
    Extract event info from wp-block-verse blocks in article HTML.

    Each verse block may contain:
    - Date in <mark> with orange highlight class
    - Venue name and URL in <a> tags
    - City name after the venue link
    - "A venir" label for upcoming events

    Args:
        html_content: Article body HTML (content.rendered from WP API)
        venue_manager: Optional VenueManager for fallback venue matching

    Returns:
        List of dicts with keys: date_text, venue_name, venue_url, city,
        is_upcoming, full_text
    """
    parser = HTMLParser(html_content, "https://journalzebuline.fr")
    blocks = []

    verse_elements = parser.select("pre.wp-block-verse")

    for verse in verse_elements:
        block_info = {
            "date_text": "",
            "venue_name": "",
            "venue_url": "",
            "city": "",
            "is_upcoming": False,
            "full_text": verse.get_text(separator=" ").strip(),
        }

        # Check if this is a book/publication block (not an event)
        full_text = block_info["full_text"]
        if _is_book_block(full_text):
            continue

        # Extract date from <mark> elements with orange highlight
        marks = verse.select("mark.has-inline-color.has-luminous-vivid-orange-color")
        if not marks:
            # Fallback: any <mark> element
            marks = verse.select("mark")

        for mark in marks:
            mark_text = mark.get_text(separator=" ").strip()
            # Check for "A venir" label
            if re.match(r"[àa]\s+venir", mark_text, re.IGNORECASE):
                block_info["is_upcoming"] = True
                continue
            # Check if this looks like a date
            if _looks_like_date(mark_text):
                block_info["date_text"] = mark_text

        # Extract venue from <a> links inside verse block
        links = verse.select("a")
        for link in links:
            href = link.get("href", "")
            link_text = link.get_text().strip()
            # Skip links that are just category references
            if "journalzebuline.fr/category/" in href:
                continue
            if link_text and href:
                block_info["venue_name"] = link_text
                block_info["venue_url"] = href
                break

        # Fallback: extract venue from <strong> tags if no link found
        if not block_info["venue_name"]:
            strong_elements = verse.select("strong")
            for strong in strong_elements:
                strong_text = strong.get_text().strip()
                # Skip if it's a date or "A venir" label
                if _looks_like_date(strong_text):
                    continue
                if re.match(r"[àa]\s+venir", strong_text, re.IGNORECASE):
                    continue
                # Skip very short text or text with too many words (likely not a venue)
                if len(strong_text) < 3 or len(strong_text.split()) > 6:
                    continue
                # Check if this looks like a known Marseille venue
                strong_lower = strong_text.lower()
                for keyword in MARSEILLE_VENUE_KEYWORDS:
                    if keyword in strong_lower:
                        block_info["venue_name"] = strong_text
                        break
                if block_info["venue_name"]:
                    break

        # Fallback: try VenueManager matching if no venue found from keywords
        if not block_info["venue_name"] and venue_manager:
            strong_elements = verse.select("strong")
            for strong in strong_elements:
                strong_text = strong.get_text().strip()
                # Skip dates and "A venir" labels
                if _looks_like_date(strong_text):
                    continue
                if re.match(r"[àa]\s+venir", strong_text, re.IGNORECASE):
                    continue
                # Skip very short text or text with too many words
                if len(strong_text) < 3 or len(strong_text.split()) > 6:
                    continue
                # Try VenueManager - if the result differs from the input,
                # a known venue was matched
                mapped = venue_manager.map_location(strong_text)
                if mapped != strong_text:
                    block_info["venue_name"] = strong_text
                    break

        # Extract city from text after the venue link
        verse_text = verse.get_text(separator="|").strip()
        city = _extract_city(verse_text)
        if city:
            block_info["city"] = city

        # Only include blocks that have at least a date
        if block_info["date_text"]:
            blocks.append(block_info)

    return blocks


def _is_book_block(text):
    """Check if a verse block is about a book rather than an event."""
    book_indicators = [
        "traduit du",
        "traduit de",
        "éditions",
        "editions",
        "éditeur",
        "editeur",
        "isbn",
        "pages",
        "eur",
        "€",
    ]
    text_lower = text.lower()
    return any(indicator in text_lower for indicator in book_indicators)


def _looks_like_date(text):
    """Check if text looks like a French date."""
    text_lower = text.strip().lower()
    # Check for month names
    for month in FRENCH_MONTHS:
        if month in text_lower:
            return True
    # Check for "Du X au Y" pattern
    if re.match(r"du\s+\d", text_lower):
        return True
    # Check for "Jusqu'au" pattern
    if text_lower.startswith("jusqu"):
        return True
    return False


def _extract_city(text):
    """
    Extract city name from verse block text.

    The city typically appears after the venue name, separated by a comma.
    E.g., "Théâtre de l'Oeuvre|, Marseille"
    """
    for city in MARSEILLE_AREA_CITIES:
        if city in text.lower():
            return city.title()
    return ""


def _is_marseille_area_event(verse_block):
    """
    Check if an event is in the Marseille area.

    Uses city name and venue keyword matching.
    """
    # Check city
    city = verse_block.get("city", "").lower()
    if city and any(c in city for c in MARSEILLE_AREA_CITIES):
        return True

    # Check venue name against known Marseille venues
    venue_name = verse_block.get("venue_name", "").lower()
    if venue_name:
        for keyword in MARSEILLE_VENUE_KEYWORDS:
            if keyword in venue_name:
                return True

    # Check venue URL for Marseille-area venues
    venue_url = verse_block.get("venue_url", "").lower()
    if venue_url:
        for keyword in MARSEILLE_VENUE_KEYWORDS:
            if keyword.replace(" ", "") in venue_url.replace("-", ""):
                return True

    # Check full text for Marseille mentions
    full_text = verse_block.get("full_text", "").lower()
    if "marseille" in full_text:
        return True

    return False


def _map_wp_categories_to_taxonomy(category_ids, category_map):
    """
    Map WordPress category IDs to our standard taxonomy.

    Args:
        category_ids: List of WordPress category IDs
        category_map: Config-based category mapping dict

    Returns:
        Category string from standard taxonomy
    """
    # Check WP category ID map first
    for cat_id in category_ids:
        if cat_id in WP_CATEGORY_MAP:
            return WP_CATEGORY_MAP[cat_id]

    return "communaute"


def _map_wp_tags_to_category(tag_names, category_map):
    """
    Try to determine category from WordPress tag names.

    Args:
        tag_names: List of tag name strings
        category_map: Config-based category mapping dict

    Returns:
        Category string or None
    """
    for tag in tag_names:
        tag_lower = tag.lower()
        # Check config category map
        if category_map:
            for source_cat, target_cat in category_map.items():
                if source_cat.lower() == tag_lower:
                    return target_cat
        # Check common patterns
        if any(k in tag_lower for k in ("danse", "ballet", "chorégraph")):
            return "danse"
        if any(k in tag_lower for k in ("musique", "concert", "jazz", "rap", "rock")):
            return "musique"
        if any(k in tag_lower for k in ("théâtre", "theatre", "spectacle")):
            return "theatre"
        if any(k in tag_lower for k in ("exposition", "art visuel", "photo")):
            return "art"

    return None


class JournalZebulineParser(BaseCrawler):
    """
    Event parser for Journal Zébuline (https://journalzebuline.fr).

    Journal Zébuline is a cultural journalism magazine covering events in
    Marseille and Provence. Unlike structured event listings, this source
    publishes articles about cultural events with practical details embedded
    in wp-block-verse blocks.

    Strategy:
    1. Fetch recent articles via WordPress REST API filtered by
       event-related categories (Scènes, Musiques, Arts visuels, etc.)
    2. Parse article HTML to extract event details from verse blocks
    3. Extract date, venue, and city from structured elements
    4. Filter for Marseille-area events
    5. Use article metadata for images, descriptions, and tags
    """

    source_name = "Journal Zébuline"

    def crawl(self) -> list[Event]:
        """
        Crawl Journal Zébuline via WordPress REST API.

        Overrides BaseCrawler.crawl() to use the REST API instead
        of fetching a single HTML page.

        Returns:
            List of processed Event objects
        """
        logger.info(f"Starting crawl for {self.source_name}")
        self.selection_stats = {"accepted": 0, "rejected": 0}

        # Fetch articles from all relevant categories
        articles = self._fetch_articles()
        if not articles:
            logger.warning("No articles found from Journal Zébuline API")
            return []

        logger.info(f"Fetched {len(articles)} articles from Journal Zébuline")

        # Parse events from articles
        events = []
        for article in articles:
            try:
                article_events = self._parse_article(article)
                events.extend(article_events)
            except Exception as e:
                title = article.get("title", {}).get("rendered", "unknown")
                logger.warning(f"Failed to parse article '{title}': {e}")

        logger.info(f"Parsed {len(events)} events from {self.source_name}")

        # Process each event (selection, dedup, markdown generation)
        processed_events = []
        for event in events:
            try:
                processed = self.process_event(event)
                if processed:
                    processed_events.append(processed)
            except Exception as e:
                logger.error(f"Error processing event '{event.name}': {e}")

        return processed_events

    def parse_events(self, parser: HTMLParser) -> list[Event]:
        """
        Not used - crawl() overrides the base class flow.

        This method exists only to satisfy the abstract interface.
        """
        return []

    def _fetch_articles(self) -> list[dict]:
        """
        Fetch articles from WordPress REST API with full pagination.

        Queries all relevant categories and paginates through every page
        using the X-WP-TotalPages response header. Deduplicates by article ID.

        Returns:
            List of article dicts from the WordPress API
        """
        all_articles = {}
        categories_param = ",".join(str(c) for c in WP_CATEGORY_IDS)
        delay = self.config.get("rate_limit", {}).get("delay_between_pages", 3.0)

        page = 1
        total_pages = None

        while True:
            url = (
                f"{WP_API_BASE}/posts?"
                f"categories={categories_param}"
                f"&per_page={WP_PER_PAGE}"
                f"&page={page}"
                f"&_embed"
                f"&orderby=date&order=desc"
            )

            try:
                result = self.http_client.fetch(url, source_id=self.source_id)
            except Exception as e:
                logger.error(f"Failed to fetch page {page} from API: {e}")
                break

            if not result.success:
                # WordPress returns 400 when page exceeds total_pages
                if result.status_code == 400:
                    logger.debug(f"Reached end of pagination at page {page}")
                    break
                logger.error(f"API error on page {page}: HTTP {result.status_code}")
                break

            # Read total pages from headers on first request
            if total_pages is None:
                total_pages = self._get_header_int(result.headers, "X-WP-TotalPages", 1)
                total_articles = self._get_header_int(result.headers, "X-WP-Total", 0)
                logger.info(
                    f"Journal Zébuline API: {total_articles} articles "
                    f"across {total_pages} pages"
                )

            # Parse articles from JSON response
            try:
                articles = json.loads(result.html)
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse API response page {page}: {e}")
                break

            if not isinstance(articles, list) or not articles:
                logger.debug(f"Empty response on page {page}, stopping")
                break

            new_count = 0
            for article in articles:
                article_id = article.get("id")
                if article_id and article_id not in all_articles:
                    all_articles[article_id] = article
                    new_count += 1

            logger.info(
                f"Page {page}/{total_pages}: {new_count} new articles "
                f"({len(all_articles)} total)"
            )

            # Stop if we've reached the last page
            if page >= total_pages:
                break

            page += 1
            time.sleep(delay)

        logger.info(f"Fetched {len(all_articles)} unique articles total")
        return list(all_articles.values())

    @staticmethod
    def _get_header_int(headers: dict, name: str, default: int) -> int:
        """
        Get an integer value from response headers, case-insensitively.

        Args:
            headers: Response headers dict
            name: Header name to look up
            default: Default value if header is missing or not an integer

        Returns:
            Integer header value or default
        """
        # Try exact case first, then lowercase
        value = headers.get(name) or headers.get(name.lower())
        if value is not None:
            try:
                return int(value)
            except (ValueError, TypeError):
                pass
        return default

    def _parse_article(self, article: dict) -> list[Event]:
        """
        Parse events from a single WordPress article.

        Extracts event details from wp-block-verse blocks in the
        article content.

        Args:
            article: WordPress article dict from REST API

        Returns:
            List of Event objects extracted from the article
        """
        events = []

        # Get article content
        content_html = article.get("content", {}).get("rendered", "")
        if not content_html:
            return events

        # Get article metadata
        title = _clean_html(article.get("title", {}).get("rendered", ""))
        article_url = article.get("link", "")
        article_id = article.get("id", 0)
        category_ids = article.get("categories", [])

        # Get description from Yoast SEO or excerpt
        description = ""
        yoast = article.get("yoast_head_json", {})
        if yoast:
            description = yoast.get("description", "")
        if not description:
            excerpt = article.get("excerpt", {}).get("rendered", "")
            description = _clean_html(excerpt)
        if description and len(description) > 160:
            description = description[:157].rsplit(" ", 1)[0] + "..."

        # Get featured image URL
        image_url = self._extract_article_image(article)

        # Get tags from embedded terms
        tag_names = self._extract_tag_names(article)

        # Determine category
        category = _map_wp_categories_to_taxonomy(category_ids, self.category_map)
        # Try tags for more specific category
        tag_category = _map_wp_tags_to_category(tag_names, self.category_map)
        if tag_category:
            category = tag_category

        # Extract event details from verse blocks
        verse_blocks = _extract_verse_blocks(content_html, self.venue_manager)

        if not verse_blocks:
            logger.debug(f"No verse blocks found in article: {title}")
            return events

        # Get article publication date as reference year
        pub_date_str = article.get("date", "")
        reference_year = datetime.now().year
        if pub_date_str:
            try:
                pub_date = datetime.fromisoformat(pub_date_str)
                reference_year = pub_date.year
            except (ValueError, TypeError):
                pass

        for block in verse_blocks:
            # Filter for Marseille area
            if not _is_marseille_area_event(block):
                logger.debug(
                    f"Skipping non-Marseille event in '{title}': "
                    f"{block.get('venue_name', 'unknown venue')}"
                )
                continue

            # Parse all dates from the date text
            event_dates = _parse_all_french_dates(block["date_text"], reference_year)
            if not event_dates:
                logger.debug(
                    f"Could not parse date '{block['date_text']}' in article: {title}"
                )
                continue

            # Build venue/location
            venue_name = block.get("venue_name", "")
            location = self.map_location(venue_name) if venue_name else ""
            locations = [location] if location else []

            # Build event name (use article title)
            event_name = title

            # Build tags from article tags
            event_tags = [t.lower() for t in tag_names[:5] if len(t) < 50]

            # Create an event for each date
            block_idx = verse_blocks.index(block)
            for date_idx, event_date in enumerate(event_dates):
                # Generate source ID - include block and date index for uniqueness
                if len(verse_blocks) > 1 or len(event_dates) > 1:
                    source_id = f"journalzebuline:{article_id}-{block_idx}-{date_idx}"
                else:
                    source_id = f"journalzebuline:{article_id}"

                try:
                    event = Event(
                        name=event_name,
                        event_url=article_url,
                        start_datetime=event_date,
                        description=description,
                        image=image_url,
                        categories=[category],
                        locations=locations,
                        tags=event_tags,
                        source_id=source_id,
                    )
                    events.append(event)
                except ValueError as e:
                    logger.warning(
                        f"Failed to create event from article '{title}': {e}"
                    )

        return events

    def _extract_article_image(self, article: dict) -> str | None:
        """
        Extract featured image URL from article data.

        Tries embedded media first, falls back to Yoast og:image.

        Args:
            article: WordPress article dict

        Returns:
            Image URL string or None
        """
        # Try embedded featured media
        embedded = article.get("_embedded", {})
        media_list = embedded.get("wp:featuredmedia", [])
        if media_list and isinstance(media_list, list):
            media = media_list[0]
            if isinstance(media, dict):
                source_url = media.get("source_url", "")
                if source_url:
                    return source_url

        # Try Yoast SEO og:image
        yoast = article.get("yoast_head_json", {})
        og_images = yoast.get("og_image", [])
        if og_images and isinstance(og_images, list):
            first_image = og_images[0]
            if isinstance(first_image, dict):
                url = first_image.get("url", "")
                if url:
                    return url

        return None

    def _extract_tag_names(self, article: dict) -> list[str]:
        """
        Extract tag names from embedded term data.

        Args:
            article: WordPress article dict with _embed

        Returns:
            List of tag name strings
        """
        tags = []
        embedded = article.get("_embedded", {})
        terms_list = embedded.get("wp:term", [])

        for term_group in terms_list:
            if not isinstance(term_group, list):
                continue
            for term in term_group:
                if not isinstance(term, dict):
                    continue
                # Tags have taxonomy "post_tag", categories have "category"
                taxonomy = term.get("taxonomy", "")
                if taxonomy == "post_tag":
                    name = term.get("name", "")
                    if name:
                        tags.append(name)

        return tags


def _clean_html(html_text):
    """Remove HTML tags from text."""
    if not html_text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", html_text)
    # Decode HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#8217;", "'")
    text = text.replace("&#8216;", "'")
    text = text.replace("&#8220;", '"')
    text = text.replace("&#8221;", '"')
    text = text.replace("&nbsp;", " ")
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text
