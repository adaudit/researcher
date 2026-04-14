"""Domain event bus for the creative strategy platform.

Events are emitted when significant state transitions occur. Consumers can
subscribe to topics for real-time notifications and webhook delivery.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventTopic(str, Enum):
    ARTIFACT_INGESTED = "artifact.ingested"
    MEMORY_RETAINED = "memory.retained"
    MEMORY_REFLECTION_CREATED = "memory.reflection_created"
    STRATEGY_BASELINE_READY = "strategy.baseline_ready"
    ITERATION_HEADERS_READY = "iteration.headers_ready"
    PERFORMANCE_FEEDBACK_RECEIVED = "performance.feedback_received"
    WORKFLOW_STATE_CHANGED = "workflow.state_changed"
    OFFER_UPDATED = "offer.updated"


@dataclass
class DomainEvent:
    topic: EventTopic
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    account_id: str | None = None
    offer_id: str | None = None


EventHandler = Callable[[DomainEvent], Coroutine[Any, Any, None]]


class EventBus:
    """In-process async event bus. Replace with Redis Streams or a proper
    message broker for multi-instance deployments."""

    def __init__(self) -> None:
        self._handlers: dict[EventTopic, list[EventHandler]] = defaultdict(list)

    def subscribe(self, topic: EventTopic, handler: EventHandler) -> None:
        self._handlers[topic].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        logger.info("event.published topic=%s id=%s", event.topic, event.event_id)
        handlers = self._handlers.get(event.topic, [])
        await asyncio.gather(
            *(self._safe_dispatch(h, event) for h in handlers),
            return_exceptions=True,
        )

    @staticmethod
    async def _safe_dispatch(handler: EventHandler, event: DomainEvent) -> None:
        try:
            await handler(event)
        except Exception:
            logger.exception(
                "event.handler_error topic=%s handler=%s",
                event.topic,
                handler.__qualname__,
            )


# Singleton — wired into the FastAPI lifespan and available to workers
event_bus = EventBus()
