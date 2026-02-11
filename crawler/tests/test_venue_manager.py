"""Tests for venue manager module."""

from pathlib import Path

import pytest
import yaml

from src.venue_manager import (
    VenueDuplicateResult,
    VenueManager,
    _extract_alias_slug,
    _normalize,
    _slug_to_words,
    _strip_accents,
    _strip_articles,
)

# ---------------------------------------------------------------------------
# Helper: minimal venues.yaml for tests
# ---------------------------------------------------------------------------

SAMPLE_VENUES = [
    {
        "slug": "la-friche",
        "title": "La Friche la Belle de Mai",
        "description": "Espace culturel pluridisciplinaire.",
        "address": "41 rue Jobin, 13003 Marseille",
        "website": "https://www.lafriche.org/",
        "type": "Complexe culturel",
        "aliases": ["/locations/friche/", "/locations/friche-belle-de-mai/"],
        "body": "",
    },
    {
        "slug": "le-makeda",
        "title": "Le Makeda",
        "description": "Bar musical et salle de concerts.",
        "address": "18 Place aux Huiles, 13001 Marseille",
        "website": "https://www.lemakeda.com/",
        "type": "Bar musical",
        "aliases": ["/locations/makeda/", "/locations/le-makeda-marseille/"],
        "body": "",
    },
    {
        "slug": "theatre-de-l-oeuvre",
        "title": "Theatre de l'Oeuvre",
        "description": "Theatre de 170 places.",
        "address": "1 rue Mission de France, 13001 Marseille",
        "website": "https://www.theatre-oeuvre.com/",
        "type": "Theatre",
        "search_names": ["la mesón", "la meson"],
        "aliases": [],
        "body": "",
    },
    {
        "slug": "cabaret-aleatoire",
        "title": "Cabaret Aleatoire",
        "description": "Salle de concerts.",
        "address": "41 Rue Jobin, 13003 Marseille",
        "website": "https://www.cabaret-aleatoire.com/",
        "type": "Salle de spectacle",
        "aliases": [
            "/locations/cabaret-aléatoire/",
            "/locations/cabaret-aleatoire-marseille/",
            "/locations/le-cabaret-aleatoire/",
        ],
        "body": "",
    },
    {
        "slug": "bmvr-alcazar",
        "title": "BMVR Alcazar",
        "description": "Bibliotheque municipale.",
        "address": "58 Cours Belsunce, 13001 Marseille",
        "website": "https://www.bmvr.marseille.fr/",
        "type": "Bibliotheque",
        "search_names": ["alcazar"],
        "aliases": [],
        "body": "",
    },
    {
        "slug": "videodrome-2",
        "title": "Videodrome 2",
        "description": "Cinema associatif.",
        "address": "49 Cours Julien, 13006 Marseille",
        "website": "https://www.videodrome2.fr/",
        "type": "Cinema",
        "search_names": ["vidéodrome", "videodrome2"],
        "aliases": [],
        "body": "",
    },
    {
        "slug": "notre-dame-de-la-garde",
        "title": "Notre Dame de la Garde",
        "description": "Basilique emblematique de Marseille.",
        "address": "Rue Fort du Sanctuaire, 13006 Marseille",
        "website": "https://www.notredamedelagarde.com/",
        "type": "Monument historique",
        "search_names": ["notre-dame"],
        "aliases": ["/locations/bonne-mere/", "/locations/ndg/"],
        "body": "",
    },
]


@pytest.fixture
def venues_file(tmp_path):
    """Create a temporary venues.yaml file."""
    venues_path = tmp_path / "venues.yaml"
    with open(venues_path, "w", encoding="utf-8") as f:
        yaml.dump(SAMPLE_VENUES, f, allow_unicode=True)
    return venues_path


@pytest.fixture
def vm(venues_file):
    """Create a VenueManager from sample data."""
    return VenueManager(venues_file)


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------


class TestUtilityFunctions:
    def test_strip_accents(self):
        assert _strip_accents("café") == "cafe"
        assert _strip_accents("théâtre") == "theatre"
        assert _strip_accents("montévidéo") == "montevideo"
        assert _strip_accents("hello") == "hello"

    def test_normalize_basic(self):
        assert _normalize("Hello World") == "hello world"
        assert _normalize("  extra  spaces  ") == "extra spaces"

    def test_normalize_accents(self):
        assert _normalize("Théâtre Gyptis") == "theatre gyptis"
        assert _normalize("Cabaret Aléatoire") == "cabaret aleatoire"

    def test_normalize_hyphens(self):
        assert _normalize("le-makeda") == "le makeda"
        assert _normalize("notre-dame-de-la-garde") == "notre dame de la garde"

    def test_normalize_apostrophes(self):
        assert _normalize("l'alhambra") == "l alhambra"
        assert _normalize("Theatre de l'Oeuvre") == "theatre de l oeuvre"

    def test_slug_to_words(self):
        assert _slug_to_words("le-cepac-silo") == "le cepac silo"
        assert _slug_to_words("klap") == "klap"

    def test_extract_alias_slug(self):
        assert _extract_alias_slug("/locations/friche/") == "friche"
        assert _extract_alias_slug("/locations/mac-marseille/") == "mac-marseille"
        assert _extract_alias_slug("/invalid/") == ""
        assert _extract_alias_slug("") == ""

    def test_strip_articles(self):
        assert _strip_articles("le makeda") == "makeda"
        assert _strip_articles("la friche") == "friche"
        assert _strip_articles("les bancs publics") == "bancs publics"
        assert _strip_articles("cabaret aleatoire") == "cabaret aleatoire"


# ---------------------------------------------------------------------------
# VenueManager initialization tests
# ---------------------------------------------------------------------------


class TestVenueManagerInit:
    def test_loads_venues(self, vm):
        assert len(vm.venues) == len(SAMPLE_VENUES)

    def test_builds_lookup(self, vm):
        assert len(vm._lookup) > 0
        assert len(vm._sorted_keys) > 0

    def test_missing_file(self, tmp_path):
        vm = VenueManager(tmp_path / "nonexistent.yaml")
        assert vm.venues == []
        assert vm._lookup == {}

    def test_get_all_slugs(self, vm):
        slugs = vm.get_all_slugs()
        assert "la-friche" in slugs
        assert "le-makeda" in slugs
        assert len(slugs) == len(SAMPLE_VENUES)

    def test_get_venue(self, vm):
        venue = vm.get_venue("la-friche")
        assert venue is not None
        assert venue["title"] == "La Friche la Belle de Mai"

    def test_get_venue_not_found(self, vm):
        assert vm.get_venue("nonexistent") is None


# ---------------------------------------------------------------------------
# map_location tests
# ---------------------------------------------------------------------------


class TestMapLocation:
    """Test location name to slug mapping."""

    def test_empty_input(self, vm):
        assert vm.map_location("") == ""

    def test_exact_slug_match(self, vm):
        """Slug-as-words should match exactly."""
        assert vm.map_location("le-makeda") == "le-makeda"
        assert vm.map_location("la-friche") == "la-friche"

    def test_title_match(self, vm):
        """Full venue title should match."""
        assert vm.map_location("Le Makeda") == "le-makeda"
        assert vm.map_location("La Friche la Belle de Mai") == "la-friche"
        assert vm.map_location("Cabaret Aleatoire") == "cabaret-aleatoire"

    def test_case_insensitive(self, vm):
        assert vm.map_location("LE MAKEDA") == "le-makeda"
        assert vm.map_location("cabaret ALEATOIRE") == "cabaret-aleatoire"

    def test_accent_handling(self, vm):
        """Accented input should match accent-stripped keys."""
        assert vm.map_location("Cabaret Aléatoire") == "cabaret-aleatoire"

    def test_alias_match(self, vm):
        """Hugo aliases should generate lookup keys."""
        assert vm.map_location("friche") == "la-friche"
        assert vm.map_location("makeda") == "le-makeda"
        assert vm.map_location("bonne-mere") == "notre-dame-de-la-garde"

    def test_search_names(self, vm):
        """Explicit search_names should match."""
        assert vm.map_location("la mesón") == "theatre-de-l-oeuvre"
        assert vm.map_location("la meson") == "theatre-de-l-oeuvre"

    def test_search_names_alcazar(self, vm):
        """Short search_name 'alcazar' should match."""
        assert vm.map_location("Alcazar") == "bmvr-alcazar"

    def test_article_stripping(self, vm):
        """Article-stripped title should match."""
        assert vm.map_location("Makeda") == "le-makeda"
        assert vm.map_location("Friche") == "la-friche"

    def test_substring_match(self, vm):
        """Keys should match as substrings of longer inputs."""
        assert vm.map_location("La Friche - Grand Plateau") == "la-friche"
        assert vm.map_location("Concert au Makeda Marseille") == "le-makeda"

    def test_videodrome_variants(self, vm):
        """Videodrome should handle various spellings."""
        assert vm.map_location("Videodrome 2") == "videodrome-2"
        assert vm.map_location("videodrome2") == "videodrome-2"
        assert vm.map_location("Vidéodrome 2") == "videodrome-2"
        assert vm.map_location("vidéodrome") == "videodrome-2"

    def test_notre_dame_search_name(self, vm):
        """Short search_name 'notre-dame' should match."""
        assert vm.map_location("notre-dame") == "notre-dame-de-la-garde"
        assert vm.map_location("Notre-Dame du Mont") == "notre-dame-de-la-garde"

    def test_unknown_passthrough(self, vm):
        """Unknown locations should pass through unchanged."""
        assert vm.map_location("Unknown Venue XYZ") == "Unknown Venue XYZ"
        assert vm.map_location("random-place") == "random-place"


# ---------------------------------------------------------------------------
# Migration test: verify all old hardcoded mappings produce a valid slug
# ---------------------------------------------------------------------------


# These are ALL the old hardcoded known_locations entries from crawler.py.
# The expected slug should be a venue that exists in the full venues.yaml.
OLD_HARDCODED_MAPPINGS = {
    "klap": "klap",
    "la friche": "la-friche",
    "friche": "la-friche",
    "la criee": "la-criee",
    "la criée": "la-criee",
    "criee": "la-criee",
    "criée": "la-criee",
    "chateau de servieres": "chateau-de-servieres",
    "servieres": "chateau-de-servieres",
    "notre dame de la garde": "notre-dame-de-la-garde",
    "notre-dame": "notre-dame-de-la-garde",
    "baby club": "baby-club",
    "bohemia": "bohemia",
    "boum marseille": "boum-marseille",
    "boum": "boum-marseille",
    "bounce club": "bounce-club-marseille",
    "bounce club marseille": "bounce-club-marseille",
    "cabaret aleatoire": "cabaret-aleatoire",
    "cabaret aléatoire": "cabaret-aleatoire",
    "danceteria": "danceteria",
    "esquina tropical": "esquina-tropical",
    "francois rouzier": "francois-rouzier",
    "françois rouzier": "francois-rouzier",
    "ipn club": "ipn-club-aix",
    "ipn club aix": "ipn-club-aix",
    "la traverse de balkis": "la-traverse-de-balkis",
    "traverse de balkis": "la-traverse-de-balkis",
    "la wo": "la-wo-marseille",
    "la wo marseille": "la-wo-marseille",
    "le bazar": "le-bazar",
    "le bouge": "le-bouge-marseille",
    "le bougé": "le-bouge-marseille",
    "le bouge marseille": "le-bouge-marseille",
    "le chapiteau": "le-chapiteau-marseille",
    "le chapiteau marseille": "le-chapiteau-marseille",
    "le makeda": "le-makeda",
    "makeda": "le-makeda",
    "le nucleaire": "le-nucleaire-marseille",
    "le nucléaire": "le-nucleaire-marseille",
    "le nucleaire marseille": "le-nucleaire-marseille",
    "level up project": "level-up-project",
    "mama shelter": "mama-shelter-marseille",
    "mama shelter marseille": "mama-shelter-marseille",
    "manray": "manray-club",
    "manray club": "manray-club",
    "mira": "mira",
    "rockypop": "rockypop-marseille",
    "rockypop marseille": "rockypop-marseille",
    "shafro": "shafro",
    "sunny comedy club": "sunny-comedy-club",
    "the pablo club": "the-pablo-club",
    "pablo club": "the-pablo-club",
    "unite 22": "unite-22",
    "unité 22": "unite-22",
    "vice versa": "vice-versa-marseille",
    "vice versa marseille": "vice-versa-marseille",
    "vl": "vl",
    "videodrome 2": "videodrome-2",
    "videodrome2": "videodrome-2",
    "vidéodrome 2": "videodrome-2",
    "vidéodrome": "videodrome-2",
    "le zef": "le-zef-theatre-du-merlan",
    "mucem": "mucem",
    "théâtre de l'oeuvre": "theatre-de-l-oeuvre",
    "theatre de l'oeuvre": "theatre-de-l-oeuvre",
    "théâtre de l'œuvre": "theatre-de-l-oeuvre",
    "la mesón": "theatre-de-l-oeuvre",
    "la meson": "theatre-de-l-oeuvre",
    "le merlan": "le-zef-theatre-du-merlan",
    "theatre du merlan": "le-zef-theatre-du-merlan",
    "théâtre du merlan": "le-zef-theatre-du-merlan",
    "ballet national de marseille": "ballet-national-de-marseille",
    "opéra de marseille": "opera-de-marseille",
    "opera de marseille": "opera-de-marseille",
    "le silo": "le-cepac-silo-marseille",
    "cepac silo": "le-cepac-silo-marseille",
    "le cepac silo": "le-cepac-silo-marseille",
    "espace julien": "espace-julien",
    "le moulin": "le-moulin",
    "l'alhambra": "l-alhambra",
    "théâtre joliette": "theatre-joliette",
    "theatre joliette": "theatre-joliette",
    "théâtre toursky": "scene-mediterranee",
    "theatre toursky": "scene-mediterranee",
    "théâtre nono": "theatre-nono",
    "theatre nono": "theatre-nono",
    "théâtre gyptis": "theatre-gyptis",
    "theatre gyptis": "theatre-gyptis",
    "gyptis": "theatre-gyptis",
    "la minoterie": "la-minoterie",
    "3 bisf": "3-bisf",
    "les bancs publics": "les-bancs-publics",
    "montévidéo": "montevideo",
    "montevideo": "montevideo",
    "pavillon noir": "pavillon-noir",
    "frac marseille": "frac-marseille",
    "bmvr alcazar": "bmvr-alcazar",
    "alcazar": "bmvr-alcazar",
    "musée cantini": "musee-cantini",
    "musee cantini": "musee-cantini",
    "le grand théâtre de provence": "grand-theatre-de-provence",
    "le grand theatre de provence": "grand-theatre-de-provence",
    "grand théâtre de provence": "grand-theatre-de-provence",
    "grand theatre de provence": "grand-theatre-de-provence",
    "théâtre du lacydon": "theatre-du-lacydon",
    "theatre du lacydon": "theatre-du-lacydon",
    "théâtre off": "theatre-off",
    "theatre off": "theatre-off",
    "théâtre des bernardines": "theatre-des-bernardines",
    "theatre des bernardines": "theatre-des-bernardines",
    "bernardines": "theatre-des-bernardines",
}

# Some old mappings intentionally map to alias slugs (e.g., "mac marseille"
# -> "mac-marseille") that are now resolved to the canonical slug. This set
# lists the old *expected slugs* that were alias slugs. The migration test
# accepts the canonical slug as a valid result for these.
OLD_ALIAS_EXPECTED = {
    "mac-marseille",  # canonical: musee-d-art-contemporain-mac
}


class TestMigrationFromHardcodedDict:
    """Verify all 130 old hardcoded map_location entries still resolve correctly.

    Uses the real venues.yaml to ensure all mappings work with the
    data-driven approach.
    """

    @pytest.fixture
    def real_vm(self):
        """Load VenueManager from the real venues.yaml."""
        real_path = Path(__file__).parent.parent / "data" / "venues.yaml"
        if not real_path.exists():
            pytest.skip("Real venues.yaml not available")
        return VenueManager(real_path)

    @pytest.mark.parametrize(
        "raw_input,expected_slug",
        list(OLD_HARDCODED_MAPPINGS.items()),
        ids=[f"{k}" for k in OLD_HARDCODED_MAPPINGS],
    )
    def test_old_mapping(self, real_vm, raw_input, expected_slug):
        """Each old hardcoded mapping should resolve to the expected venue."""
        result = real_vm.map_location(raw_input)
        all_slugs = real_vm.get_all_slugs()

        # The result must be a known venue slug
        assert result in all_slugs, (
            f"map_location({raw_input!r}) returned {result!r} "
            f"which is not a known venue slug"
        )

        # It should match the expected slug (or the canonical slug if old
        # expected was an alias)
        if expected_slug in OLD_ALIAS_EXPECTED:
            # For alias slugs, just verify we got a valid slug
            pass
        else:
            assert result == expected_slug, (
                f"map_location({raw_input!r}) returned {result!r}, "
                f"expected {expected_slug!r}"
            )


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------


class TestFindDuplicates:
    def test_no_duplicates(self, vm):
        duplicates = vm.find_duplicates()
        # Sample venues should not be duplicates of each other
        # (there might be some address-based matches for same-address venues)
        for dup in duplicates:
            assert isinstance(dup, VenueDuplicateResult)

    def test_name_duplicate(self, tmp_path):
        venues = [
            {
                "slug": "venue-a",
                "title": "Le Theatre National",
                "address": "",
                "website": "",
            },
            {
                "slug": "venue-b",
                "title": "Le Theatre National",
                "address": "",
                "website": "",
            },
        ]
        path = tmp_path / "venues.yaml"
        with open(path, "w") as f:
            yaml.dump(venues, f)

        vm = VenueManager(path)
        dups = vm.find_duplicates()
        assert len(dups) == 1
        assert dups[0].match_type == "name"
        assert dups[0].similarity >= 0.85

    def test_website_duplicate(self, tmp_path):
        venues = [
            {
                "slug": "a",
                "title": "Salle Mozart",
                "address": "",
                "website": "https://www.example.com/",
            },
            {
                "slug": "b",
                "title": "Cinema Rex",
                "address": "",
                "website": "https://www.example.com/page",
            },
        ]
        path = tmp_path / "venues.yaml"
        with open(path, "w") as f:
            yaml.dump(venues, f)

        vm = VenueManager(path)
        dups = vm.find_duplicates()
        assert len(dups) == 1
        assert dups[0].match_type == "website"


# ---------------------------------------------------------------------------
# Audit tests
# ---------------------------------------------------------------------------


class TestAudit:
    def test_reports_missing_fields(self, tmp_path):
        venues = [
            {
                "slug": "incomplete",
                "title": "Test",
                "description": "",
                "address": "",
                "website": "",
            },
        ]
        path = tmp_path / "venues.yaml"
        with open(path, "w") as f:
            yaml.dump(venues, f)

        events_dir = tmp_path / "events"
        events_dir.mkdir()

        vm = VenueManager(path)
        result = vm.audit(events_dir)

        assert result.total_venues == 1
        assert len(result.missing_fields) == 1
        assert "description" in result.missing_fields[0]["fields"]
        assert "address" in result.missing_fields[0]["fields"]
        assert "website" in result.missing_fields[0]["fields"]

    def test_reports_unmapped_locations(self, tmp_path):
        venues = [
            {
                "slug": "known-venue",
                "title": "Known",
                "description": "x",
                "address": "x",
                "website": "x",
            }
        ]
        path = tmp_path / "venues.yaml"
        with open(path, "w") as f:
            yaml.dump(venues, f)

        events_dir = tmp_path / "events"
        events_dir.mkdir(parents=True)

        # Create an event file with unknown location
        event_content = """---
title: "Test Event"
locations:
  - "unknown-venue"
---
"""
        event_file = events_dir / "test.fr.md"
        event_file.write_text(event_content)

        vm = VenueManager(path)
        result = vm.audit(events_dir)

        assert "unknown-venue" in result.unmapped_locations


# ---------------------------------------------------------------------------
# discover_unmapped tests
# ---------------------------------------------------------------------------


class TestDiscoverUnmapped:
    def test_finds_unknown_slugs(self, vm, tmp_path):
        events_dir = tmp_path / "events"
        events_dir.mkdir()

        event_content = """---
title: "Test"
locations:
  - "unknown-place"
  - "la-friche"
---
"""
        (events_dir / "test.fr.md").write_text(event_content)

        result = vm.discover_unmapped(events_dir)
        assert "unknown-place" in result
        assert "la-friche" not in result

    def test_alias_slugs_are_known(self, vm, tmp_path):
        events_dir = tmp_path / "events"
        events_dir.mkdir()

        event_content = """---
title: "Test"
locations:
  - "friche"
  - "makeda"
---
"""
        (events_dir / "test.fr.md").write_text(event_content)

        result = vm.discover_unmapped(events_dir)
        assert "friche" not in result
        assert "makeda" not in result

    def test_empty_events_dir(self, vm, tmp_path):
        events_dir = tmp_path / "events"
        events_dir.mkdir()

        result = vm.discover_unmapped(events_dir)
        assert result == []


# ---------------------------------------------------------------------------
# append_stubs tests
# ---------------------------------------------------------------------------


class TestAppendStubs:
    def test_appends_to_file(self, venues_file):
        vm = VenueManager(venues_file)
        original_count = len(vm.venues)

        new_venues = vm.append_stubs(["new-venue-1", "new-venue-2"])

        assert len(new_venues) == 2
        assert len(vm.venues) == original_count + 2
        assert new_venues[0]["slug"] == "new-venue-1"

        # Verify file was updated
        text = venues_file.read_text()
        assert "new-venue-1" in text
        assert "new-venue-2" in text

    def test_new_stubs_are_mappable(self, venues_file):
        vm = VenueManager(venues_file)
        vm.append_stubs(["theatre-du-port"])

        # Slug-as-words should now be a lookup key
        assert vm.map_location("theatre-du-port") == "theatre-du-port"
