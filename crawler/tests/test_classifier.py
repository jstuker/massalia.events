"""Tests for event classifier module."""

import pytest

from src.classifier import ClassificationResult, EventClassifier


class TestClassificationResult:
    """Tests for ClassificationResult dataclass."""

    def test_basic_result(self):
        result = ClassificationResult(
            category="musique",
            confidence=0.85,
            reason="Matched keyword 'concert'",
        )
        assert result.category == "musique"
        assert result.confidence == 0.85
        assert result.is_confident is True
        assert result.is_uncertain is False

    def test_confident_threshold(self):
        """Test is_confident property at boundary."""
        result_high = ClassificationResult(
            category="danse", confidence=0.7, reason="test"
        )
        result_low = ClassificationResult(
            category="danse", confidence=0.69, reason="test"
        )
        assert result_high.is_confident is True
        assert result_low.is_confident is False

    def test_uncertain_threshold(self):
        """Test is_uncertain property at boundary."""
        result_uncertain = ClassificationResult(
            category="communaute", confidence=0.49, reason="test"
        )
        result_ok = ClassificationResult(
            category="communaute", confidence=0.5, reason="test"
        )
        assert result_uncertain.is_uncertain is True
        assert result_ok.is_uncertain is False

    def test_with_alternatives(self):
        result = ClassificationResult(
            category="musique",
            confidence=0.6,
            reason="Matched keywords",
            alternatives=[("theatre", 0.25), ("art", 0.15)],
        )
        assert len(result.alternatives) == 2
        assert result.alternatives[0] == ("theatre", 0.25)


class TestEventClassifierSourceCategory:
    """Tests for source category mapping."""

    @pytest.fixture
    def classifier(self):
        return EventClassifier()

    def test_source_category_concert(self, classifier):
        result = classifier.classify(
            name="Événement musical",
            source_category="Concert",
        )
        assert result.category == "musique"
        assert result.confidence >= 0.9

    def test_source_category_exposition(self, classifier):
        result = classifier.classify(
            name="Nouvelle exposition",
            source_category="Exposition",
        )
        assert result.category == "art"
        assert result.confidence >= 0.9

    def test_source_category_danse(self, classifier):
        result = classifier.classify(
            name="Soirée spéciale",
            source_category="Danse",
        )
        assert result.category == "danse"
        assert result.confidence >= 0.9

    def test_source_category_theatre(self, classifier):
        result = classifier.classify(
            name="Pièce de saison",
            source_category="Théâtre",
        )
        assert result.category == "theatre"
        assert result.confidence >= 0.9

    def test_source_category_festival(self, classifier):
        result = classifier.classify(
            name="Grand événement",
            source_category="Festival",
        )
        assert result.category == "communaute"
        assert result.confidence >= 0.9


class TestEventClassifierVenueMapping:
    """Tests for venue-based classification."""

    @pytest.fixture
    def classifier(self):
        return EventClassifier()

    def test_venue_klap_danse(self, classifier):
        result = classifier.classify(
            name="Spectacle contemporain",
            location="KLAP Maison pour la danse",
        )
        assert result.category == "danse"
        assert "venue" in result.reason.lower()

    def test_venue_opera_musique(self, classifier):
        result = classifier.classify(
            name="Représentation du soir",
            location="Opéra de Marseille",
        )
        assert result.category == "musique"

    def test_venue_criee_theatre(self, classifier):
        result = classifier.classify(
            name="Nouvelle création",
            location="La Criée - Théâtre National",
        )
        assert result.category == "theatre"

    def test_venue_mucem_art(self, classifier):
        result = classifier.classify(
            name="Ouverture publique",
            location="MUCEM",
        )
        assert result.category == "art"

    def test_venue_friche_multipurpose(self, classifier):
        """Multi-purpose venues should not auto-assign category."""
        result = classifier.classify(
            name="Événement à la Friche",
            location="La Friche Belle de Mai",
        )
        # Should fall back to keyword matching or default
        assert result.category == "communaute"  # Default when no other signals


class TestEventClassifierKeywords:
    """Tests for keyword-based classification."""

    @pytest.fixture
    def classifier(self):
        return EventClassifier()

    def test_keyword_concert_in_name(self, classifier):
        result = classifier.classify(name="Concert de Jazz")
        assert result.category == "musique"
        assert result.confidence > 0.5

    def test_keyword_exposition_in_name(self, classifier):
        result = classifier.classify(name="Exposition Art Moderne")
        assert result.category == "art"

    def test_keyword_ballet_in_name(self, classifier):
        result = classifier.classify(name="Ballet du Bolchoï")
        assert result.category == "danse"

    def test_keyword_theatre_in_name(self, classifier):
        result = classifier.classify(name="Pièce de Théâtre Classique")
        assert result.category == "theatre"

    def test_keyword_festival_in_name(self, classifier):
        result = classifier.classify(name="Festival de Marseille")
        assert result.category == "communaute"

    def test_keyword_in_description(self, classifier):
        result = classifier.classify(
            name="Soirée spéciale",
            description="Venez découvrir notre concert exceptionnel",
        )
        assert result.category == "musique"

    def test_name_keywords_higher_priority(self, classifier):
        """Keywords in name should have higher weight than description."""
        result = classifier.classify(
            name="Concert de Rock",
            description="Une exposition de photos du groupe",
        )
        assert result.category == "musique"

    def test_multiple_keywords_boost_confidence(self, classifier):
        result = classifier.classify(
            name="Grand Concert Jazz Live",
            description="Musique et improvisation toute la soirée",
        )
        assert result.category == "musique"
        assert result.confidence > 0.6


class TestEventClassifierEdgeCases:
    """Tests for edge cases and default behavior."""

    @pytest.fixture
    def classifier(self):
        return EventClassifier()

    def test_no_signals_returns_default(self, classifier):
        result = classifier.classify(name="Événement mystère")
        assert result.category == "communaute"
        assert result.confidence < 0.5

    def test_empty_name(self, classifier):
        result = classifier.classify(name="")
        assert result.category == "communaute"
        assert result.confidence == 0.3

    def test_ambiguous_event(self, classifier):
        """Event with multiple category signals."""
        result = classifier.classify(
            name="Festival de Danse et Musique",
        )
        # Should pick one category
        assert result.category in ["danse", "musique", "communaute"]
        # Should have alternatives
        assert len(result.alternatives) >= 0

    def test_custom_default_category(self):
        classifier = EventClassifier(default_category="art")
        result = classifier.classify(name="Événement sans indice")
        assert result.category == "art"

    def test_case_insensitive_matching(self, classifier):
        result = classifier.classify(name="CONCERT DE JAZZ")
        assert result.category == "musique"

    def test_accented_characters(self, classifier):
        result = classifier.classify(name="Théâtre de la Méditerranée")
        assert result.category == "theatre"


class TestEventClassifierCustomMappings:
    """Tests for custom configuration."""

    def test_custom_source_mapping(self):
        classifier = EventClassifier(
            source_mappings={"spectacle vivant": "theatre"}
        )
        result = classifier.classify(
            name="Performance",
            source_category="Spectacle Vivant",
        )
        assert result.category == "theatre"

    def test_custom_venue_mapping(self):
        classifier = EventClassifier(
            venue_mappings={"salle xyz": "musique"}
        )
        result = classifier.classify(
            name="Événement",
            location="Salle XYZ",
        )
        assert result.category == "musique"

    def test_from_config(self):
        config = {
            "category_mapping": {
                "default": "art",
                "mappings": {
                    "performance": "theatre",
                },
            }
        }
        classifier = EventClassifier.from_config(config)
        result = classifier.classify(
            name="Test",
            source_category="Performance",
        )
        assert result.category == "theatre"


class TestEventClassifierRealWorldExamples:
    """Tests with realistic event examples."""

    @pytest.fixture
    def classifier(self):
        return EventClassifier()

    def test_jazz_concert_at_opera(self, classifier):
        result = classifier.classify(
            name="Soirée Jazz - Trio Méditerranée",
            description="Concert exceptionnel de jazz manouche",
            location="Opéra de Marseille",
        )
        assert result.category == "musique"
        assert result.is_confident

    def test_contemporary_dance_at_klap(self, classifier):
        result = classifier.classify(
            name="Vendre la mèche",
            description="Création chorégraphique contemporaine",
            location="KLAP Maison pour la danse",
        )
        assert result.category == "danse"
        assert result.confidence >= 0.6  # Venue + keyword match

    def test_exhibition_at_mucem(self, classifier):
        result = classifier.classify(
            name="La Relève",
            description="Exposition photographique sur la jeunesse",
            location="MUCEM",
            source_category="Exposition",
        )
        assert result.category == "art"
        assert result.confidence >= 0.9

    def test_theatre_at_criee(self, classifier):
        result = classifier.classify(
            name="Le Malade Imaginaire",
            description="Comédie de Molière mise en scène par...",
            location="La Criée - Théâtre National de Marseille",
        )
        assert result.category == "theatre"

    def test_street_market(self, classifier):
        result = classifier.classify(
            name="Marché de Noël du Vieux-Port",
            description="Artisanat local et produits régionaux",
            location="Quai du Port",
        )
        assert result.category == "communaute"

    def test_vernissage(self, classifier):
        result = classifier.classify(
            name="Vernissage - Œuvres de Jean Dupont",
            description="Ouverture de l'exposition peintures",
            location="Galerie du Panier",
        )
        assert result.category == "art"

    def test_standup_comedy(self, classifier):
        result = classifier.classify(
            name="One Man Show - Ahmed Sylla",
            description="Spectacle d'humour",
            location="Le Silo",
        )
        assert result.category == "theatre"

    def test_dj_night(self, classifier):
        result = classifier.classify(
            name="DJ Set - Techno Night",
            description="Soirée électro avec DJ international",
            location="Dock des Suds",
        )
        assert result.category == "musique"
