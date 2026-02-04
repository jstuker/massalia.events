"""French date and time parsing utilities.

This module provides shared utilities for parsing French-formatted dates and times,
commonly used across event parser implementations. Consolidating these utilities
avoids code duplication and ensures consistent parsing behavior.

Supported formats:
- Single date: "27 janvier 2026", "27 janvier"
- Date with time: "27 janvier 2026 à 19h30"
- Date range: "Du 29 janvier au 7 février 2026"
- Time formats: "19h", "19h30", "19:30"
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

# Paris timezone - standard for French events
PARIS_TZ = ZoneInfo("Europe/Paris")

# French month names to month numbers (1-12)
# Includes both accented and non-accented variants
FRENCH_MONTHS: dict[str, int] = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}

# French day names (lowercase) - for validation or display
FRENCH_DAYS: dict[str, int] = {
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
    "dimanche": 6,
}

# Default event time when not specified (8 PM is common for evening events)
DEFAULT_HOUR = 20
DEFAULT_MINUTE = 0


def parse_french_date(
    text: str,
    reference_year: int | None = None,
    default_hour: int = DEFAULT_HOUR,
    default_minute: int = DEFAULT_MINUTE,
) -> datetime | None:
    """
    Parse a French date string into a datetime object.

    Handles formats like:
    - "27 janvier 2026" (full date)
    - "27 janvier" (date without year, uses reference_year)
    - "Mardi 27 janvier 2026" (with day name prefix)
    - "27 janvier 2026 à 19h30" (with time)
    - "Du 29 janvier au 7 février 2026" (range, returns start date)

    Args:
        text: French date string to parse
        reference_year: Year to use if not specified in text (defaults to current year)
        default_hour: Hour to use if no time is specified (default: 20)
        default_minute: Minute to use if no time is specified (default: 0)

    Returns:
        datetime in Paris timezone, or None if parsing failed
    """
    if not text:
        return None

    if reference_year is None:
        reference_year = datetime.now().year

    text_lower = text.strip().lower()

    # Try to extract time first
    hour, minute = default_hour, default_minute
    time_result = parse_french_time(text_lower)
    if time_result:
        hour, minute = time_result

    # Pattern for date range: "Du DD mois au DD mois YYYY"
    range_pattern = r"du\s+(\d{1,2})\s+(\w+)(?:\s+au\s+\d{1,2}\s+\w+)?\s+(\d{4})"
    match = re.search(range_pattern, text_lower)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        month = FRENCH_MONTHS.get(month_name)
        if month:
            try:
                return datetime(year, month, day, hour, minute, tzinfo=PARIS_TZ)
            except ValueError:
                pass

    # Pattern for single date with year: "DD mois YYYY"
    with_year_pattern = r"(\d{1,2})\s+(\w+)\s+(\d{4})"
    match = re.search(with_year_pattern, text_lower)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        month = FRENCH_MONTHS.get(month_name)
        if month:
            try:
                return datetime(year, month, day, hour, minute, tzinfo=PARIS_TZ)
            except ValueError:
                pass

    # Pattern for single date without year: "DD mois"
    without_year_pattern = r"(\d{1,2})\s+(\w+)\b"
    match = re.search(without_year_pattern, text_lower)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        month = FRENCH_MONTHS.get(month_name)
        if month:
            year = infer_year(month, day, reference_year)
            try:
                return datetime(year, month, day, hour, minute, tzinfo=PARIS_TZ)
            except ValueError:
                pass

    return None


def parse_french_time(text: str) -> tuple[int, int] | None:
    """
    Extract time from French time format.

    Handles formats like:
    - "19h" -> (19, 0)
    - "19h30" -> (19, 30)
    - "19H30" -> (19, 30)
    - "19:30" -> (19, 30)
    - "à 19h30" -> (19, 30)

    Args:
        text: Text containing a time

    Returns:
        Tuple of (hour, minute) or None if no time found
    """
    if not text:
        return None

    # Match "HHhMM" or "HHh" format (French style)
    match = re.search(r"(\d{1,2})[hH](\d{2})?", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour, minute)

    # Match "HH:MM" format
    match = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour, minute)

    return None


def parse_all_french_dates(
    text: str,
    reference_year: int | None = None,
    default_hour: int = DEFAULT_HOUR,
    default_minute: int = DEFAULT_MINUTE,
) -> list[datetime]:
    """
    Parse a French date string and return ALL dates (for ranges and lists).

    Handles formats:
    - "30 janvier" -> [Jan 30]
    - "Du 3 au 5 février" -> [Feb 3, Feb 4, Feb 5]
    - "2, 3 et 5 février" -> [Feb 2, Feb 3, Feb 5]
    - "23 et 24 janvier" -> [Jan 23, Jan 24]
    - "Jusqu'au 31 janvier" -> [Jan 31]

    Args:
        text: French date string
        reference_year: Year to use if not specified in text
        default_hour: Hour to use if no time is specified
        default_minute: Minute to use if no time is specified

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
                    dates.append(
                        datetime(
                            year,
                            month,
                            day,
                            default_hour,
                            default_minute,
                            tzinfo=PARIS_TZ,
                        )
                    )
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
                        datetime(
                            year,
                            month,
                            int(day_str),
                            default_hour,
                            default_minute,
                            tzinfo=PARIS_TZ,
                        )
                    )
                except ValueError:
                    pass
            # Add the day after 'et'
            try:
                dates.append(
                    datetime(
                        year,
                        month,
                        last_day,
                        default_hour,
                        default_minute,
                        tzinfo=PARIS_TZ,
                    )
                )
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
                return [
                    datetime(
                        year, month, day, default_hour, default_minute, tzinfo=PARIS_TZ
                    )
                ]
            except ValueError:
                pass

    # Fallback: single date
    single = parse_french_date(text, reference_year, default_hour, default_minute)
    if single:
        return [single]

    return []


def infer_year(month: int, day: int, reference_year: int | None = None) -> int:
    """
    Infer the year for a date without year specification.

    If the date has already passed this year (by more than 30 days),
    assumes next year.

    Args:
        month: Month number (1-12)
        day: Day of month
        reference_year: Reference year (defaults to current year)

    Returns:
        Inferred year
    """
    if reference_year is None:
        reference_year = datetime.now().year

    now = datetime.now(PARIS_TZ)
    try:
        candidate = datetime(reference_year, month, day, tzinfo=PARIS_TZ)
    except ValueError:
        return reference_year

    # If date is more than 30 days in the past, assume next year
    if (now - candidate).days > 30:
        return reference_year + 1
    return reference_year


def format_french_date(dt: datetime) -> str:
    """
    Format a datetime as a French date string.

    Args:
        dt: datetime to format

    Returns:
        French date string like "27 janvier 2026"
    """
    # Reverse lookup for month name
    month_names = {
        v: k for k, v in FRENCH_MONTHS.items() if "é" in k or "û" in k or len(k) > 4
    }
    # Use accented versions when available
    month_name = month_names.get(dt.month, list(FRENCH_MONTHS.keys())[dt.month - 1])
    return f"{dt.day} {month_name} {dt.year}"
