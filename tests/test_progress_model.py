"""Unit tests for FEAT-PROGRESS stage-weighted progress helpers."""
from app.domain.services.progress_model import (
    compute_eta_seconds,
    cumulative_percent_after_stage,
    translate_progress_percent,
)


def test_cumulative_after_stage():
    assert cumulative_percent_after_stage("ingest") == 5
    assert cumulative_percent_after_stage("segment") == 15
    assert cumulative_percent_after_stage("translate") == 85
    assert cumulative_percent_after_stage("format") == 95
    assert cumulative_percent_after_stage("export") == 100


def test_translate_progress_single_batch():
    assert translate_progress_percent(0, 1) == 85


def test_translate_progress_two_batches():
    assert translate_progress_percent(0, 2) == 50  # 15 + 35
    assert translate_progress_percent(1, 2) == 85


def test_compute_eta():
    assert compute_eta_seconds(100.0, 50) == 100
    assert compute_eta_seconds(10.0, 0) is None
    assert compute_eta_seconds(10.0, 100) == 0
