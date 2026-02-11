"""Site-specific event parsers."""

from .agendaculturel import AgendaCulturelParser
from .base import ConfigurableEventParser, ParsedEvent, SelectorConfig
from .cepacsilo import CepacSiloParser
from .citemusique import CiteMusiqueParser
from .journalzebuline import JournalZebulineParser
from .klemenis import KlemenisParser
from .lacriee import LaCrieeParser
from .lafriche import LaFricheParser
from .lemakeda import LeMakedaParser
from .lezef import LeZefParser
from .loeuvre import LoeuvreParser
from .shotgun import ShotgunParser
from .videodrome2 import Videodrome2Parser

PARSERS = {
    "lafriche": LaFricheParser,
    "klemenis": KlemenisParser,
    "loeuvre": LoeuvreParser,
    "shotgun": ShotgunParser,
    "agendaculturel": AgendaCulturelParser,
    "journalzebuline": JournalZebulineParser,
    "cepacsilo": CepacSiloParser,
    "citemusique": CiteMusiqueParser,
    "lacriee": LaCrieeParser,
    "lemakeda": LeMakedaParser,
    "lezef": LeZefParser,
    "videodrome2": Videodrome2Parser,
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
    "CepacSiloParser",
    "CiteMusiqueParser",
    "ConfigurableEventParser",
    "JournalZebulineParser",
    "LaCrieeParser",
    "LeMakedaParser",
    "LeZefParser",
    "ParsedEvent",
    "SelectorConfig",
    "LaFricheParser",
    "KlemenisParser",
    "LoeuvreParser",
    "ShotgunParser",
    "Videodrome2Parser",
    "get_parser",
    "list_parsers",
]
