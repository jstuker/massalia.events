"""Selection criteria for filtering events."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .logger import get_logger

# Paris timezone for Marseille events
PARIS_TZ = ZoneInfo("Europe/Paris")

logger = get_logger(__name__)


class SelectionError(Exception):
    """Raised when selection criteria configuration is invalid."""

    pass


@dataclass
class SelectionResult:
    """Result of evaluating an event against selection criteria."""

    accepted: bool
    reason: str
    criteria_matched: str = ""  # Which criteria triggered the decision


@dataclass
class GeographyConfig:
    """Geographic scope configuration."""

    required_location: str = "Marseille"
    include_nearby: list[str] = field(default_factory=list)
    exclude_locations: list[str] = field(default_factory=list)
    local_keywords: list[str] = field(default_factory=list)


@dataclass
class DatesConfig:
    """Date constraints configuration."""

    min_days_ahead: int = 0
    max_days_ahead: int = 90
    exclude_past: bool = True


@dataclass
class EventTypesConfig:
    """Event type filters configuration."""

    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)


@dataclass
class KeywordsConfig:
    """Keyword filters configuration."""

    positive: list[str] = field(default_factory=list)
    negative: list[str] = field(default_factory=list)


@dataclass
class CategoryMappingConfig:
    """Category mapping configuration."""

    default: str = "communaute"
    mappings: dict[str, str] = field(default_factory=dict)


@dataclass
class SelectionCriteria:
    """
    Selection criteria for filtering events.

    Defines rules for which events should be included in the calendar.
    Events are evaluated against geography, dates, event types,
    keywords, and required fields.
    """

    version: str = "1.0"
    geography: GeographyConfig = field(default_factory=GeographyConfig)
    dates: DatesConfig = field(default_factory=DatesConfig)
    event_types: EventTypesConfig = field(default_factory=EventTypesConfig)
    keywords: KeywordsConfig = field(default_factory=KeywordsConfig)
    required_fields: list[str] = field(default_factory=lambda: ["name", "date"])
    recommended_fields: list[str] = field(default_factory=list)
    category_mapping: CategoryMappingConfig = field(
        default_factory=CategoryMappingConfig
    )

    def evaluate(
        self,
        name: str,
        date: datetime | None,
        location: str = "",
        description: str = "",
        category: str = "",
        url: str = "",
    ) -> SelectionResult:
        """
        Evaluate an event against all selection criteria.

        Args:
            name: Event name/title
            date: Event date/time
            location: Event location/venue
            description: Event description
            category: Event category/type
            url: Event URL

        Returns:
            SelectionResult with accepted status and reason
        """
        # Combine all text for keyword matching
        all_text = " ".join(
            [
                name or "",
                location or "",
                description or "",
                category or "",
            ]
        ).lower()

        # 1. Check required fields
        result = self._check_required_fields(name, date, location)
        if not result.accepted:
            return result

        # 2. Check negative keywords (exclusion)
        result = self._check_negative_keywords(all_text)
        if not result.accepted:
            return result

        # 3. Check excluded event types
        result = self._check_excluded_types(all_text, category)
        if not result.accepted:
            return result

        # 4. Check excluded locations
        result = self._check_excluded_locations(location, all_text)
        if not result.accepted:
            return result

        # 5. Check date constraints
        if date:
            result = self._check_date_constraints(date)
            if not result.accepted:
                return result

        # 6. Check included event types (at least one should match for non-empty list)
        if self.event_types.include:
            result = self._check_included_types(all_text, category)
            if not result.accepted:
                return result

        # Event passed all criteria
        positive_keywords = self._find_positive_keywords(all_text)
        if positive_keywords:
            return SelectionResult(
                accepted=True,
                reason=f"Accepted with positive keywords: {', '.join(positive_keywords)}",
                criteria_matched="positive_keywords",
            )

        return SelectionResult(
            accepted=True,
            reason="Accepted - passed all criteria",
            criteria_matched="all_criteria",
        )

    def _check_required_fields(
        self, name: str, date: datetime | None, location: str
    ) -> SelectionResult:
        """Check that required fields are present."""
        missing = []

        if "name" in self.required_fields and not name:
            missing.append("name")
        if "date" in self.required_fields and not date:
            missing.append("date")
        if "location" in self.required_fields and not location:
            missing.append("location")

        if missing:
            return SelectionResult(
                accepted=False,
                reason=f"Missing required fields: {', '.join(missing)}",
                criteria_matched="required_fields",
            )

        return SelectionResult(accepted=True, reason="")

    def _check_negative_keywords(self, text: str) -> SelectionResult:
        """Check for negative keywords that trigger exclusion."""
        for keyword in self.keywords.negative:
            if keyword.lower() in text:
                return SelectionResult(
                    accepted=False,
                    reason=f"Contains negative keyword: '{keyword}'",
                    criteria_matched="negative_keyword",
                )

        return SelectionResult(accepted=True, reason="")

    def _check_excluded_types(self, text: str, category: str) -> SelectionResult:
        """Check for excluded event types."""
        check_text = f"{text} {category}".lower()

        for excluded_type in self.event_types.exclude:
            if excluded_type.lower() in check_text:
                return SelectionResult(
                    accepted=False,
                    reason=f"Excluded event type: '{excluded_type}'",
                    criteria_matched="excluded_type",
                )

        return SelectionResult(accepted=True, reason="")

    def _check_excluded_locations(self, location: str, text: str) -> SelectionResult:
        """Check for excluded locations.

        Skips the check when the event location matches a known local
        keyword, so that city names appearing in titles or descriptions
        (e.g. a film about Paris screened at a Marseille venue) do not
        cause false rejections.
        """
        # If the location itself is a known local venue, trust it
        if location and self.geography.local_keywords:
            loc_normalized = location.lower().replace("-", " ").replace("_", " ")
            for local_kw in self.geography.local_keywords:
                kw_normalized = local_kw.lower().replace("-", " ").replace("_", " ")
                if kw_normalized in loc_normalized or loc_normalized in kw_normalized:
                    return SelectionResult(accepted=True, reason="")

        check_text = f"{location} {text}".lower()

        for excluded_loc in self.geography.exclude_locations:
            if excluded_loc.lower() in check_text:
                return SelectionResult(
                    accepted=False,
                    reason=f"Excluded location: '{excluded_loc}'",
                    criteria_matched="excluded_location",
                )

        return SelectionResult(accepted=True, reason="")

    def _check_date_constraints(self, date: datetime) -> SelectionResult:
        """Check date is within allowed range."""
        now = datetime.now(PARIS_TZ)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Check if past
        if self.dates.exclude_past and date < today:
            return SelectionResult(
                accepted=False,
                reason="Event date is in the past",
                criteria_matched="past_date",
            )

        # Check min days ahead
        min_date = today + timedelta(days=self.dates.min_days_ahead)
        if date < min_date:
            return SelectionResult(
                accepted=False,
                reason=f"Event date is before minimum ({self.dates.min_days_ahead} days ahead)",
                criteria_matched="min_days",
            )

        # Check max days ahead
        max_date = today + timedelta(days=self.dates.max_days_ahead)
        if date > max_date:
            return SelectionResult(
                accepted=False,
                reason=f"Event date is beyond maximum ({self.dates.max_days_ahead} days ahead)",
                criteria_matched="max_days",
            )

        return SelectionResult(accepted=True, reason="")

    def _check_included_types(self, text: str, category: str) -> SelectionResult:
        """Check that event matches at least one included type."""
        check_text = f"{text} {category}".lower()

        for included_type in self.event_types.include:
            if included_type.lower() in check_text:
                return SelectionResult(accepted=True, reason="")

        # No included type matched
        return SelectionResult(
            accepted=False,
            reason="Does not match any included event type",
            criteria_matched="no_included_type",
        )

    def _find_positive_keywords(self, text: str) -> list[str]:
        """Find positive keywords present in text."""
        found = []
        for keyword in self.keywords.positive:
            if keyword.lower() in text:
                found.append(keyword)
        return found

    def map_category(self, source_category: str) -> str:
        """
        Map a source category to standard taxonomy.

        Args:
            source_category: Category from source site

        Returns:
            Standard category slug
        """
        if not source_category:
            return self.category_mapping.default

        source_lower = source_category.lower()

        # Check explicit mappings
        for source, target in self.category_mapping.mappings.items():
            if source.lower() in source_lower:
                return target

        return self.category_mapping.default


def load_selection_criteria(config_path: Path) -> SelectionCriteria:
    """
    Load selection criteria from YAML configuration file.

    Args:
        config_path: Path to selection-criteria.yaml

    Returns:
        SelectionCriteria instance

    Raises:
        SelectionError: If configuration is invalid
    """
    if not config_path.exists():
        logger.warning(f"Selection criteria not found: {config_path}, using defaults")
        return SelectionCriteria()

    logger.info(f"Loading selection criteria from {config_path}")

    try:
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise SelectionError(f"Invalid YAML in selection criteria: {e}") from e

    if not raw:
        logger.warning("Selection criteria file is empty, using defaults")
        return SelectionCriteria()

    # Parse configuration sections
    geography_raw = raw.get("geography", {})
    geography = GeographyConfig(
        required_location=geography_raw.get("required_location", "Marseille"),
        include_nearby=geography_raw.get("include_nearby", []),
        exclude_locations=geography_raw.get("exclude_locations", []),
        local_keywords=geography_raw.get("local_keywords", []),
    )

    dates_raw = raw.get("dates", {})
    dates = DatesConfig(
        min_days_ahead=dates_raw.get("min_days_ahead", 0),
        max_days_ahead=dates_raw.get("max_days_ahead", 90),
        exclude_past=dates_raw.get("exclude_past", True),
    )

    event_types_raw = raw.get("event_types", {})
    event_types = EventTypesConfig(
        include=event_types_raw.get("include", []),
        exclude=event_types_raw.get("exclude", []),
    )

    keywords_raw = raw.get("keywords", {})
    keywords = KeywordsConfig(
        positive=keywords_raw.get("positive", []),
        negative=keywords_raw.get("negative", []),
    )

    category_raw = raw.get("category_mapping", {})
    category_mapping = CategoryMappingConfig(
        default=category_raw.get("default", "communaute"),
        mappings=category_raw.get("mappings", {}),
    )

    criteria = SelectionCriteria(
        version=raw.get("version", "1.0"),
        geography=geography,
        dates=dates,
        event_types=event_types,
        keywords=keywords,
        required_fields=raw.get("required_fields", ["name", "date"]),
        recommended_fields=raw.get("recommended_fields", []),
        category_mapping=category_mapping,
    )

    logger.info(
        f"Loaded selection criteria v{criteria.version}: "
        f"{len(event_types.include)} included types, "
        f"{len(event_types.exclude)} excluded types, "
        f"{len(keywords.negative)} negative keywords"
    )

    return criteria
