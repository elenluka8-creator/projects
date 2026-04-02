from __future__ import annotations

from decimal import Decimal

import pytest

from app.cost.estimator import (
    CostCapConfig,
    CostCapExceeded,
    CostEstimate,
    EstimationConfig,
    check_job_cap,
    check_retry_cap,
    estimate_job_cost,
)

_CONFIG = EstimationConfig(
    tokens_per_word=Decimal("1.3"),
    context_overhead_ratio=Decimal("0.20"),
    guided_mode_passes=2,
    output_ratio_translate=Decimal("1.0"),
    output_ratio_guided=Decimal("1.5"),
    usd_per_1k_tokens_in=Decimal("0.0015"),
    usd_per_1k_tokens_out=Decimal("0.002"),
    usd_per_1k_cache_read_tokens=Decimal("0.0003"),
)

_CAP = CostCapConfig(
    max_usd_per_job=Decimal("5.00"),
    max_usd_per_retry=Decimal("2.00"),
)


def test_estimate_translate_mode_returns_cost_estimate() -> None:
    estimate = estimate_job_cost(word_count=1000, mode="translate", config=_CONFIG)

    assert isinstance(estimate, CostEstimate)
    assert estimate.estimated_tokens_in > 0
    assert estimate.estimated_tokens_out > 0
    assert estimate.estimated_usd > Decimal("0")


def test_estimate_guided_costs_more_than_translate() -> None:
    translate = estimate_job_cost(word_count=1000, mode="translate", config=_CONFIG)
    guided = estimate_job_cost(word_count=1000, mode="guided", config=_CONFIG)

    assert guided.estimated_tokens_in > translate.estimated_tokens_in
    assert guided.estimated_usd > translate.estimated_usd


def test_estimate_scales_linearly_with_word_count() -> None:
    small = estimate_job_cost(word_count=1000, mode="translate", config=_CONFIG)
    large = estimate_job_cost(word_count=2000, mode="translate", config=_CONFIG)

    assert large.estimated_tokens_in == small.estimated_tokens_in * 2
    assert large.estimated_tokens_out == small.estimated_tokens_out * 2


def test_estimate_guided_uses_two_passes() -> None:
    translate = estimate_job_cost(word_count=1000, mode="translate", config=_CONFIG)
    guided = estimate_job_cost(word_count=1000, mode="guided", config=_CONFIG)

    # guided_mode_passes=2 means guided tokens_in should be ~2x (before output_ratio diff)
    assert guided.estimated_tokens_in > translate.estimated_tokens_in


def test_estimate_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unknown mode"):
        estimate_job_cost(word_count=1000, mode="unknown", config=_CONFIG)


def test_check_job_cap_passes_when_under_limit() -> None:
    estimate = CostEstimate(
        estimated_tokens_in=1000,
        estimated_tokens_out=1000,
        estimated_usd=Decimal("1.00"),
    )
    check_job_cap(estimate, cap_config=_CAP)  # should not raise


def test_check_job_cap_raises_when_over_limit() -> None:
    estimate = CostEstimate(
        estimated_tokens_in=100000,
        estimated_tokens_out=100000,
        estimated_usd=Decimal("6.00"),
    )
    with pytest.raises(CostCapExceeded) as exc_info:
        check_job_cap(estimate, cap_config=_CAP)

    assert exc_info.value.estimated_usd == Decimal("6.00")
    assert exc_info.value.cap_usd == Decimal("5.00")
    assert "per-job" in exc_info.value.reason


def test_check_retry_cap_passes_when_under_limit() -> None:
    check_retry_cap(Decimal("1.50"), cap_config=_CAP)  # should not raise


def test_check_retry_cap_raises_when_over_limit() -> None:
    with pytest.raises(CostCapExceeded) as exc_info:
        check_retry_cap(Decimal("2.50"), cap_config=_CAP)

    assert exc_info.value.cap_usd == Decimal("2.00")
    assert "retry" in exc_info.value.reason


def test_cost_cap_exceeded_carries_all_fields() -> None:
    exc = CostCapExceeded(
        reason="Test reason.",
        estimated_usd=Decimal("3.00"),
        cap_usd=Decimal("2.00"),
    )
    assert exc.reason == "Test reason."
    assert exc.estimated_usd == Decimal("3.00")
    assert exc.cap_usd == Decimal("2.00")


def test_zero_word_count_produces_zero_cost() -> None:
    estimate = estimate_job_cost(word_count=0, mode="translate", config=_CONFIG)
    assert estimate.estimated_usd == Decimal("0")
    assert estimate.estimated_tokens_in == 0
    assert estimate.estimated_tokens_out == 0
