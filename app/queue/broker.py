"""Queue broker implementations.

QueueBrokerProtocol — defines the contract.
InMemoryQueueBroker — for tests; no Redis required.
RedisQueueBroker    — for production; wraps redis-py LIST operations.

Workers enqueue job_run_ids. The broker provides reliable enqueue/dequeue
semantics. Canonical job state always lives in PostgreSQL; Redis is
non-canonical signaling only (DEC-001, ARCH §Queue Broker).
"""
from __future__ import annotations

import logging
from collections import deque
from typing import Deque, Optional, Protocol, runtime_checkable

import uuid

logger = logging.getLogger(__name__)

_QUEUE_KEY = "unfolda:job_run_queue"


@runtime_checkable
class QueueBrokerProtocol(Protocol):
    def enqueue(self, job_run_id: uuid.UUID) -> None: ...
    def dequeue(self, timeout_seconds: int = 0) -> Optional[uuid.UUID]: ...
    def queue_length(self) -> int: ...


class InMemoryQueueBroker:
    """FIFO in-memory queue for tests and local development. Thread-safe for simple cases."""

    def __init__(self) -> None:
        self._queue: Deque[uuid.UUID] = deque()

    def enqueue(self, job_run_id: uuid.UUID) -> None:
        self._queue.append(job_run_id)

    def dequeue(self, timeout_seconds: int = 0) -> Optional[uuid.UUID]:
        if self._queue:
            return self._queue.popleft()
        return None

    def queue_length(self) -> int:
        return len(self._queue)


class RedisQueueBroker:
    """Production queue broker backed by Redis LIST operations.

    Uses RPUSH/BLPOP for reliable enqueue/dequeue. Redis stores only
    job_run_id strings — canonical state remains in PostgreSQL.
    """

    def __init__(self, redis_url: str, queue_key: str = _QUEUE_KEY) -> None:
        try:
            import redis as redis_lib

            self._client = redis_lib.from_url(redis_url, decode_responses=True)
        except ImportError as exc:
            raise ImportError(
                "redis package is required for RedisQueueBroker. "
                "Install it via: pip install redis"
            ) from exc
        self._queue_key = queue_key

    def enqueue(self, job_run_id: uuid.UUID) -> None:
        self._client.rpush(self._queue_key, str(job_run_id))

    def dequeue(self, timeout_seconds: int = 5) -> Optional[uuid.UUID]:
        result = self._client.blpop(self._queue_key, timeout=timeout_seconds)
        if result is None:
            return None
        _, value = result
        return uuid.UUID(value)

    def queue_length(self) -> int:
        return self._client.llen(self._queue_key)
