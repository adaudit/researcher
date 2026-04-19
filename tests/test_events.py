"""Tests for the domain event bus."""

import asyncio

import pytest

from app.core.events import DomainEvent, EventBus, EventTopic


@pytest.mark.asyncio
async def test_event_publish_and_subscribe():
    bus = EventBus()
    received = []

    async def handler(event: DomainEvent):
        received.append(event)

    bus.subscribe(EventTopic.ARTIFACT_INGESTED, handler)

    event = DomainEvent(
        topic=EventTopic.ARTIFACT_INGESTED,
        payload={"artifact_id": "art_1"},
        account_id="acct_1",
    )
    await bus.publish(event)

    assert len(received) == 1
    assert received[0].payload["artifact_id"] == "art_1"


@pytest.mark.asyncio
async def test_event_handler_error_does_not_propagate():
    bus = EventBus()

    async def bad_handler(event: DomainEvent):
        raise ValueError("boom")

    bus.subscribe(EventTopic.MEMORY_RETAINED, bad_handler)

    # Should not raise
    await bus.publish(DomainEvent(
        topic=EventTopic.MEMORY_RETAINED,
        payload={},
    ))
