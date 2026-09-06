"""Long-lived refresh tokens (collection `refresh_tokens`).

A refresh token is a random opaque value handed to the browser only inside
an httpOnly cookie -- JavaScript never sees it, so an XSS bug that steals
localStorage steals the short-lived access token, never this. Only its
SHA-256 hash is ever written to Mongo; a database read can never hand back
something usable as a credential.

Every use rotates: `rotate()` kills the presented token and issues a new one
in the same call. Presenting a token that has already been rotated away is
what a stolen-and-replayed (or duplicated) token looks like -- an honest
client already moved on to the newer one -- so that case revokes every
token this user has, not just the one presented. A token someone logged out
of deliberately (`revoke()`) is not that signal -- it's expected to be dead,
and a sibling session (another device, another tab) must survive it -- so
the two death reasons are tracked separately (`rotated` vs a plain
`revoked_at`) rather than being indistinguishable once a token is inactive.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.configs.settings import settings


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _as_utc(value: datetime) -> datetime:
    """Mongo (and mongomock) hand datetimes back naive-as-UTC; give them a
    zone before comparing against an aware `now`."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class RefreshTokenStore:
    def __init__(self, db) -> None:
        # Deferred, matching UserStore: FastAPI constructs every route
        # dependency before the route body runs, including on a request
        # that fails before ever needing this store (e.g. /auth/google with
        # an invalid Google token) -- eager access would crash on whatever
        # `db` is at that point instead of letting the real failure surface.
        self._db = db

    @property
    def collection(self):
        return self._db["refresh_tokens"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("token_hash", unique=True)
        await self.collection.create_index([("user_id", 1), ("revoked_at", 1)])
        # TTL index: Mongo reaps rows itself well after expiry, so a flood of
        # abandoned tokens (browsers that never come back) doesn't accumulate
        # forever. The app's own expiry check below still runs on every
        # lookup and does not depend on this cleanup having happened yet.
        await self.collection.create_index("expires_at", expireAfterSeconds=0)

    async def issue(self, user_id: str, now: Optional[datetime] = None) -> str:
        now = now or datetime.now(timezone.utc)
        raw = secrets.token_urlsafe(32)
        await self.collection.insert_one({
            "token_hash": _hash(raw),
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + timedelta(seconds=settings.REFRESH_TOKEN_MAX_AGE_SECONDS),
            "revoked_at": None,
            "rotated": False,
        })
        return raw

    async def rotate(
        self, raw_token: str, now: Optional[datetime] = None
    ) -> Optional[tuple[str, str]]:
        now = now or datetime.now(timezone.utc)
        doc = await self.collection.find_one({"token_hash": _hash(raw_token)})
        if doc is None:
            return None

        if doc["revoked_at"] is not None:
            if doc["rotated"]:
                # This exact token already produced its successor once --
                # presenting it again is a replay, not a logged-out client
                # retrying. A token someone deliberately logged out of
                # (revoked but not rotated) is expected to be dead and must
                # not take a sibling session down with it.
                await self.revoke_all(doc["user_id"])
            return None

        if _as_utc(doc["expires_at"]) <= now:
            return None

        new_raw = await self.issue(doc["user_id"], now=now)
        await self.collection.update_one(
            {"_id": doc["_id"]}, {"$set": {"revoked_at": now, "rotated": True}}
        )
        return doc["user_id"], new_raw

    async def revoke(self, raw_token: str) -> None:
        await self.collection.update_one(
            {"token_hash": _hash(raw_token), "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc)}},
        )

    async def revoke_all(self, user_id: str) -> None:
        await self.collection.update_many(
            {"user_id": user_id, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc)}},
        )
