"""Site-specific event parsers."""

from .agendaculturel import AgendaCulturelParser
from .base import ConfigurableEventParser, ParsedEvent, SelectorConfig
from .klemenis import KlemenisParser
from .lafriche import LaFricheParser
from .shotgun import ShotgunParser

PARSERS = {
    "lafriche": LaFricheParser,
    "klemenis": KlemenisParser,
    "shotgun": ShotgunParser,
    "agendaculturel": AgendaCulturelParser,
    "generic": ConfigurableEventParser,
}


def get_parser(name: str):
    """
    Get parser class by name.

    Args:
        name: Parser name (e.g., 'lafriche', 'generic')

    Returns:
        Parser class

    Raises:
        ValueError: If parser not found
    """
    parser_class = PARSERS.get(name.lower())
    if not parser_class:
        available = ", ".join(PARSERS.keys())
        raise ValueError(f"Unknown parser: {name}. Available: {available}")
    return parser_class


def list_parsers() -> list[str]:
    """
    List all available parser names.

    Returns:
        List of parser names
    """
    return list(PARSERS.keys())


__all__ = [
    "AgendaCulturelParser",
    "ConfigurableEventParser",
    "ParsedEvent",
    "SelectorConfig",
    "LaFricheParser",
    "KlemenisParser",
    "ShotgunParser",
    "get_parser",
    "list_parsers",
]
