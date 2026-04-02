from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class EstimationConfig:
    """Token-level cost estimation parameters.

    All values are configurable from environment variables so that prompt
    changes remain visible and reviewable rather than hidden implementation drift
    (DEC-006 §Consequences).
    """

    tokens_per_word: Decimal
    context_overhead_ratio: Decimal
    guided_mode_passes: int
    output_ratio_translate: Decimal
    output_ratio_guided: Decimal
    usd_per_1k_tokens_in: Decimal
    usd_per_1k_tokens_out: Decimal
    usd_per_1k_cache_read_tokens: Decimal = Decimal("0.0003")

    @staticmethod
    def from_env() -> "EstimationConfig":
        return EstimationConfig(
            tokens_per_word=Decimal(os.getenv("COST_TOKENS_PER_WORD", "1.3")),
            context_overhead_ratio=Decimal(
                os.getenv("COST_CONTEXT_OVERHEAD_RATIO", "0.20")
            ),
            guided_mode_passes=int(os.getenv("COST_GUIDED_MODE_PASSES", "2")),
            output_ratio_translate=Decimal(
                os.getenv("COST_OUTPUT_RATIO_TRANSLATE", "1.0")
            ),
            output_ratio_guided=Decimal(os.getenv("COST_OUTPUT_RATIO_GUIDED", "1.5")),
            usd_per_1k_tokens_in=Decimal(
                os.getenv("COST_USD_PER_1K_TOKENS_IN", "0.0015")
            ),
            usd_per_1k_tokens_out=Decimal(
                os.getenv("COST_USD_PER_1K_TOKENS_OUT", "0.002")
            ),
            usd_per_1k_cache_read_tokens=Decimal(
                os.getenv("COST_USD_PER_1K_CACHE_READ_TOKENS", "0.0003")
            ),
        )


@dataclass(frozen=True)
class CostEstimate:
    estimated_tokens_in: int
    estimated_tokens_out: int
    estimated_usd: Decimal


@dataclass(frozen=True)
class CostCapConfig:
    """Hard cost caps for job and retry budget enforcement (DEC-006, DEC-007)."""

    max_usd_per_job: Decimal
    max_usd_per_retry: Decimal

    @staticmethod
    def from_env() -> "CostCapConfig":
        return CostCapConfig(
            max_usd_per_job=Decimal(os.getenv("COST_MAX_USD_PER_JOB", "5.00")),
            max_usd_per_retry=Decimal(os.getenv("COST_MAX_USD_PER_RETRY", "2.00")),
        )


class CostCapExceeded(Exception):
    """Raised when a cost estimate or accumulated cost exceeds a hard cap."""

    def __init__(self, reason: str, estimated_usd: Decimal, cap_usd: Decimal) -> None:
        super().__init__(
            f"{reason} Estimated: ${estimated_usd:.6f}, Cap: ${cap_usd:.6f}."
        )
        self.reason = reason
        self.estimated_usd = estimated_usd
        self.cap_usd = cap_usd


def estimate_job_cost(
    word_count: int,
    mode: str,
    config: EstimationConfig | None = None,
) -> CostEstimate:
    """Estimate LLM inference cost for a job before queue admission.

    Formula (per DEC-006 §Estimation):
        passes          = 1 (translate) or guided_mode_passes (guided)
        raw_tokens_in   = word_count × tokens_per_word × passes × (1 + overhead)
        raw_tokens_out  = word_count × tokens_per_word × passes × output_ratio
        estimated_usd   = (tokens_in × usd_per_1k_in + tokens_out × usd_per_1k_out) / 1000

    Args:
        word_count: Source word count from pre-submission analysis.
        mode: Processing mode — "translate" or "guided".
        config: Estimation parameters (defaults to env-sourced config).

    Returns:
        CostEstimate with token counts and USD estimate.

    Raises:
        ValueError: if mode is not "translate" or "guided".
    """
    if mode not in ("translate", "guided"):
        raise ValueError(f"Unknown mode '{mode}'. Must be 'translate' or 'guided'.")

    cfg = config or EstimationConfig.from_env()

    passes = 1 if mode == "translate" else cfg.guided_mode_passes
    output_ratio = (
        cfg.output_ratio_translate if mode == "translate" else cfg.output_ratio_guided
    )

    overhead_multiplier = Decimal(1) + cfg.context_overhead_ratio
    base_tokens = Decimal(word_count) * cfg.tokens_per_word * Decimal(passes)

    tokens_in_decimal = base_tokens * overhead_multiplier
    tokens_out_decimal = base_tokens * output_ratio

    tokens_in = int(tokens_in_decimal.to_integral_value())
    tokens_out = int(tokens_out_decimal.to_integral_value())

    cost_in = (Decimal(tokens_in) / Decimal(1000)) * cfg.usd_per_1k_tokens_in
    cost_out = (Decimal(tokens_out) / Decimal(1000)) * cfg.usd_per_1k_tokens_out
    estimated_usd = (cost_in + cost_out).quantize(Decimal("0.000001"))

    return CostEstimate(
        estimated_tokens_in=tokens_in,
        estimated_tokens_out=tokens_out,
        estimated_usd=estimated_usd,
    )


def check_job_cap(
    estimate: CostEstimate,
    cap_config: CostCapConfig | None = None,
) -> None:
    """Raise CostCapExceeded if the job estimate exceeds the per-job hard cap.

    Called before queue admission (DEC-006).
    """
    cfg = cap_config or CostCapConfig.from_env()
    if estimate.estimated_usd > cfg.max_usd_per_job:
        raise CostCapExceeded(
            reason="Job cost estimate exceeds per-job hard cap.",
            estimated_usd=estimate.estimated_usd,
            cap_usd=cfg.max_usd_per_job,
        )


def check_retry_cap(
    accumulated_usd: Decimal,
    cap_config: CostCapConfig | None = None,
) -> None:
    """Raise CostCapExceeded if accumulated retry cost exceeds the retry budget.

    Called before scheduling a retry (DEC-007).
    """
    cfg = cap_config or CostCapConfig.from_env()
    if accumulated_usd > cfg.max_usd_per_retry:
        raise CostCapExceeded(
            reason="Accumulated retry cost exceeds per-retry budget cap.",
            estimated_usd=accumulated_usd,
            cap_usd=cfg.max_usd_per_retry,
        )
