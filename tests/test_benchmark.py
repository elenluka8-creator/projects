from __future__ import annotations

import os
import tempfile

import pytest

from app.telemetry.benchmark import (
    EVALUATION_DATASET,
    BenchmarkCase,
    BenchmarkResult,
    BenchmarkStore,
    compare_runs,
)


@pytest.fixture
def tmp_store(tmp_path) -> BenchmarkStore:
    return BenchmarkStore(store_path=str(tmp_path / "benchmarks"))


def test_benchmark_store_creates_directory_on_first_use(tmp_path) -> None:
    store_path = str(tmp_path / "new_benchmarks")
    store = BenchmarkStore(store_path=store_path)
    assert not os.path.exists(store_path)

    store.record(
        BenchmarkResult(
            run_label="run-001",
            case_id="test-case",
            metric_name="quality_score",
            metric_value=0.85,
            recorded_at="2026-03-14T00:00:00+00:00",
        )
    )
    assert os.path.exists(store_path)


def test_benchmark_store_record_and_load_roundtrip(tmp_store: BenchmarkStore) -> None:
    result = BenchmarkResult(
        run_label="run-001",
        case_id="en-fr-translate-short",
        metric_name="quality_score",
        metric_value=0.87,
        recorded_at="2026-03-14T00:00:00+00:00",
    )
    tmp_store.record(result)

    loaded = tmp_store.load_results(case_id="en-fr-translate-short", run_label="run-001")
    assert len(loaded) == 1
    assert loaded[0].metric_value == 0.87
    assert loaded[0].metric_name == "quality_score"


def test_benchmark_store_isolates_by_run_label(tmp_store: BenchmarkStore) -> None:
    tmp_store.record(
        BenchmarkResult("run-001", "case-a", "score", 0.9, "2026-03-14T00:00:00+00:00")
    )
    tmp_store.record(
        BenchmarkResult("run-002", "case-a", "score", 0.8, "2026-03-14T01:00:00+00:00")
    )

    run1 = tmp_store.load_results("case-a", "run-001")
    run2 = tmp_store.load_results("case-a", "run-002")
    assert len(run1) == 1
    assert len(run2) == 1
    assert run1[0].metric_value == 0.9
    assert run2[0].metric_value == 0.8


def test_benchmark_store_list_run_labels(tmp_store: BenchmarkStore) -> None:
    for label in ["run-001", "run-002", "run-003"]:
        tmp_store.record(
            BenchmarkResult(label, "case-b", "score", 0.75, "2026-03-14T00:00:00+00:00")
        )

    labels = tmp_store.list_run_labels("case-b")
    assert set(labels) == {"run-001", "run-002", "run-003"}


def test_benchmark_store_returns_empty_for_unknown_case(tmp_store: BenchmarkStore) -> None:
    results = tmp_store.load_results("nonexistent-case", "run-001")
    assert results == []

    labels = tmp_store.list_run_labels("nonexistent-case")
    assert labels == []


def test_compare_runs_passes_when_within_tolerance(tmp_store: BenchmarkStore) -> None:
    tmp_store.record(
        BenchmarkResult("baseline", "case-c", "quality_score", 0.90, "2026-03-14T00:00:00+00:00")
    )
    tmp_store.record(
        BenchmarkResult("candidate", "case-c", "quality_score", 0.87, "2026-03-14T01:00:00+00:00")
    )

    # 0.87 vs 0.90 = 3.3% regression, within 5% tolerance
    result = compare_runs(
        store=tmp_store,
        case_id="case-c",
        baseline_label="baseline",
        candidate_label="candidate",
        metric_name="quality_score",
        max_regression_ratio=0.05,
    )
    assert result is True


def test_compare_runs_detects_regression(tmp_store: BenchmarkStore) -> None:
    tmp_store.record(
        BenchmarkResult("baseline", "case-d", "quality_score", 0.90, "2026-03-14T00:00:00+00:00")
    )
    tmp_store.record(
        BenchmarkResult("candidate", "case-d", "quality_score", 0.75, "2026-03-14T01:00:00+00:00")
    )

    # 0.75 vs 0.90 = 16.7% regression, exceeds 5% tolerance
    result = compare_runs(
        store=tmp_store,
        case_id="case-d",
        baseline_label="baseline",
        candidate_label="candidate",
        metric_name="quality_score",
        max_regression_ratio=0.05,
    )
    assert result is False


def test_compare_runs_raises_when_baseline_missing(tmp_store: BenchmarkStore) -> None:
    tmp_store.record(
        BenchmarkResult("candidate", "case-e", "score", 0.8, "2026-03-14T00:00:00+00:00")
    )
    with pytest.raises(ValueError, match="No baseline results"):
        compare_runs(
            store=tmp_store,
            case_id="case-e",
            baseline_label="nonexistent-baseline",
            candidate_label="candidate",
            metric_name="score",
        )


def test_compare_runs_raises_when_candidate_missing(tmp_store: BenchmarkStore) -> None:
    tmp_store.record(
        BenchmarkResult("baseline", "case-f", "score", 0.8, "2026-03-14T00:00:00+00:00")
    )
    with pytest.raises(ValueError, match="No candidate results"):
        compare_runs(
            store=tmp_store,
            case_id="case-f",
            baseline_label="baseline",
            candidate_label="nonexistent-candidate",
            metric_name="score",
        )


def test_evaluation_dataset_has_minimum_cases() -> None:
    assert len(EVALUATION_DATASET) >= 6


def test_evaluation_dataset_covers_multiple_language_pairs() -> None:
    language_pairs = {case.language_pair for case in EVALUATION_DATASET}
    assert len(language_pairs) >= 3


def test_evaluation_dataset_covers_both_modes() -> None:
    modes = {case.mode for case in EVALUATION_DATASET}
    assert "translate" in modes
    assert "guided" in modes


def test_evaluation_dataset_case_ids_are_unique() -> None:
    case_ids = [case.case_id for case in EVALUATION_DATASET]
    assert len(case_ids) == len(set(case_ids))


def test_evaluation_dataset_has_valid_expected_segment_counts() -> None:
    for case in EVALUATION_DATASET:
        assert case.expected_segment_count > 0
