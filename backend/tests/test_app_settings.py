"""Deployment-wide settings in Mongo, replacing the .env rewriting.

The model choice has to reach the running LLM without a restart -- that was
the one thing the old .env-mutating endpoint got right, and dropping it would
be a regression.
"""

from mongomock_motor import AsyncMongoMockClient

from backend import app_settings as app_settings_module
from backend.app_settings import AppSettingsStore, current_llm_model


def _store():
    return AppSettingsStore(AsyncMongoMockClient()["test_db"])


async def test_model_starts_unset():
    assert await _store().get_llm_model() is None


async def test_setting_the_model_persists_it():
    store = _store()
    await store.set_llm_model("aug/sonnet5-high")
    assert await store.get_llm_model() == "aug/sonnet5-high"


async def test_setting_the_model_replaces_rather_than_accumulates():
    store = _store()
    await store.set_llm_model("first")
    await store.set_llm_model("second")

    assert await store.get_llm_model() == "second"
    assert await store.collection.count_documents({}) == 1


def test_current_model_falls_back_to_the_configured_default(monkeypatch):
    from backend.configs import settings as settings_module

    monkeypatch.setattr(app_settings_module, "_cached_llm_model", None)
    monkeypatch.setattr(settings_module.settings, "OMNIROUTE_MODEL", "env/default-model")

    assert current_llm_model() == "env/default-model"


async def test_saving_a_model_takes_effect_without_a_restart(monkeypatch):
    """get_llm() is sync and called per request, so the stored value is cached
    in the process rather than read from Mongo on every call."""
    monkeypatch.setattr(app_settings_module, "_cached_llm_model", None)
    store = _store()

    await store.set_llm_model("aug/sonnet5-high")

    assert current_llm_model() == "aug/sonnet5-high"


async def test_the_stored_model_is_loaded_at_startup(monkeypatch):
    monkeypatch.setattr(app_settings_module, "_cached_llm_model", None)
    store = _store()
    await store.collection.update_one(
        {"_id": "singleton"}, {"$set": {"llm_model": "persisted/model"}}, upsert=True
    )

    await store.load_into_cache()

    assert current_llm_model() == "persisted/model"
