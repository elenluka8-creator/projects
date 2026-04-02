from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cost.estimator import EstimationConfig
from app.db.models.cost_ledger import CostLedgerEntry
from app.logging.structured import log_structured

logger = logging.getLogger(__name__)


def _calculate_cost_usd(
    tokens_in: int,
    tokens_out: int,
    config: EstimationConfig,
    cache_read_tokens: int = 0,
) -> Decimal:
    billable_in = max(0, tokens_in - cache_read_tokens)
    cost_in = (Decimal(billable_in) / Decimal(1000)) * config.usd_per_1k_tokens_in
    cost_cache = (Decimal(cache_read_tokens) / Decimal(1000)) * config.usd_per_1k_cache_read_tokens
    cost_out = (Decimal(tokens_out) / Decimal(1000)) * config.usd_per_1k_tokens_out
    return (cost_in + cost_cache + cost_out).quantize(Decimal("0.000001"))


def record_batch_cost(
    session: Session,
    job_id: uuid.UUID,
    tokens_in: int,
    tokens_out: int,
    estimation_config: EstimationConfig | None = None,
    *,
    cache_read_tokens: int = 0,
    job_run_id: Optional[uuid.UUID] = None,
    batch_index: Optional[int] = None,
    provider: Optional[str] = None,
) -> CostLedgerEntry:
    """Record a cost ledger entry for a provider batch call.

    Every cost-significant provider interaction must produce a cost_ledger_entry
    (DEC-006). Caller owns the session commit.

    Args:
        session: SQLAlchemy session.
        job_id: The job this batch belongs to.
        tokens_in: Actual input tokens consumed (includes cache_read_tokens per Anthropic API).
        tokens_out: Actual output tokens produced.
        estimation_config: Cost config (defaults to env-sourced config).
        cache_read_tokens: Tokens served from the prompt cache (billed at the cache-read rate).
        job_run_id: Optional run identifier.
        batch_index: Optional batch index within the run.
        provider: Optional provider identifier (e.g. "openai").

    Returns:
        The created CostLedgerEntry (not yet committed).
    """
    config = estimation_config or EstimationConfig.from_env()
    estimated_cost_usd = _calculate_cost_usd(
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        config=config,
        cache_read_tokens=cache_read_tokens,
    )

    entry = CostLedgerEntry(
        job_id=job_id,
        job_run_id=job_run_id,
        batch_index=batch_index,
        provider=provider,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost_usd=float(estimated_cost_usd),
    )
    session.add(entry)
    session.flush()

    log_record = {
        "job_id": str(job_id),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cache_read_tokens": cache_read_tokens,
        "estimated_cost_usd": str(estimated_cost_usd),
    }
    if job_run_id is not None:
        log_record["job_run_id"] = str(job_run_id)
    if batch_index is not None:
        log_record["batch_index"] = batch_index
    if provider is not None:
        log_record["provider"] = provider

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="cost_ledger_entry",
        payload=log_record,
    )

    return entry


def get_run_total_cost(session: Session, job_run_id: uuid.UUID) -> Decimal:
    """Return the total estimated USD cost for all batches in a job run."""
    rows = session.execute(
        select(CostLedgerEntry).where(CostLedgerEntry.job_run_id == job_run_id)
    ).scalars().all()
    return sum(
        (Decimal(str(r.estimated_cost_usd)) for r in rows), Decimal("0")
    )


def get_job_total_cost(session: Session, job_id: uuid.UUID) -> Decimal:
    """Return the total estimated USD cost across all runs for a job."""
    rows = session.execute(
        select(CostLedgerEntry).where(CostLedgerEntry.job_id == job_id)
    ).scalars().all()
    return sum(
        (Decimal(str(r.estimated_cost_usd)) for r in rows), Decimal("0")
    )
