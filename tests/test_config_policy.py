"""Unit tests for the translation configuration policy module."""
from __future__ import annotations

import math

import pytest

from app.config.policy import (
    SUPPORTED_LANGUAGES,
    ConfigValidationError,
    estimate_credits,
    get_confidence_label,
    get_language_pair_tier,
    validate_job_config,
)


# ── estimate_credits ──────────────────────────────────────────────────────────

def test_estimate_credits_translate_basic() -> None:
    # 1000 words / 100 = 10 base, mode=translate (1.0x) = 10
    assert estimate_credits(1000, "translate") == 10


def test_estimate_credits_guided_standard() -> None:
    # 1000 / 100 = 10, guided (1.5x) * standard (1.2x) = 10 * 1.5 * 1.2 = 18
    assert estimate_credits(1000, "guided", "standard") == 18


def test_estimate_credits_guided_detailed() -> None:
    # 1000 / 100 = 10, guided (1.5x) * detailed (1.5x) = 22.5 → ceil = 23
    assert estimate_credits(1000, "guided", "detailed") == 23


def test_estimate_credits_guided_minimal() -> None:
    # 1000 / 100 = 10, guided (1.5x) * minimal (1.0x) = 15
    assert estimate_credits(1000, "guided", "minimal") == 15


def test_estimate_credits_translate_ignores_depth() -> None:
    # Depth multiplier does not apply to translate mode
    assert estimate_credits(1000, "translate", "detailed") == estimate_credits(
        1000, "translate", "minimal"
    )


def test_estimate_credits_minimum_one() -> None:
    assert estimate_credits(0, "translate") == 1
    assert estimate_credits(1, "guided") == 2  # ceil(1 * 1.5 * 1.2)


def test_estimate_credits_large_book() -> None:
    # 100 000 words, guided, detailed: ceil(100000/100 * 1.5 * 1.5) = ceil(2250) = 2250
    assert estimate_credits(100_000, "guided", "detailed") == 2250


# ── get_confidence_label ──────────────────────────────────────────────────────

def test_confidence_high() -> None:
    assert get_confidence_label(0.92) == "high"
    assert get_confidence_label(0.85) == "high"


def test_confidence_medium() -> None:
    assert get_confidence_label(0.75) == "medium"
    assert get_confidence_label(0.60) == "medium"


def test_confidence_low() -> None:
    assert get_confidence_label(0.59) == "low"
    assert get_confidence_label(0.0) == "low"


# ── get_language_pair_tier ────────────────────────────────────────────────────

def test_standard_tier_default() -> None:
    assert get_language_pair_tier("en", "ru") == "standard"
    assert get_language_pair_tier("ja", "de") == "standard"


def test_all_mvp_pairs_are_standard() -> None:
    for src in SUPPORTED_LANGUAGES:
        for tgt in SUPPORTED_LANGUAGES:
            if src != tgt:
                assert get_language_pair_tier(src, tgt) == "standard"


# ── validate_job_config ───────────────────────────────────────────────────────

def test_valid_config_passes() -> None:
    # Should not raise
    validate_job_config(
        mode="translate",
        target_language="en",
        translation_style="natural",
        user_level="B1",
        explanation_depth="standard",
        source_language="ru",
    )


def test_valid_guided_config_passes() -> None:
    validate_job_config(
        mode="guided",
        target_language="de",
        translation_style="literal",
        user_level="A2",
        explanation_depth="detailed",
        source_language="fr",
    )


def test_invalid_mode_raises() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_job_config(
            mode="magic",
            target_language="en",
            translation_style="natural",
            user_level="B1",
            explanation_depth="standard",
        )
    assert any("mode" in e.lower() for e in exc_info.value.errors)


def test_unsupported_target_language_raises() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_job_config(
            mode="translate",
            target_language="xx",
            translation_style="natural",
            user_level="B1",
            explanation_depth="standard",
        )
    assert any("target language" in e.lower() for e in exc_info.value.errors)


def test_unsupported_source_language_raises() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_job_config(
            mode="translate",
            target_language="en",
            translation_style="natural",
            user_level="B1",
            explanation_depth="standard",
            source_language="xx",
        )
    assert any("source language" in e.lower() for e in exc_info.value.errors)


def test_same_source_and_target_raises() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_job_config(
            mode="translate",
            target_language="en",
            translation_style="natural",
            user_level="B1",
            explanation_depth="standard",
            source_language="en",
        )
    assert any("differ" in e.lower() for e in exc_info.value.errors)


def test_invalid_style_raises() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_job_config(
            mode="translate",
            target_language="en",
            translation_style="poetic",
            user_level="B1",
            explanation_depth="standard",
        )
    assert any("translation_style" in e.lower() for e in exc_info.value.errors)


def test_invalid_user_level_raises() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_job_config(
            mode="translate",
            target_language="en",
            translation_style="natural",
            user_level="D1",
            explanation_depth="standard",
        )
    assert any("user_level" in e.lower() for e in exc_info.value.errors)


def test_invalid_depth_in_guided_raises() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_job_config(
            mode="guided",
            target_language="en",
            translation_style="natural",
            user_level="B1",
            explanation_depth="extreme",
        )
    assert any("explanation_depth" in e.lower() for e in exc_info.value.errors)


def test_invalid_depth_in_translate_is_ignored() -> None:
    # explanation_depth is not validated for translate mode
    validate_job_config(
        mode="translate",
        target_language="en",
        translation_style="natural",
        user_level="B1",
        explanation_depth="extreme",  # not validated for translate
    )


def test_multiple_errors_collected() -> None:
    """All violations are collected and returned in one raise."""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_job_config(
            mode="bad_mode",
            target_language="xx",
            translation_style="bad_style",
            user_level="Z9",
            explanation_depth="standard",
        )
    assert len(exc_info.value.errors) >= 3


# ── LANGUAGE_CATALOG / Serbian ─────────────────────────────────────────────

def test_language_catalog_exported() -> None:
    from app.config.policy import LANGUAGE_CATALOG
    assert len(LANGUAGE_CATALOG) > 0


def test_language_catalog_codes_match_supported_languages() -> None:
    from app.config.policy import LANGUAGE_CATALOG
    catalog_codes = {entry["code"] for entry in LANGUAGE_CATALOG}
    assert catalog_codes == SUPPORTED_LANGUAGES


def test_serbian_in_supported_languages() -> None:
    assert "sr" in SUPPORTED_LANGUAGES


def test_serbian_catalog_entry() -> None:
    from app.config.policy import LANGUAGE_CATALOG
    sr = next((e for e in LANGUAGE_CATALOG if e["code"] == "sr"), None)
    assert sr is not None
    assert sr["name"] == "Serbian"
    assert sr["tier"] == "standard"


def test_catalog_codes_not_in_unsupported_set() -> None:
    """cs and ar were removed from the dropdown; they must not be in the backend set."""
    from app.config.policy import LANGUAGE_CATALOG
    catalog_codes = {entry["code"] for entry in LANGUAGE_CATALOG}
    assert "cs" not in catalog_codes
    assert "ar" not in catalog_codes
