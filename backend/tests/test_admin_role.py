"""Roles exist so deployment-wide settings are not writable by anyone who can
sign in. Before this there was no role concept at all.
"""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

from backend.auth.dependency import require_admin
from backend.auth.models import User
from backend.auth.store import UserStore


def _user(role="user"):
    return User(
        id="u1", google_sub="sub-1", email="a@example.com", name="A",
        picture=None, created_at=datetime(2024, 1, 1, tzinfo=timezone.utc), role=role,
    )


def test_users_are_not_admins_by_default():
    assert _user().role == "user"


async def test_require_admin_rejects_a_normal_user():
    with pytest.raises(HTTPException) as exc:
        await require_admin(_user())
    assert exc.value.status_code == 403


async def test_require_admin_allows_an_admin():
    admin = _user(role="admin")
    assert await require_admin(admin) is admin


async def test_login_grants_admin_to_a_configured_email(monkeypatch):
    from backend.configs import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "ADMIN_EMAILS", ["boss@example.com"])
    store = UserStore(AsyncMongoMockClient()["test_db"])

    user = await store.upsert_from_google(
        google_sub="sub-boss", email="boss@example.com", name="Boss", picture=None,
    )
    assert user.role == "admin"


async def test_login_leaves_everyone_else_a_normal_user(monkeypatch):
    from backend.configs import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "ADMIN_EMAILS", ["boss@example.com"])
    store = UserStore(AsyncMongoMockClient()["test_db"])

    user = await store.upsert_from_google(
        google_sub="sub-other", email="someone@example.com", name="Someone", picture=None,
    )
    assert user.role == "user"


async def test_admin_is_revoked_when_the_email_leaves_the_list(monkeypatch):
    """Role is re-derived on every login, so editing the env list is enough --
    no stale admin left behind in the database."""
    from backend.configs import settings as settings_module

    store = UserStore(AsyncMongoMockClient()["test_db"])

    monkeypatch.setattr(settings_module.settings, "ADMIN_EMAILS", ["boss@example.com"])
    first = await store.upsert_from_google(
        google_sub="sub-boss", email="boss@example.com", name="Boss", picture=None,
    )
    assert first.role == "admin"

    monkeypatch.setattr(settings_module.settings, "ADMIN_EMAILS", [])
    second = await store.upsert_from_google(
        google_sub="sub-boss", email="boss@example.com", name="Boss", picture=None,
    )
    assert second.role == "user"
