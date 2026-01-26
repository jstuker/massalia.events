"""Site-specific event parsers."""

from .lafriche import LaFricheParser

PARSERS = {
    "lafriche": LaFricheParser,
}


def get_parser(name: str):
    """Get parser class by name."""
    parser_class = PARSERS.get(name.lower())
    if not parser_class:
        available = ", ".join(PARSERS.keys())
        raise ValueError(f"Unknown parser: {name}. Available: {available}")
    return parser_class
