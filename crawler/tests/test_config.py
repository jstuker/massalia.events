"""Tests for configuration loading and validation."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.config import (
    ConfigurationError,
    RateLimit,
    Selectors,
    Source,
    SourcesConfig,
    load_sources_config,
)


class TestRateLimit:
    """Tests for RateLimit dataclass."""

    def test_default_values(self):
        rate_limit = RateLimit()
        assert rate_limit.requests_per_second == 1.0
        assert rate_limit.delay_between_pages == 2.0

    def test_custom_values(self):
        rate_limit = RateLimit(requests_per_second=0.5, delay_between_pages=3.0)
        assert rate_limit.requests_per_second == 0.5
        assert rate_limit.delay_between_pages == 3.0


class TestSelectors:
    """Tests for Selectors dataclass."""

    def test_default_values(self):
        selectors = Selectors()
        assert selectors.event_list is None
        assert selectors.event_item is None

    def test_custom_values(self):
        selectors = Selectors(event_list=".events", event_item=".event-card")
        assert selectors.event_list == ".events"
        assert selectors.event_item == ".event-card"


class TestSource:
    """Tests for Source dataclass."""

    def test_required_fields(self):
        source = Source(
            name="Test Source",
            id="test",
            url="https://example.com",
            parser="test_parser",
        )
        assert source.name == "Test Source"
        assert source.id == "test"
        assert source.url == "https://example.com"
        assert source.parser == "test_parser"

    def test_default_values(self):
        source = Source(
            name="Test",
            id="test",
            url="https://example.com",
            parser="test",
        )
        assert source.enabled is True
        assert source.rate_limit.requests_per_second == 1.0
        assert source.categories_map == {}

    def test_env_url_override(self):
        """Test environment variable URL override."""
        os.environ["CRAWLER_SOURCE_TEST_URL"] = "https://override.example.com"
        try:
            source = Source(
                name="Test",
                id="test",
                url="https://example.com",
                parser="test",
            )
            assert source.url == "https://override.example.com"
        finally:
            del os.environ["CRAWLER_SOURCE_TEST_URL"]

    def test_env_enabled_override(self):
        """Test environment variable enabled override."""
        os.environ["CRAWLER_SOURCE_TEST_ENABLED"] = "false"
        try:
            source = Source(
                name="Test",
                id="test",
                url="https://example.com",
                parser="test",
            )
            assert source.enabled is False
        finally:
            del os.environ["CRAWLER_SOURCE_TEST_ENABLED"]

    def test_env_enabled_override_true(self):
        """Test environment variable enabled override with true."""
        os.environ["CRAWLER_SOURCE_TEST_ENABLED"] = "true"
        try:
            source = Source(
                name="Test",
                id="test",
                url="https://example.com",
                parser="test",
                enabled=False,
            )
            assert source.enabled is True
        finally:
            del os.environ["CRAWLER_SOURCE_TEST_ENABLED"]


class TestSourcesConfig:
    """Tests for SourcesConfig dataclass."""

    @pytest.fixture
    def sample_sources(self):
        return [
            Source(name="Source 1", id="source1", url="https://s1.com", parser="p1"),
            Source(
                name="Source 2",
                id="source2",
                url="https://s2.com",
                parser="p2",
                enabled=False,
            ),
            Source(name="Source 3", id="source3", url="https://s3.com", parser="p1"),
        ]

    def test_get_enabled_sources(self, sample_sources):
        config = SourcesConfig(sources=sample_sources)
        enabled = config.get_enabled_sources()
        assert len(enabled) == 2
        assert all(s.enabled for s in enabled)

    def test_get_source_by_id(self, sample_sources):
        config = SourcesConfig(sources=sample_sources)

        source = config.get_source_by_id("source2")
        assert source is not None
        assert source.name == "Source 2"

        not_found = config.get_source_by_id("nonexistent")
        assert not_found is None

    def test_get_source_by_parser(self, sample_sources):
        config = SourcesConfig(sources=sample_sources)
        p1_sources = config.get_source_by_parser("p1")
        assert len(p1_sources) == 2


class TestLoadSourcesConfig:
    """Tests for load_sources_config function."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary directory with config files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_load_valid_config(self, temp_config_dir):
        """Test loading a valid configuration."""
        config_data = {
            "sources": [
                {
                    "name": "Test Source",
                    "id": "test",
                    "url": "https://example.com",
                    "parser": "test",
                    "enabled": True,
                }
            ]
        }

        config_file = temp_config_dir / "sources.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_sources_config(config_file)

        assert len(config.sources) == 1
        assert config.sources[0].name == "Test Source"
        assert config.sources[0].id == "test"

    def test_load_config_with_defaults(self, temp_config_dir):
        """Test loading configuration with defaults section."""
        config_data = {
            "sources": [
                {
                    "name": "Test",
                    "id": "test",
                    "url": "https://example.com",
                    "parser": "test",
                }
            ],
            "defaults": {
                "rate_limit": {"requests_per_second": 0.5, "delay_between_pages": 5.0}
            },
        }

        config_file = temp_config_dir / "sources.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_sources_config(config_file)

        # Should apply defaults
        assert config.sources[0].rate_limit.requests_per_second == 0.5
        assert config.sources[0].rate_limit.delay_between_pages == 5.0

    def test_load_config_with_category_map(self, temp_config_dir):
        """Test loading configuration with category mapping."""
        config_data = {
            "sources": [
                {
                    "name": "Test",
                    "id": "test",
                    "url": "https://example.com",
                    "parser": "test",
                    "categories_map": {"Concert": "musique", "Spectacle": "theatre"},
                }
            ]
        }

        config_file = temp_config_dir / "sources.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_sources_config(config_file)

        assert config.sources[0].categories_map == {
            "Concert": "musique",
            "Spectacle": "theatre",
        }

    def test_file_not_found(self):
        """Test error when config file doesn't exist."""
        with pytest.raises(ConfigurationError, match="not found"):
            load_sources_config(Path("/nonexistent/sources.yaml"))

    def test_empty_config(self, temp_config_dir):
        """Test error when config file is empty."""
        config_file = temp_config_dir / "sources.yaml"
        config_file.write_text("")

        with pytest.raises(ConfigurationError, match="empty"):
            load_sources_config(config_file)

    def test_no_sources(self, temp_config_dir):
        """Test error when no sources defined."""
        config_data = {"defaults": {"enabled": True}}

        config_file = temp_config_dir / "sources.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with pytest.raises(ConfigurationError, match="No sources"):
            load_sources_config(config_file)

    def test_missing_required_field(self, temp_config_dir):
        """Test error when required field is missing."""
        config_data = {
            "sources": [
                {
                    "name": "Test",
                    # Missing id, url, parser
                }
            ]
        }

        config_file = temp_config_dir / "sources.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with pytest.raises(ConfigurationError, match="Missing required field"):
            load_sources_config(config_file)

    def test_invalid_yaml(self, temp_config_dir):
        """Test error when YAML is invalid."""
        config_file = temp_config_dir / "sources.yaml"
        config_file.write_text("invalid: yaml: content: [")

        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            load_sources_config(config_file)

    def test_load_with_selectors(self, temp_config_dir):
        """Test loading configuration with custom selectors."""
        config_data = {
            "sources": [
                {
                    "name": "Test",
                    "id": "test",
                    "url": "https://example.com",
                    "parser": "test",
                    "selectors": {
                        "event_list": ".events",
                        "event_item": ".event-card",
                    },
                }
            ]
        }

        config_file = temp_config_dir / "sources.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_sources_config(config_file)

        assert config.sources[0].selectors.event_list == ".events"
        assert config.sources[0].selectors.event_item == ".event-card"
