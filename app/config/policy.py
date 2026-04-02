"""Translation configuration policy.

Defines supported languages, validation rules, credit cost estimation,
language pair tiers, and source language confidence thresholds.

All constants are module-level so they can be overridden in tests
via monkeypatching without modifying production paths.

Credit multipliers are intentionally kept simple for MVP. They are
documented here as the place to tune once benchmark data exists.
"""
from __future__ import annotations

import math
import os
from decimal import Decimal
from typing import FrozenSet, Optional

# ── Supported languages ───────────────────────────────────────────────────────

SUPPORTED_LANGUAGES: FrozenSet[str] = frozenset(
    {
        "en",  # English
        "ru",  # Russian
        "sr",  # Serbian
        "de",  # German
        "fr",  # French
        "es",  # Spanish
        "it",  # Italian
        "pt",  # Portuguese
        "zh",  # Chinese (Simplified)
        "ja",  # Japanese
        "ko",  # Korean
        "tr",  # Turkish
        "nl",  # Dutch
        "pl",  # Polish
    }
)

# Canonical display metadata; every ``code`` must appear in ``SUPPORTED_LANGUAGES``.
LANGUAGE_CATALOG: tuple[dict[str, str], ...] = (
    {"code": "de", "name": "German",               "tier": "standard"},
    {"code": "en", "name": "English",               "tier": "standard"},
    {"code": "es", "name": "Spanish",               "tier": "standard"},
    {"code": "fr", "name": "French",                "tier": "standard"},
    {"code": "it", "name": "Italian",               "tier": "standard"},
    {"code": "ja", "name": "Japanese",              "tier": "standard"},
    {"code": "ko", "name": "Korean",                "tier": "standard"},
    {"code": "nl", "name": "Dutch",                 "tier": "standard"},
    {"code": "pl", "name": "Polish",                "tier": "standard"},
    {"code": "pt", "name": "Portuguese",            "tier": "standard"},
    {"code": "ru", "name": "Russian",               "tier": "standard"},
    {"code": "sr", "name": "Serbian",               "tier": "standard"},
    {"code": "tr", "name": "Turkish",               "tier": "standard"},
    {"code": "zh", "name": "Chinese (Simplified)",  "tier": "standard"},
)


# ── Valid config values ───────────────────────────────────────────────────────

VALID_MODES: FrozenSet[str] = frozenset({"translate", "guided"})
VALID_STYLES: FrozenSet[str] = frozenset({"literal", "natural"})
VALID_LEVELS: FrozenSet[str] = frozenset({"A1", "A2", "B1", "B2", "C1"})
VALID_DEPTHS: FrozenSet[str] = frozenset({"minimal", "standard", "detailed"})

# ── Quality tiers ─────────────────────────────────────────────────────────────
#
# Each tier maps to a distinct Claude model and a credit cost multiplier.
# Model slugs are overridable via environment variables per DEC-003.
# Multipliers reflect the approximate cost ratio between models.

VALID_QUALITY_TIERS: FrozenSet[str] = frozenset({"express", "standard", "premium"})

TIER_CREDIT_MULTIPLIERS: dict[str, Decimal] = {
    "express":  Decimal("0.5"),
    "standard": Decimal("1.0"),
    "premium":  Decimal("2.5"),
}

TIER_MODELS: dict[str, str] = {
    "express":  os.getenv("TRANSLATION_MODEL_EXPRESS",  "claude-haiku-4-5-20251001"),
    "standard": os.getenv("TRANSLATION_MODEL_STANDARD", "claude-sonnet-4-6"),
    "premium":  os.getenv("TRANSLATION_MODEL_PREMIUM",  "claude-opus-4-6"),
}


def get_tier_model(quality_tier: str) -> str:
    """Return the Claude model slug for a quality tier.

    Falls back to the TRANSLATION_MODEL env var (then the haiku default) for
    unknown tier values so that legacy jobs without a tier set still work.
    """
    return TIER_MODELS.get(
        quality_tier,
        os.getenv("TRANSLATION_MODEL", "claude-haiku-4-5-20251001"),
    )


# ── Language pair tiers ───────────────────────────────────────────────────────
#
# Configuration-driven. Pairs not listed here are "standard".
# Promote pairs to "experimental" once benchmark data identifies quality gaps.
# Format: frozenset of (source_language, target_language) tuples.

_EXPERIMENTAL_PAIRS: FrozenSet[tuple] = frozenset()


def get_language_pair_tier(source_language: str, target_language: str) -> str:
    """Return 'standard' or 'experimental' for a language pair."""
    if (source_language, target_language) in _EXPERIMENTAL_PAIRS:
        return "experimental"
    return "standard"


# ── Credit cost estimation ────────────────────────────────────────────────────
#
# Formula: ceil(word_count / WORDS_PER_CREDIT) × mode_multiplier × depth_multiplier × tier_multiplier
# These multipliers are the correct place to tune when pricing is finalised.

WORDS_PER_CREDIT: int = 100

MODE_MULTIPLIERS: dict = {
    "translate": 1.0,
    "guided": 1.5,
}

# Explanation depth multiplier applies only to Guided Mode.
EXPLANATION_DEPTH_MULTIPLIERS: dict = {
    "minimal": 1.0,
    "standard": 1.2,
    "detailed": 1.5,
}


def estimate_credits(
    word_count: int,
    mode: str,
    explanation_depth: str = "standard",
    quality_tier: str = "standard",
) -> int:
    """Return the estimated credit cost for a job configuration.

    Minimum 1 credit. Explanation depth only applies in Guided Mode.
    quality_tier applies a multiplier per TIER_CREDIT_MULTIPLIERS.
    """
    base = max(1, math.ceil(word_count / WORDS_PER_CREDIT))
    mode_mult = MODE_MULTIPLIERS.get(mode, 1.0)
    depth_mult = (
        EXPLANATION_DEPTH_MULTIPLIERS.get(explanation_depth, 1.2)
        if mode == "guided"
        else 1.0
    )
    tier_mult = float(TIER_CREDIT_MULTIPLIERS.get(quality_tier, Decimal("1.0")))
    return max(1, math.ceil(base * mode_mult * depth_mult * tier_mult))


# ── Source language confidence ────────────────────────────────────────────────
#
# Per §Source Language Confidence Policy:
#   high   (≥ 0.85) → auto-fill; no user action required
#   medium (≥ 0.60) → show a warning; user can confirm
#   low    (< 0.60) → require explicit user confirmation

CONFIDENCE_HIGH: float = 0.85
CONFIDENCE_MEDIUM: float = 0.60


def get_confidence_label(confidence: float) -> str:
    """Return 'high', 'medium', or 'low' for a language detection confidence."""
    if confidence >= CONFIDENCE_HIGH:
        return "high"
    if confidence >= CONFIDENCE_MEDIUM:
        return "medium"
    return "low"


# ── Config validation ─────────────────────────────────────────────────────────


class ConfigValidationError(Exception):
    """Raised when job configuration fails policy validation.

    `errors` contains one entry per violation for structured client display.
    """

    def __init__(self, errors: list) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def validate_job_config(
    mode: str,
    target_language: str,
    translation_style: str,
    user_level: str,
    explanation_depth: str,
    source_language: Optional[str] = None,
    quality_tier: Optional[str] = None,
) -> None:
    """Validate all job configuration parameters against policy.

    Collects all violations before raising so the client receives the full
    list in one response rather than one error per round-trip.

    Raises:
        ConfigValidationError: one or more policy violations found.
    """
    errors: list = []

    if mode not in VALID_MODES:
        errors.append(
            f"Invalid mode '{mode}'. Allowed: {', '.join(sorted(VALID_MODES))}."
        )

    if target_language not in SUPPORTED_LANGUAGES:
        errors.append(
            f"Unsupported target language '{target_language}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_LANGUAGES))}."
        )

    if source_language is not None:
        if source_language not in SUPPORTED_LANGUAGES:
            errors.append(
                f"Unsupported source language '{source_language}'."
            )
        elif source_language == target_language:
            errors.append("Source and target languages must be different.")

    if translation_style not in VALID_STYLES:
        errors.append(
            f"Invalid translation_style '{translation_style}'. "
            f"Allowed: {', '.join(sorted(VALID_STYLES))}."
        )

    if user_level not in VALID_LEVELS:
        errors.append(
            f"Invalid user_level '{user_level}'. "
            f"Allowed: {', '.join(sorted(VALID_LEVELS))}."
        )

    # explanation_depth is only validated for Guided Mode;
    # for Translate Mode it is accepted but ignored.
    if mode == "guided" and explanation_depth not in VALID_DEPTHS:
        errors.append(
            f"Invalid explanation_depth '{explanation_depth}'. "
            f"Allowed: {', '.join(sorted(VALID_DEPTHS))}."
        )

    if quality_tier is not None and quality_tier not in VALID_QUALITY_TIERS:
        errors.append(
            f"Invalid quality_tier '{quality_tier}'. "
            f"Allowed: {', '.join(sorted(VALID_QUALITY_TIERS))}."
        )

    if errors:
        raise ConfigValidationError(errors)


# ── Initial credit grant ──────────────────────────────────────────────────────
#
# This default is intentionally 0. The actual initial grant is stored in
# the app_settings table and managed via the admin panel.

def _initial_credit_grant() -> int:
    value = os.getenv("INITIAL_CREDIT_GRANT", "0")
    try:
        return int(value)
    except ValueError:
        return 0
