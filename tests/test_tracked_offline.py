# Офлайн-тесты TrackedGroupsStore: то, что проверяется до обращения к БД.

from __future__ import annotations

import pytest

from mospolytech_mcp.tracked import TrackedGroupsStore, UnknownGroupError


def _no_db():
    raise AssertionError("до БД дойти не должны")


async def _known():
    return ["241-327", "221-111"]


async def test_add_rejects_unknown_group():
    store = TrackedGroupsStore(_no_db, _known)
    with pytest.raises(UnknownGroupError, match="999-999"):
        await store.add("r.v.starkov", "999-999")


async def test_add_rejects_unknown_group_after_strip():
    store = TrackedGroupsStore(_no_db, _known)
    with pytest.raises(UnknownGroupError):
        await store.add("r.v.starkov", " 241-328 ")
