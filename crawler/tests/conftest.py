"""Shared pytest fixtures."""

from datetime import datetime

import pytest


def _frozen_datetime_class(frozen: datetime) -> type[datetime]:
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return frozen.astimezone(tz)
            return frozen.replace(tzinfo=None)

    return FrozenDatetime


@pytest.fixture
def freeze_time(monkeypatch):
    """Return a callable that freezes datetime.now() in the given modules.

    Parser test fixtures embed absolute event dates, and parsers drop
    events in the past. Freezing 'now' at the date the fixtures were
    written keeps the tests deterministic.

    Usage:
        freeze_time("2026-02-04T12:00:00+01:00", "src.parsers.videodrome2")
    """

    def _freeze(frozen_iso: str, *modules: str) -> None:
        frozen = datetime.fromisoformat(frozen_iso)
        frozen_cls = _frozen_datetime_class(frozen)
        for module in modules:
            monkeypatch.setattr(f"{module}.datetime", frozen_cls)

    return _freeze
