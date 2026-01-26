"""Tests for selection criteria module."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from src.selection import (
    CategoryMappingConfig,
    DatesConfig,
    EventTypesConfig,
    GeographyConfig,
    KeywordsConfig,
    SelectionCriteria,
    SelectionError,
    SelectionResult,
    load_selection_criteria,
)


class TestSelectionResult:
    """Tests for SelectionResult dataclass."""

    def test_accepted_result(self):
        result = SelectionResult(accepted=True, reason="Passed all criteria")
        assert result.accepted is True
        assert result.reason == "Passed all criteria"

    def test_rejected_result(self):
        result = SelectionResult(
            accepted=False,
            reason="Contains negative keyword",
            criteria_matched="negative_keyword",
        )
        assert result.accepted is False
        assert result.criteria_matched == "negative_keyword"


class TestSelectionCriteria:
    """Tests for SelectionCriteria evaluation."""

    @pytest.fixture
    def criteria(self):
        """Create a SelectionCriteria with test configuration."""
        return SelectionCriteria(
            geography=GeographyConfig(
                required_location="Marseille",
                exclude_locations=["Paris", "Lyon"],
            ),
            dates=DatesConfig(
                min_days_ahead=0,
                max_days_ahead=90,
                exclude_past=True,
            ),
            event_types=EventTypesConfig(
                include=["concert", "spectacle", "exposition"],
                exclude=["formation", "cours"],
            ),
            keywords=KeywordsConfig(
                positive=["gratuit", "vernissage"],
                negative=["complet", "annulé", "privé"],
            ),
            required_fields=["name", "date"],
            category_mapping=CategoryMappingConfig(
                default="communaute",
                mappings={"concert": "musique", "exposition": "art"},
            ),
        )

    def test_accept_valid_event(self, criteria):
        """Test accepting a valid event."""
        future_date = datetime.now() + timedelta(days=7)
        result = criteria.evaluate(
            name="Concert Jazz à Marseille",
            date=future_date,
            location="La Friche",
            description="Un super concert de jazz",
            category="concert",
        )
        assert result.accepted is True

    def test_reject_missing_name(self, criteria):
        """Test rejecting event without name."""
        future_date = datetime.now() + timedelta(days=7)
        result = criteria.evaluate(
            name="",
            date=future_date,
            location="Marseille",
        )
        assert result.accepted is False
        assert "name" in result.reason.lower()

    def test_reject_missing_date(self, criteria):
        """Test rejecting event without date."""
        result = criteria.evaluate(
            name="Test Event",
            date=None,
            location="Marseille",
        )
        assert result.accepted is False
        assert "date" in result.reason.lower()

    def test_reject_negative_keyword(self, criteria):
        """Test rejecting event with negative keyword."""
        future_date = datetime.now() + timedelta(days=7)
        result = criteria.evaluate(
            name="Concert complet",
            date=future_date,
            location="Marseille",
            category="concert",
        )
        assert result.accepted is False
        assert "complet" in result.reason.lower()

    def test_reject_negative_keyword_in_description(self, criteria):
        """Test rejecting event with negative keyword in description."""
        future_date = datetime.now() + timedelta(days=7)
        result = criteria.evaluate(
            name="Concert Jazz",
            date=future_date,
            description="Événement annulé pour cause de météo",
            category="concert",
        )
        assert result.accepted is False
        assert "annulé" in result.reason.lower()

    def test_reject_excluded_type(self, criteria):
        """Test rejecting excluded event type."""
        future_date = datetime.now() + timedelta(days=7)
        result = criteria.evaluate(
            name="Formation Python",
            date=future_date,
            location="Marseille",
            category="formation",
        )
        assert result.accepted is False
        assert "formation" in result.reason.lower()

    def test_reject_excluded_location(self, criteria):
        """Test rejecting event in excluded location."""
        future_date = datetime.now() + timedelta(days=7)
        result = criteria.evaluate(
            name="Concert à Paris",
            date=future_date,
            location="Paris",
            category="concert",
        )
        assert result.accepted is False
        assert "Paris" in result.reason

    def test_reject_past_date(self, criteria):
        """Test rejecting past event."""
        past_date = datetime.now() - timedelta(days=7)
        result = criteria.evaluate(
            name="Concert passé",
            date=past_date,
            location="Marseille",
            category="concert",
        )
        assert result.accepted is False
        assert "past" in result.reason.lower()

    def test_reject_too_far_future(self, criteria):
        """Test rejecting event too far in future."""
        far_future = datetime.now() + timedelta(days=100)
        result = criteria.evaluate(
            name="Concert dans 100 jours",
            date=far_future,
            location="Marseille",
            category="concert",
        )
        assert result.accepted is False
        assert "maximum" in result.reason.lower() or "beyond" in result.reason.lower()

    def test_reject_no_matching_type(self, criteria):
        """Test rejecting event that doesn't match any included type."""
        future_date = datetime.now() + timedelta(days=7)
        result = criteria.evaluate(
            name="Réunion administrative",
            date=future_date,
            location="Marseille",
            category="réunion",
            description="Une simple réunion",
        )
        assert result.accepted is False
        assert "included event type" in result.reason.lower()

    def test_accept_with_positive_keyword(self, criteria):
        """Test accepting event with positive keyword noted."""
        future_date = datetime.now() + timedelta(days=7)
        result = criteria.evaluate(
            name="Vernissage gratuit",
            date=future_date,
            location="Marseille",
            category="exposition",
        )
        assert result.accepted is True
        assert "positive keywords" in result.reason.lower()

    def test_category_mapping(self, criteria):
        """Test category mapping."""
        assert criteria.map_category("concert") == "musique"
        assert criteria.map_category("CONCERT live") == "musique"
        assert criteria.map_category("exposition") == "art"
        assert criteria.map_category("unknown") == "communaute"


class TestDateConstraints:
    """Tests for date constraint evaluation."""

    @pytest.fixture
    def criteria_strict_dates(self):
        """Create criteria with strict date constraints."""
        return SelectionCriteria(
            dates=DatesConfig(
                min_days_ahead=1,
                max_days_ahead=30,
                exclude_past=True,
            ),
            event_types=EventTypesConfig(include=[]),  # Accept any type
        )

    def test_reject_today_when_min_days_1(self, criteria_strict_dates):
        """Test rejecting today's event when min_days_ahead=1."""
        today = datetime.now().replace(hour=20, minute=0)
        result = criteria_strict_dates.evaluate(
            name="Event Today",
            date=today,
        )
        assert result.accepted is False

    def test_accept_tomorrow(self, criteria_strict_dates):
        """Test accepting tomorrow's event."""
        tomorrow = datetime.now() + timedelta(days=1)
        result = criteria_strict_dates.evaluate(
            name="Event Tomorrow",
            date=tomorrow,
        )
        assert result.accepted is True

    def test_reject_31_days_ahead(self, criteria_strict_dates):
        """Test rejecting event 31 days ahead when max is 30."""
        future = datetime.now() + timedelta(days=31)
        result = criteria_strict_dates.evaluate(
            name="Event in 31 days",
            date=future,
        )
        assert result.accepted is False


class TestKeywordFiltering:
    """Tests for keyword-based filtering."""

    @pytest.fixture
    def criteria_keywords(self):
        """Create criteria with keyword filters."""
        return SelectionCriteria(
            keywords=KeywordsConfig(
                positive=["gratuit", "entrée libre", "première"],
                negative=["sold out", "complet", "annulé", "privé"],
            ),
            event_types=EventTypesConfig(include=[]),
        )

    def test_reject_sold_out(self, criteria_keywords):
        """Test rejecting sold out events."""
        future = datetime.now() + timedelta(days=7)
        result = criteria_keywords.evaluate(
            name="Concert - Sold Out",
            date=future,
        )
        assert result.accepted is False

    def test_reject_private_event(self, criteria_keywords):
        """Test rejecting private events."""
        future = datetime.now() + timedelta(days=7)
        result = criteria_keywords.evaluate(
            name="Soirée",
            date=future,
            description="Événement privé sur invitation",
        )
        assert result.accepted is False

    def test_accept_free_event(self, criteria_keywords):
        """Test accepting free events with positive boost."""
        future = datetime.now() + timedelta(days=7)
        result = criteria_keywords.evaluate(
            name="Concert gratuit",
            date=future,
        )
        assert result.accepted is True
        assert "gratuit" in result.reason.lower()


class TestLoadSelectionCriteria:
    """Tests for loading selection criteria from YAML."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_load_valid_config(self, temp_dir):
        """Test loading a valid configuration."""
        config = {
            "version": "1.0",
            "geography": {"required_location": "Marseille"},
            "dates": {"max_days_ahead": 60},
            "event_types": {"include": ["concert"], "exclude": ["formation"]},
            "keywords": {"negative": ["annulé"]},
        }

        config_file = temp_dir / "selection-criteria.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        criteria = load_selection_criteria(config_file)

        assert criteria.version == "1.0"
        assert criteria.geography.required_location == "Marseille"
        assert criteria.dates.max_days_ahead == 60
        assert "concert" in criteria.event_types.include
        assert "annulé" in criteria.keywords.negative

    def test_load_nonexistent_returns_defaults(self, temp_dir):
        """Test that missing file returns default criteria."""
        nonexistent = temp_dir / "nonexistent.yaml"
        criteria = load_selection_criteria(nonexistent)

        assert criteria is not None
        assert criteria.required_fields == ["name", "date"]

    def test_load_empty_returns_defaults(self, temp_dir):
        """Test that empty file returns default criteria."""
        config_file = temp_dir / "selection-criteria.yaml"
        config_file.write_text("")

        criteria = load_selection_criteria(config_file)

        assert criteria is not None

    def test_load_invalid_yaml_raises(self, temp_dir):
        """Test that invalid YAML raises error."""
        config_file = temp_dir / "selection-criteria.yaml"
        config_file.write_text("invalid: yaml: content: [")

        with pytest.raises(SelectionError, match="Invalid YAML"):
            load_selection_criteria(config_file)

    def test_load_with_category_mapping(self, temp_dir):
        """Test loading category mapping."""
        config = {
            "category_mapping": {
                "default": "communaute",
                "mappings": {"concert": "musique", "expo": "art"},
            }
        }

        config_file = temp_dir / "selection-criteria.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        criteria = load_selection_criteria(config_file)

        assert criteria.category_mapping.default == "communaute"
        assert criteria.map_category("concert") == "musique"
        assert criteria.map_category("expo") == "art"
