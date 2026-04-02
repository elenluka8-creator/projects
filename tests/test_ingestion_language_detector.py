"""Tests for the language detector."""
from __future__ import annotations

import pytest

from app.pipeline.ingestion.language_detector import LANG_DETECTION_TEXT_CAP, LanguageDetector

_ENGLISH_TEXT = (
    "The quick brown fox jumps over the lazy dog. "
    "This is a test of the language detection system. "
    "We need enough text to get a reliable detection result. "
    "Natural language processing is a fascinating field of study. "
) * 5

_FRENCH_TEXT = (
    "Le renard brun rapide saute par-dessus le chien paresseux. "
    "Ceci est un test du système de détection de langue. "
    "Nous avons besoin de suffisamment de texte pour un résultat fiable. "
    "Le traitement du langage naturel est un domaine fascinant. "
) * 5


class TestLanguageDetector:
    def test_detects_english(self):
        detector = LanguageDetector(seed=42)
        lang, confidence = detector.detect(_ENGLISH_TEXT)
        assert lang == "en"
        assert 0.0 < confidence <= 1.0

    def test_detects_french(self):
        detector = LanguageDetector(seed=42)
        lang, confidence = detector.detect(_FRENCH_TEXT)
        assert lang == "fr"
        assert confidence > 0.5

    def test_deterministic_with_same_seed(self):
        d1 = LanguageDetector(seed=42)
        d2 = LanguageDetector(seed=42)
        lang1, conf1 = d1.detect(_ENGLISH_TEXT)
        lang2, conf2 = d2.detect(_ENGLISH_TEXT)
        assert lang1 == lang2
        assert abs(conf1 - conf2) < 0.01

    def test_empty_text_raises_value_error(self):
        detector = LanguageDetector(seed=42)
        with pytest.raises(ValueError, match="empty"):
            detector.detect("")

    def test_whitespace_only_raises_value_error(self):
        detector = LanguageDetector(seed=42)
        with pytest.raises(ValueError, match="empty"):
            detector.detect("   \n\t  ")

    def test_confidence_between_0_and_1(self):
        detector = LanguageDetector(seed=42)
        _, confidence = detector.detect(_ENGLISH_TEXT)
        assert 0.0 <= confidence <= 1.0

    def test_lang_detection_text_cap_constant(self):
        assert LANG_DETECTION_TEXT_CAP == 50_000

    def test_long_text_capped(self):
        # A text longer than the cap should not raise — detector caps internally.
        long_text = _ENGLISH_TEXT * 100
        assert len(long_text) > LANG_DETECTION_TEXT_CAP
        detector = LanguageDetector(seed=42)
        lang, _ = detector.detect(long_text)
        assert lang == "en"
