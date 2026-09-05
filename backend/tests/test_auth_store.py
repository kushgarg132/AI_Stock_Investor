import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.auth.store import UserStore


@pytest.fixture
def store():
    client = AsyncMongoMockClient()
    return UserStore(client["test_db"])


def test_upsert_from_google_creates_new_user(store):
    user = asyncio.run(store.upsert_from_google(
        google_sub="google-sub-123", email="a@example.com", name="Alice", picture="http://pic",
    ))
    assert user.google_sub == "google-sub-123"
    assert user.email == "a@example.com"
    assert user.name == "Alice"
    assert user.picture == "http://pic"
    assert user.id  # a fresh id was assigned


def test_upsert_from_google_is_idempotent_by_google_sub(store):
    first = asyncio.run(store.upsert_from_google(
        google_sub="google-sub-123", email="a@example.com", name="Alice", picture=None,
    ))
    second = asyncio.run(store.upsert_from_google(
        google_sub="google-sub-123", email="a@example.com", name="Alice Updated", picture=None,
    ))
    assert first.id == second.id
    assert second.name == "Alice Updated"


def test_get_by_id_returns_none_for_unknown_user(store):
    result = asyncio.run(store.get_by_id("no-such-id"))
    assert result is None


def test_get_by_id_returns_the_stored_user(store):
    created = asyncio.run(store.upsert_from_google(
        google_sub="google-sub-456", email="b@example.com", name="Bob", picture=None,
    ))
    fetched = asyncio.run(store.get_by_id(created.id))
    assert fetched is not None
    assert fetched.email == "b@example.com"
