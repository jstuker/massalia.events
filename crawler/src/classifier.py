"""Event classifier for automatic category assignment."""

import re
from dataclasses import dataclass, field

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class ClassificationResult:
    """
    Result of event classification.

    Contains the assigned category, confidence score, and reasoning.
    """

    category: str
    confidence: float
    reason: str
    alternatives: list[tuple[str, float]] = field(default_factory=list)

    @property
    def is_confident(self) -> bool:
        """Check if classification has high confidence (>= 0.7)."""
        return self.confidence >= 0.7

    @property
    def is_uncertain(self) -> bool:
        """Check if classification is uncertain (< 0.5)."""
        return self.confidence < 0.5


class EventClassifier:
    """
    Automatic event classifier using keyword matching and venue mapping.

    Classifies events into taxonomy categories:
    - danse: Dance performances, ballet, choreography
    - musique: Concerts, music festivals, DJ sets
    - theatre: Theatre, comedy, circus, performances
    - art: Exhibitions, galleries, visual arts
    - communaute: Community events, festivals, markets

    Classification uses multiple signals:
    1. Source category mapping (highest priority)
    2. Venue-based hints
    3. Keyword matching in name/description
    """

    # Standard taxonomy categories (lowercase slugs)
    CATEGORIES = ["danse", "musique", "theatre", "art", "communaute"]

    # Category keywords (French)
    CATEGORY_KEYWORDS: dict[str, list[str]] = {
        "danse": [
            "danse",
            "ballet",
            "chorégraphie",
            "choregraphie",
            "hip-hop",
            "hip hop",
            "contemporain",
            "classique",
            "flamenco",
            "tango",
            "salsa",
            "breakdance",
            "break dance",
            "modern jazz",
            "danseur",
            "danseuse",
            "bal",
        ],
        "musique": [
            "concert",
            "musique",
            "music",
            "jazz",
            "rock",
            "électro",
            "electro",
            "techno",
            "house",
            "classique",
            "orchestre",
            "chanson",
            "rap",
            "dj",
            "dj set",
            "live",
            "festival musical",
            "symphonie",
            "opéra",
            "opera",
            "chorale",
            "récital",
            "recital",
            "philharmonique",
            "acoustique",
            "unplugged",
        ],
        "theatre": [
            "théâtre",
            "theatre",
            "spectacle",
            "pièce",
            "piece",
            "comédie",
            "comedie",
            "tragédie",
            "tragedie",
            "one-man-show",
            "one man show",
            "humour",
            "humor",
            "stand-up",
            "stand up",
            "marionnettes",
            "marionnette",
            "cirque",
            "circus",
            "magie",
            "magic",
            "conte",
            "contes",
            "lecture",
            "dramaturge",
            "mise en scène",
            "clown",
        ],
        "art": [
            "exposition",
            "expo",
            "vernissage",
            "galerie",
            "gallery",
            "art",
            "peinture",
            "sculpture",
            "photo",
            "photographie",
            "photography",
            "installation",
            "art contemporain",
            "beaux-arts",
            "beaux arts",
            "musée",
            "musee",
            "museum",
            "cinéma",
            "cinema",
            "projection",
            "film",
            "street art",
            "graffiti",
            "dessin",
            "gravure",
            "céramique",
            "ceramique",
        ],
        "communaute": [
            "festival",
            "marché",
            "marche",
            "brocante",
            "vide-grenier",
            "vide grenier",
            "fête",
            "fete",
            "carnaval",
            "défilé",
            "defile",
            "parade",
            "célébration",
            "celebration",
            "rencontre",
            "atelier",
            "workshop",
            "conférence",
            "conference",
            "débat",
            "debat",
            "forum",
            "salon",
            "journée",
            "journee",
            "portes ouvertes",
        ],
    }

    # Venue-to-category mapping for known Marseille venues
    VENUE_CATEGORIES: dict[str, str | None] = {
        # Dance venues
        "klap": "danse",
        "ballet": "danse",
        "maison de la danse": "danse",
        # Music venues
        "opéra": "musique",
        "opera": "musique",
        "conservatoire": "musique",
        "cabaret": "musique",
        "dock des suds": "musique",
        "espace julien": "musique",
        "moulin": "musique",
        # Theatre venues
        "théâtre": "theatre",
        "theatre": "theatre",
        "criée": "theatre",
        "criee": "theatre",
        "gymnase": "theatre",
        "toursky": "theatre",
        "bernardines": "theatre",
        # Art venues
        "galerie": "art",
        "musée": "art",
        "musee": "art",
        "mucem": "art",
        "mac": "art",
        "frac": "art",
        "vieille charité": "art",
        "vieille charite": "art",
        "château de servières": "art",
        # Multi-purpose venues (no automatic category)
        "friche": None,
        "la friche": None,
        "cité de la musique": None,
        "cite de la musique": None,
    }

    # Default source category mappings
    DEFAULT_SOURCE_MAPPINGS: dict[str, str] = {
        # Music
        "concert": "musique",
        "musique": "musique",
        "music": "musique",
        "dj": "musique",
        "électro": "musique",
        "electro": "musique",
        "jazz": "musique",
        "rock": "musique",
        "hip-hop": "musique",
        "rap": "musique",
        "classique": "musique",
        "opéra": "musique",
        "chorale": "musique",
        # Theatre
        "spectacle": "theatre",
        "théâtre": "theatre",
        "theatre": "theatre",
        "comédie": "theatre",
        "comedie": "theatre",
        "humour": "theatre",
        "stand-up": "theatre",
        "cirque": "theatre",
        "marionnettes": "theatre",
        "conte": "theatre",
        # Dance
        "danse": "danse",
        "dance": "danse",
        "ballet": "danse",
        "contemporain": "danse",
        "flamenco": "danse",
        "tango": "danse",
        "salsa": "danse",
        "bal": "danse",
        # Art
        "exposition": "art",
        "expo": "art",
        "art": "art",
        "vernissage": "art",
        "galerie": "art",
        "photographie": "art",
        "peinture": "art",
        "sculpture": "art",
        "installation": "art",
        "cinéma": "art",
        "projection": "art",
        "film": "art",
        # Community
        "festival": "communaute",
        "fête": "communaute",
        "fete": "communaute",
        "marché": "communaute",
        "marche": "communaute",
        "brocante": "communaute",
        "carnaval": "communaute",
        "défilé": "communaute",
        "atelier": "communaute",
        "workshop": "communaute",
        "rencontre": "communaute",
        "conférence": "communaute",
        "débat": "communaute",
    }

    def __init__(
        self,
        source_mappings: dict[str, str] | None = None,
        venue_mappings: dict[str, str | None] | None = None,
        keyword_mappings: dict[str, list[str]] | None = None,
        default_category: str = "communaute",
    ):
        """
        Initialize the event classifier.

        Args:
            source_mappings: Custom source category to taxonomy mappings
            venue_mappings: Custom venue to category mappings
            keyword_mappings: Custom keyword lists per category
            default_category: Default category when no match found
        """
        # Merge default mappings with custom ones
        self.source_mappings = {**self.DEFAULT_SOURCE_MAPPINGS}
        if source_mappings:
            self.source_mappings.update(source_mappings)

        self.venue_mappings = {**self.VENUE_CATEGORIES}
        if venue_mappings:
            self.venue_mappings.update(venue_mappings)

        self.keyword_mappings = {**self.CATEGORY_KEYWORDS}
        if keyword_mappings:
            for cat, keywords in keyword_mappings.items():
                if cat in self.keyword_mappings:
                    self.keyword_mappings[cat].extend(keywords)
                else:
                    self.keyword_mappings[cat] = keywords

        self.default_category = default_category

    def classify(
        self,
        name: str,
        description: str = "",
        location: str = "",
        source_category: str = "",
    ) -> ClassificationResult:
        """
        Classify an event into a taxonomy category.

        Args:
            name: Event name/title
            description: Event description
            location: Event venue/location
            source_category: Category from source website

        Returns:
            ClassificationResult with category, confidence, and reasoning
        """
        scores: dict[str, float] = dict.fromkeys(self.CATEGORIES, 0.0)

        # Normalize all text
        name_norm = self._normalize(name)
        desc_norm = self._normalize(description)
        location_norm = self._normalize(location)
        source_cat_norm = self._normalize(source_category)

        # 1. Check source category mapping (highest priority)
        if source_cat_norm:
            for source_key, target_cat in self.source_mappings.items():
                if source_key.lower() in source_cat_norm:
                    logger.debug(
                        f"Source category match: '{source_key}' → '{target_cat}'"
                    )
                    return ClassificationResult(
                        category=target_cat,
                        confidence=0.95,
                        reason=f"Source category mapped: '{source_category}' → {target_cat}",
                    )

        # 2. Check venue mapping
        venue_match = None
        for venue_key, category in self.venue_mappings.items():
            if venue_key in location_norm:
                if category:  # Skip None (multi-purpose venues)
                    scores[category] += 3.0
                    venue_match = (venue_key, category)
                    logger.debug(f"Venue match: '{venue_key}' → '{category}' (+3.0)")
                break

        # 3. Keyword matching in name (higher weight)
        for category, keywords in self.keyword_mappings.items():
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in name_norm:
                    scores[category] += 2.0
                    logger.debug(f"Name keyword match: '{keyword}' → '{category}' (+2.0)")

        # 4. Keyword matching in description
        for category, keywords in self.keyword_mappings.items():
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in desc_norm and keyword_lower not in name_norm:
                    scores[category] += 1.0
                    logger.debug(f"Desc keyword match: '{keyword}' → '{category}' (+1.0)")

        # Find best category
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_category, best_score = sorted_scores[0]

        # Calculate confidence
        total_score = sum(scores.values())
        if total_score > 0:
            confidence = best_score / total_score
            # Boost confidence if score is high
            if best_score >= 5.0:
                confidence = min(confidence + 0.1, 0.95)
        else:
            confidence = 0.0

        # Build alternatives list
        alternatives = [
            (cat, score) for cat, score in sorted_scores[1:4] if score > 0
        ]

        # Use default if no clear match
        if best_score == 0:
            logger.debug(f"No matches found, using default: '{self.default_category}'")
            return ClassificationResult(
                category=self.default_category,
                confidence=0.3,
                reason="No category keywords matched, using default",
                alternatives=[],
            )

        # Build reason string
        reasons = []
        if venue_match:
            reasons.append(f"venue '{venue_match[0]}'")
        keyword_count = int(best_score - (3.0 if venue_match else 0))
        if keyword_count > 0:
            reasons.append(f"{keyword_count} keyword(s)")

        reason = f"Matched {', '.join(reasons)} for '{best_category}'"

        logger.debug(
            f"Classification: '{name[:30]}...' → {best_category} "
            f"(confidence: {confidence:.2f})"
        )

        return ClassificationResult(
            category=best_category,
            confidence=min(confidence, 0.95),
            reason=reason,
            alternatives=alternatives,
        )

    def classify_event(self, event) -> ClassificationResult:
        """
        Classify an Event model instance.

        Args:
            event: Event model with name, description, locations, categories

        Returns:
            ClassificationResult
        """
        return self.classify(
            name=event.name,
            description=event.description or "",
            location=" ".join(event.locations) if event.locations else "",
            source_category=" ".join(event.categories) if event.categories else "",
        )

    def _normalize(self, text: str) -> str:
        """
        Normalize text for matching.

        Args:
            text: Raw text

        Returns:
            Lowercase, stripped text with normalized whitespace
        """
        if not text:
            return ""
        # Convert to lowercase
        text = text.lower()
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @classmethod
    def from_config(cls, config: dict) -> "EventClassifier":
        """
        Create classifier from configuration dictionary.

        Args:
            config: Configuration with optional mappings

        Returns:
            EventClassifier instance
        """
        category_mapping = config.get("category_mapping", {})
        return cls(
            source_mappings=category_mapping.get("mappings"),
            default_category=category_mapping.get("default", "communaute"),
        )
