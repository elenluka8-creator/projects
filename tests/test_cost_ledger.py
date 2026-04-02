from __future__ import annotations

import logging
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 — registers all models with Base
from app.db.base import Base
from app.db.models.cost_ledger import CostLedgerEntry
from app.cost.estimator import EstimationConfig
from app.cost.ledger import get_job_total_cost, get_run_total_cost, record_batch_cost


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


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_record_batch_cost_inserts_entry(db_session) -> None:
    job_id = uuid4()

    entry = record_batch_cost(
        session=db_session,
        job_id=job_id,
        tokens_in=1000,
        tokens_out=800,
        estimation_config=_CONFIG,
    )
    db_session.commit()

    record = db_session.get(CostLedgerEntry, entry.entry_id)
    assert record is not None
    assert record.job_id == job_id
    assert record.tokens_in == 1000
    assert record.tokens_out == 800
    assert record.estimated_cost_usd > 0


def test_record_batch_cost_stores_optional_fields(db_session) -> None:
    job_id = uuid4()
    job_run_id = uuid4()

    entry = record_batch_cost(
        session=db_session,
        job_id=job_id,
        tokens_in=500,
        tokens_out=400,
        estimation_config=_CONFIG,
        job_run_id=job_run_id,
        batch_index=2,
        provider="openai",
    )
    db_session.commit()

    record = db_session.get(CostLedgerEntry, entry.entry_id)
    assert record.job_run_id == job_run_id
    assert record.batch_index == 2
    assert record.provider == "openai"


def test_record_batch_cost_emits_structured_log(
    db_session, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.cost.ledger"):
        record_batch_cost(
            session=db_session,
            job_id=uuid4(),
            tokens_in=100,
            tokens_out=80,
            estimation_config=_CONFIG,
        )

    assert any("cost_ledger_entry" in r.message for r in caplog.records)


def test_zero_tokens_produces_zero_cost(db_session) -> None:
    entry = record_batch_cost(
        session=db_session,
        job_id=uuid4(),
        tokens_in=0,
        tokens_out=0,
        estimation_config=_CONFIG,
    )
    db_session.commit()

    record = db_session.get(CostLedgerEntry, entry.entry_id)
    assert Decimal(str(record.estimated_cost_usd)) == Decimal("0")


def test_get_run_total_cost_aggregates_entries(db_session) -> None:
    job_id = uuid4()
    job_run_id = uuid4()

    record_batch_cost(
        session=db_session,
        job_id=job_id,
        tokens_in=1000,
        tokens_out=800,
        estimation_config=_CONFIG,
        job_run_id=job_run_id,
        batch_index=0,
    )
    record_batch_cost(
        session=db_session,
        job_id=job_id,
        tokens_in=1000,
        tokens_out=800,
        estimation_config=_CONFIG,
        job_run_id=job_run_id,
        batch_index=1,
    )
    db_session.commit()

    total = get_run_total_cost(db_session, job_run_id)
    single = record_batch_cost(
        session=db_session,
        job_id=uuid4(),
        tokens_in=1000,
        tokens_out=800,
        estimation_config=_CONFIG,
    )
    single_cost = Decimal(str(single.estimated_cost_usd))

    assert total == (single_cost * 2).quantize(Decimal("0.000001"))


def test_get_job_total_cost_aggregates_across_runs(db_session) -> None:
    job_id = uuid4()
    run_a = uuid4()
    run_b = uuid4()

    for run_id in (run_a, run_b):
        record_batch_cost(
            session=db_session,
            job_id=job_id,
            tokens_in=500,
            tokens_out=400,
            estimation_config=_CONFIG,
            job_run_id=run_id,
        )
    db_session.commit()

    run_a_total = get_run_total_cost(db_session, run_a)
    job_total = get_job_total_cost(db_session, job_id)

    assert job_total == (run_a_total * 2).quantize(Decimal("0.000001"))


def test_get_run_total_cost_returns_zero_for_unknown_run(db_session) -> None:
    total = get_run_total_cost(db_session, uuid4())
    assert total == Decimal("0")


def test_get_job_total_cost_returns_zero_for_unknown_job(db_session) -> None:
    total = get_job_total_cost(db_session, uuid4())
    assert total == Decimal("0")


def test_cache_read_tokens_reduce_cost(db_session) -> None:
    job_id = uuid4()

    entry_no_cache = record_batch_cost(
        session=db_session,
        job_id=job_id,
        tokens_in=1000,
        tokens_out=500,
        estimation_config=_CONFIG,
        cache_read_tokens=0,
    )
    entry_with_cache = record_batch_cost(
        session=db_session,
        job_id=job_id,
        tokens_in=1000,
        tokens_out=500,
        estimation_config=_CONFIG,
        cache_read_tokens=800,
    )
    db_session.commit()

    cost_no_cache = Decimal(str(entry_no_cache.estimated_cost_usd))
    cost_with_cache = Decimal(str(entry_with_cache.estimated_cost_usd))

    assert cost_with_cache < cost_no_cache
