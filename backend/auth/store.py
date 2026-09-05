import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.auth.models import User


def _to_user(doc: dict) -> User:
    doc = dict(doc)
    doc.pop("_id", None)
    return User(**doc)


class UserStore:
    """Mongo-backed user store. Collection `users`, unique index on
    google_sub. This is the one and only place a User document is ever
    created in this app -- there is no separate password-registration
    path to keep in sync (unlike RoutineOS, which has both and once let a
    field drift between them). If a second account-creation path is ever
    added, audit its field set against upsert_from_google explicitly."""

    def __init__(self, db):
        # Deferred: db["users"] isn't accessed until a method actually
        # needs it. FastAPI resolves every Depends() in a route's
        # signature before the route body runs, so constructing a
        # UserStore happens even on requests that will fail before ever
        # using the store (e.g. an invalid Google token) -- eager access
        # here would crash on an unconnected db in that case.
        self._db = db

    @property
    def collection(self):
        return self._db["users"]

    async def ensure_indexes(self):
        await self.collection.create_index("google_sub", unique=True)

    async def upsert_from_google(
        self, google_sub: str, email: str, name: str, picture: Optional[str]
    ) -> User:
        existing = await self.collection.find_one({"google_sub": google_sub})
        if existing is not None:
            await self.collection.update_one(
                {"google_sub": google_sub},
                {"$set": {"email": email, "name": name, "picture": picture}},
            )
            existing.update({"email": email, "name": name, "picture": picture})
            return _to_user(existing)

        user = User(
            id=str(uuid.uuid4()),
            google_sub=google_sub,
            email=email,
            name=name,
            picture=picture,
            created_at=datetime.now(timezone.utc),
        )
        await self.collection.insert_one(user.model_dump())
        return user

    async def get_by_id(self, user_id: str) -> Optional[User]:
        doc = await self.collection.find_one({"id": user_id})
        return _to_user(doc) if doc else None
