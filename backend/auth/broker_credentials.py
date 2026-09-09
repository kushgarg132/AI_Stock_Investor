"""Per-user broker API credentials (collection `broker_credentials`).

Credentials used to be a single KITE_API_KEY/KITE_API_SECRET pair in the
process environment, which meant every signed-in user shared one broker
account -- and any of them could overwrite it for everyone through the
settings API. They now belong to a user, encrypted at rest so a database dump
does not hand over broker access.

The encryption key lives in CREDENTIAL_ENCRYPTION_KEY (a Fernet key). When it
is absent this store refuses to save rather than quietly writing plaintext
secrets: a deployment missing its key should fail loudly at the first save,
not leak.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import Fernet


class CredentialEncryptionUnavailable(RuntimeError):
    """No CREDENTIAL_ENCRYPTION_KEY configured, so nothing may be stored."""


@dataclass(frozen=True)
class BrokerCredentials:
    api_key: str
    api_secret: str
    # Not every broker needs one -- Upstox's OAuth flow requires a
    # registered redirect_uri alongside the client id/secret; Kite doesn't
    # use one at all. Encrypted alongside the rest for simplicity even where
    # it isn't itself secret.
    extra: Optional[str] = None


def fernet_from_settings() -> Optional[Fernet]:
    from backend.configs.settings import settings

    key = settings.CREDENTIAL_ENCRYPTION_KEY
    return Fernet(key) if key else None


def get_credential_store() -> "BrokerCredentialStore":
    """FastAPI dependency. Lives here rather than in a router so every router
    that needs credentials resolves the same one."""
    from backend.database import db

    return BrokerCredentialStore(db.db, fernet_from_settings())


def _mask(api_key: str) -> str:
    """Enough to recognise which key is stored, never enough to use it."""
    tail = api_key[-4:] if len(api_key) >= 4 else api_key
    return f"{'•' * 6}{tail}"


class BrokerCredentialStore:
    def __init__(self, db, fernet: Optional[Fernet]) -> None:
        self._db = db
        self._fernet = fernet

    @property
    def collection(self):
        return self._db["broker_credentials"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("user_id", 1), ("broker", 1)], unique=True)

    async def save(
        self, user_id: str, broker: str, api_key: str, api_secret: str, extra: Optional[str] = None,
    ) -> None:
        if self._fernet is None:
            raise CredentialEncryptionUnavailable(
                "CREDENTIAL_ENCRYPTION_KEY is not configured; refusing to store credentials"
            )

        fields = {
            "user_id": user_id,
            "broker": broker,
            "api_key_enc": self._fernet.encrypt(api_key.encode()).decode(),
            "api_secret_enc": self._fernet.encrypt(api_secret.encode()).decode(),
            "api_key_masked": _mask(api_key),
            "updated_at": datetime.now(timezone.utc),
        }
        if extra is not None:
            fields["extra_enc"] = self._fernet.encrypt(extra.encode()).decode()

        await self.collection.update_one(
            {"user_id": user_id, "broker": broker}, {"$set": fields}, upsert=True,
        )

    async def get(self, user_id: str, broker: str) -> Optional[BrokerCredentials]:
        doc = await self.collection.find_one({"user_id": user_id, "broker": broker})
        if doc is None:
            return None
        if self._fernet is None:
            raise CredentialEncryptionUnavailable(
                "CREDENTIAL_ENCRYPTION_KEY is not configured; stored credentials cannot be read"
            )
        extra_enc = doc.get("extra_enc")
        return BrokerCredentials(
            api_key=self._fernet.decrypt(doc["api_key_enc"].encode()).decode(),
            api_secret=self._fernet.decrypt(doc["api_secret_enc"].encode()).decode(),
            extra=self._fernet.decrypt(extra_enc.encode()).decode() if extra_enc else None,
        )

    async def status(self, user_id: str, broker: str) -> dict:
        doc = await self.collection.find_one({"user_id": user_id, "broker": broker})
        if doc is None:
            return {"configured": False, "api_key_masked": None}
        return {"configured": True, "api_key_masked": doc.get("api_key_masked")}

    async def delete(self, user_id: str, broker: str) -> None:
        await self.collection.delete_one({"user_id": user_id, "broker": broker})
