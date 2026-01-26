"""Massalia Events Crawler - Event aggregation for Marseille cultural events."""

from .classifier import ClassificationResult, EventClassifier
from .deduplicator import DuplicateResult, EventDeduplicator, MergeResult

__version__ = "1.0.0"

__all__ = [
    "ClassificationResult",
    "DuplicateResult",
    "EventClassifier",
    "EventDeduplicator",
    "MergeResult",
]
