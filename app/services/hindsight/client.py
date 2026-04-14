"""Hindsight SDK client wrapper.

Provides a typed interface to the three core Hindsight operations:
retain, recall, and reflect. All interactions use the explicit client API
so the SaaS controls exactly when memory operations occur.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)


class HindsightClient:
    """Thin wrapper around the Hindsight REST/SDK API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._base_url = (base_url or settings.HINDSIGHT_BASE_URL).rstrip("/")
        self._api_key = api_key or settings.HINDSIGHT_API_KEY
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def retain(
        self,
        bank_id: str,
        content: str,
        *,
        memory_type: str = "world_fact",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write strategic knowledge into the correct account bank.

        Args:
            bank_id: Target bank (e.g. ``acct_142_voc``).
            content: The knowledge to retain.
            memory_type: ``world_fact`` | ``experience`` | ``mental_model``.
            metadata: Structured metadata for filtering on recall.

        Returns:
            Hindsight memory reference payload.
        """
        payload: dict[str, Any] = {
            "bank_id": bank_id,
            "content": content,
            "memory_type": memory_type,
        }
        if metadata:
            payload["metadata"] = metadata

        logger.info("hindsight.retain bank=%s type=%s", bank_id, memory_type)
        resp = await self._http.post("/v1/memories", json=payload)
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def recall(
        self,
        bank_ids: list[str],
        query: str,
        *,
        top_k: int = 20,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch the smallest relevant bank slice needed for a task.

        Args:
            bank_ids: Banks to query (narrow scope per worker contract).
            query: Natural language retrieval query.
            top_k: Maximum memories to return.
            metadata_filter: Key-value filters applied during retrieval.

        Returns:
            Ranked list of memory objects with scores.
        """
        payload: dict[str, Any] = {
            "bank_ids": bank_ids,
            "query": query,
            "top_k": top_k,
        }
        if metadata_filter:
            payload["metadata_filter"] = metadata_filter

        logger.info("hindsight.recall banks=%s query_len=%d", bank_ids, len(query))
        resp = await self._http.post("/v1/memories/recall", json=payload)
        resp.raise_for_status()
        return resp.json().get("memories", [])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    async def reflect(
        self,
        bank_ids: list[str],
        *,
        prompt: str | None = None,
        output_bank_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate higher-order lessons and mental models.

        Args:
            bank_ids: Source banks for reflection.
            prompt: Optional guidance for the reflection.
            output_bank_id: Bank where reflections should be stored.

        Returns:
            Reflection result with generated insights.
        """
        payload: dict[str, Any] = {"bank_ids": bank_ids}
        if prompt:
            payload["prompt"] = prompt
        if output_bank_id:
            payload["output_bank_id"] = output_bank_id

        logger.info("hindsight.reflect banks=%s", bank_ids)
        resp = await self._http.post("/v1/memories/reflect", json=payload)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Bank management
    # ------------------------------------------------------------------

    async def create_bank(
        self,
        bank_id: str,
        *,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "bank_id": bank_id,
            "description": description,
        }
        if metadata:
            payload["metadata"] = metadata

        logger.info("hindsight.create_bank id=%s", bank_id)
        resp = await self._http.post("/v1/banks", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def list_banks(
        self, *, prefix: str | None = None
    ) -> list[dict[str, Any]]:
        params = {}
        if prefix:
            params["prefix"] = prefix
        resp = await self._http.get("/v1/banks", params=params)
        resp.raise_for_status()
        return resp.json().get("banks", [])

    async def delete_bank(self, bank_id: str) -> None:
        resp = await self._http.delete(f"/v1/banks/{bank_id}")
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._http.aclose()


# Module-level singleton
hindsight_client = HindsightClient()
