from __future__ import annotations

from app.config.policy import LANGUAGE_CATALOG, SUPPORTED_LANGUAGES


def test_serbian_in_supported_languages() -> None:
    assert "sr" in SUPPORTED_LANGUAGES


def test_language_catalog_matches_supported_set() -> None:
    catalog_codes = {entry["code"] for entry in LANGUAGE_CATALOG}
    assert catalog_codes == SUPPORTED_LANGUAGES


def test_serbian_catalog_entry() -> None:
    sr = next(e for e in LANGUAGE_CATALOG if e["code"] == "sr")
    assert sr["name"] == "Serbian"
    assert sr["tier"] == "standard"
