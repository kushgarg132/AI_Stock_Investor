"""logo_url must never point at logo.clearbit.com again -- that free API is
dead (DNS doesn't resolve at all), which is what made every stock's logo
render as a broken image."""

from backend.components.master.stock_info import _favicon_url


def test_favicon_url_never_uses_the_dead_clearbit_host():
    assert "clearbit" not in _favicon_url("https://www.tcs.com/about")
    assert "clearbit" not in _favicon_url("reliance.com")


def test_favicon_url_strips_scheme_and_www_from_a_website():
    assert _favicon_url("https://www.tcs.com/investors") == (
        "https://www.google.com/s2/favicons?sz=128&domain=tcs.com"
    )


def test_favicon_url_accepts_a_bare_guessed_domain():
    assert _favicon_url("reliance.com") == (
        "https://www.google.com/s2/favicons?sz=128&domain=reliance.com"
    )
