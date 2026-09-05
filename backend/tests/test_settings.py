from backend.configs.settings import Settings


def test_single_omniroute_api_key_splits_on_comma():
    s = Settings(OMNIROUTE_API_KEY="key-a,key-b")
    assert s.OMNIROUTE_API_KEYS == ["key-a", "key-b"]


def test_explicit_omniroute_api_keys_list_takes_precedence():
    s = Settings(OMNIROUTE_API_KEY="ignored", OMNIROUTE_API_KEYS=["real-key"])
    assert s.OMNIROUTE_API_KEYS == ["real-key"]


def test_no_keys_configured_returns_empty_list():
    s = Settings(OMNIROUTE_API_KEY=None, OMNIROUTE_API_KEYS=[])
    assert s.OMNIROUTE_API_KEYS == []
