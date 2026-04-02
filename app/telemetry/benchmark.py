from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List, Optional


@dataclass(frozen=True)
class BenchmarkCase:
    """A single evaluation case in the benchmark dataset."""

    case_id: str
    language_pair: str  # e.g. "en-fr", "en-ja"
    mode: str  # "translate" | "guided"
    description: str
    expected_segment_count: int


@dataclass
class BenchmarkResult:
    """A single metric measurement from a benchmark run."""

    run_label: str
    case_id: str
    metric_name: str
    metric_value: float
    recorded_at: str  # ISO-8601 UTC


class BenchmarkStore:
    """JSON-file-backed store for benchmark results.

    Creates the store directory and file on first use.
    Each case gets its own JSON file: {store_path}/{case_id}.json
    """

    def __init__(self, store_path: str) -> None:
        self._path = store_path

    def _case_file(self, case_id: str) -> str:
        return os.path.join(self._path, f"{case_id}.json")

    def _ensure_dir(self) -> None:
        os.makedirs(self._path, exist_ok=True)

    def record(self, result: BenchmarkResult) -> None:
        """Append a benchmark result to the case store."""
        self._ensure_dir()
        case_file = self._case_file(result.case_id)
        records: List[dict] = []
        if os.path.exists(case_file):
            with open(case_file, "r", encoding="utf-8") as f:
                records = json.load(f)
        records.append(asdict(result))
        with open(case_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    def load_results(self, case_id: str, run_label: str) -> List[BenchmarkResult]:
        """Load all results for a given case and run label."""
        case_file = self._case_file(case_id)
        if not os.path.exists(case_file):
            return []
        with open(case_file, "r", encoding="utf-8") as f:
            records = json.load(f)
        return [
            BenchmarkResult(**r)
            for r in records
            if r.get("run_label") == run_label
        ]

    def list_run_labels(self, case_id: str) -> List[str]:
        """Return all distinct run labels for a case."""
        case_file = self._case_file(case_id)
        if not os.path.exists(case_file):
            return []
        with open(case_file, "r", encoding="utf-8") as f:
            records = json.load(f)
        return list(dict.fromkeys(r.get("run_label", "") for r in records))


def compare_runs(
    store: BenchmarkStore,
    case_id: str,
    baseline_label: str,
    candidate_label: str,
    metric_name: str,
    max_regression_ratio: float = 0.05,
) -> bool:
    """Compare a candidate run against a baseline for regression.

    Returns True when candidate is within tolerance (no regression).
    Returns False when candidate has regressed beyond max_regression_ratio.

    A regression is defined as: candidate_value < baseline_value * (1 - max_regression_ratio)
    (applies to metrics where higher is better, such as quality scores).

    For metrics where lower is better (e.g. latency), callers should negate values
    before recording to use this function correctly.

    Args:
        store: BenchmarkStore to load results from.
        case_id: The benchmark case ID.
        baseline_label: Label of the baseline run.
        candidate_label: Label of the candidate run.
        metric_name: The metric to compare.
        max_regression_ratio: Maximum allowed relative regression (default 5%).

    Returns:
        True = no regression; False = regression detected.

    Raises:
        ValueError: if baseline or candidate results are not found for the metric.
    """
    baseline_results = store.load_results(case_id=case_id, run_label=baseline_label)
    candidate_results = store.load_results(case_id=case_id, run_label=candidate_label)

    baseline_values = [r.metric_value for r in baseline_results if r.metric_name == metric_name]
    candidate_values = [r.metric_value for r in candidate_results if r.metric_name == metric_name]

    if not baseline_values:
        raise ValueError(
            f"No baseline results found for case '{case_id}', "
            f"run '{baseline_label}', metric '{metric_name}'."
        )
    if not candidate_values:
        raise ValueError(
            f"No candidate results found for case '{case_id}', "
            f"run '{candidate_label}', metric '{metric_name}'."
        )

    baseline_avg = sum(baseline_values) / len(baseline_values)
    candidate_avg = sum(candidate_values) / len(candidate_values)

    if baseline_avg == 0:
        return candidate_avg >= 0

    regression_ratio = (baseline_avg - candidate_avg) / baseline_avg
    return regression_ratio <= max_regression_ratio


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Representative evaluation dataset for MVP quality regression detection.
# Language pairs: en-fr (European), en-ja (ideographic), en-es (Latin)
# Modes: translate, guided
# Shapes: short (few segments), long (many segments)
EVALUATION_DATASET: List[BenchmarkCase] = [
    BenchmarkCase(
        case_id="en-fr-translate-short",
        language_pair="en-fr",
        mode="translate",
        description="Short English-to-French translation (prose, ~10 segments)",
        expected_segment_count=10,
    ),
    BenchmarkCase(
        case_id="en-fr-translate-long",
        language_pair="en-fr",
        mode="translate",
        description="Long English-to-French translation (novel chapter, ~200 segments)",
        expected_segment_count=200,
    ),
    BenchmarkCase(
        case_id="en-ja-translate-short",
        language_pair="en-ja",
        mode="translate",
        description="Short English-to-Japanese translation (ideographic target, ~10 segments)",
        expected_segment_count=10,
    ),
    BenchmarkCase(
        case_id="en-es-translate-short",
        language_pair="en-es",
        mode="translate",
        description="Short English-to-Spanish translation (~15 segments)",
        expected_segment_count=15,
    ),
    BenchmarkCase(
        case_id="en-fr-guided-short",
        language_pair="en-fr",
        mode="guided",
        description="Short English-to-French guided reading (4-block output, ~10 segments)",
        expected_segment_count=10,
    ),
    BenchmarkCase(
        case_id="en-ja-guided-short",
        language_pair="en-ja",
        mode="guided",
        description="Short English-to-Japanese guided reading (~10 segments)",
        expected_segment_count=10,
    ),
]
