"""Per-user broker credentials: the store that replaces one shared key pair
in .env. Every test here is a tenancy or secrecy property -- if one of these
fails, one user can reach another user's broker account.
"""

import pytest
from cryptography.fernet import Fernet
from mongomock_motor import AsyncMongoMockClient

from backend.auth.broker_credentials import (
    BrokerCredentialStore,
    CredentialEncryptionUnavailable,
)


def _store(fernet=None):
    client = AsyncMongoMockClient()
    return BrokerCredentialStore(client["test_db"], fernet or Fernet(Fernet.generate_key()))


async def test_saved_credentials_round_trip_for_their_owner():
    store = _store()
    await store.save("alice", "kite", api_key="ak-alice", api_secret="as-alice")

    creds = await store.get("alice", "kite")
    assert creds is not None
    assert creds.api_key == "ak-alice"
    assert creds.api_secret == "as-alice"


async def test_one_users_credentials_are_invisible_to_another():
    store = _store()
    await store.save("alice", "kite", api_key="ak-alice", api_secret="as-alice")

    assert await store.get("bob", "kite") is None


async def test_saving_for_one_user_does_not_disturb_another():
    store = _store()
    await store.save("alice", "kite", api_key="ak-alice", api_secret="as-alice")
    await store.save("bob", "kite", api_key="ak-bob", api_secret="as-bob")

    alice = await store.get("alice", "kite")
    bob = await store.get("bob", "kite")
    assert alice.api_secret == "as-alice"
    assert bob.api_secret == "as-bob"


async def test_credentials_are_encrypted_at_rest():
    """A database dump must not hand over broker access."""
    store = _store()
    await store.save("alice", "kite", api_key="ak-alice", api_secret="as-alice")

    raw = await store.collection.find_one({"user_id": "alice", "broker": "kite"})
    assert "as-alice" not in str(raw)
    assert "ak-alice" not in str(raw)


async def test_a_different_key_cannot_decrypt_stored_credentials():
    written = _store(Fernet(Fernet.generate_key()))
    await written.save("alice", "kite", api_key="ak-alice", api_secret="as-alice")

    attacker = BrokerCredentialStore(written.collection.database, Fernet(Fernet.generate_key()))
    with pytest.raises(Exception):
        await attacker.get("alice", "kite")


async def test_saving_without_an_encryption_key_is_refused():
    """Refusing beats silently writing plaintext secrets to the database."""
    store = BrokerCredentialStore(AsyncMongoMockClient()["test_db"], None)

    with pytest.raises(CredentialEncryptionUnavailable):
        await store.save("alice", "kite", api_key="ak", api_secret="as")


async def test_status_reports_configured_without_revealing_the_secret():
    store = _store()
    await store.save("alice", "kite", api_key="abcd1234wxyz", api_secret="as-alice")

    status = await store.status("alice", "kite")
    assert status["configured"] is True
    assert "as-alice" not in str(status)
    assert status["api_key_masked"].endswith("wxyz")
    assert "abcd1234wxyz" != status["api_key_masked"]


async def test_status_for_a_user_with_no_credentials():
    status = await _store().status("nobody", "kite")
    assert status == {"configured": False, "api_key_masked": None}


async def test_delete_removes_only_that_users_credentials():
    store = _store()
    await store.save("alice", "kite", api_key="ak-alice", api_secret="as-alice")
    await store.save("bob", "kite", api_key="ak-bob", api_secret="as-bob")

    await store.delete("alice", "kite")

    assert await store.get("alice", "kite") is None
    assert (await store.get("bob", "kite")).api_secret == "as-bob"


async def test_resaving_replaces_rather_than_duplicates():
    store = _store()
    await store.save("alice", "kite", api_key="old", api_secret="old-secret")
    await store.save("alice", "kite", api_key="new", api_secret="new-secret")

    assert (await store.get("alice", "kite")).api_secret == "new-secret"
    assert await store.collection.count_documents({"user_id": "alice", "broker": "kite"}) == 1
