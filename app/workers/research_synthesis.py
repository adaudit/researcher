"""Research Synthesis Worker — weekly batch processing of research inbox.

Pattern:
  1. Pull all unprocessed inbox items from the past 7 days
  2. Cheap LLM (Qwen Flash) scores each for relevance to the offer
  3. Filter: keep top 20% (or score >= 7)
  4. Premium LLM synthesizes findings → retains to RESEARCH/CULTURE/VOC
  5. Mark items as processed
  6. Cleanup: delete irrelevant + processed older than 30 days

This is the cost-optimal pattern for continuous research ingestion:
- Webhooks ingest data continuously (no polling)
- Cheap filtering removes ~80% noise before premium analysis
- Synthesis runs once weekly, not per-item
- Storage stays bounded via cleanup
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update, delete

from app.db.models.research_inbox import ResearchInbox
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.services.llm.router import Capability, router
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)


RELEVANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "score": {"type": "integer"},
                    "reason": {"type": "string"},
                    "bank_target": {"type": "string"},
                },
            },
        },
    },
}


SYNTHESIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "inbox_id": {"type": "string"},
                    "claim": {"type": "string"},
                    "evidence_strength": {"type": "string"},
                    "source": {"type": "string"},
                    "bank_target": {"type": "string"},
                    "confidence": {"type": "number"},
                    "regulatory_flag": {"type": "boolean"},
                },
            },
        },
        "weekly_summary": {"type": "string"},
        "themes": {"type": "array", "items": {"type": "string"}},
    },
}


# Score cutoffs
MIN_SCORE_FOR_SYNTHESIS = 6
MIN_SCORE_TO_RETAIN_RAW = 4
PROCESSED_RETENTION_DAYS = 30


class ResearchSynthesisWorker(BaseWorker):
    contract = SkillContract(
        skill_name="research_synthesis",
        purpose="Weekly batch synthesis of webhook-ingested research data with cleanup",
        accepted_input_types=["weekly_synthesis_trigger"],
        recall_scope=[
            BankType.OFFER, BankType.RESEARCH, BankType.VOC, BankType.CULTURE,
        ],
        write_scope=[BankType.RESEARCH, BankType.VOC, BankType.CULTURE],
        steps=[
            "fetch_unprocessed_inbox_items",
            "score_relevance_with_cheap_llm",
            "filter_by_score_threshold",
            "synthesize_findings_with_premium_llm",
            "retain_to_appropriate_banks",
            "mark_inbox_processed",
            "cleanup_irrelevant_and_stale",
        ],
        quality_checks=[
            "every_finding_must_cite_source",
            "regulatory_findings_must_be_flagged",
            "score_distribution_must_be_logged",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        from app.db.session import async_session_factory

        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        days_back = params.get("days_back", 7)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        # Step 1: Fetch unprocessed items
        async with async_session_factory() as db:
            stmt = select(ResearchInbox).where(
                ResearchInbox.account_id == account_id,
                ResearchInbox.processed.is_(False),
                ResearchInbox.received_at >= cutoff,
            )
            if offer_id:
                stmt = stmt.where(ResearchInbox.offer_id == offer_id)

            inbox_result = await db.execute(stmt)
            items = list(inbox_result.scalars().all())

        if not items:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=True,
                data={"message": "Inbox empty for this period", "items_processed": 0},
            )

        logger.info(
            "research_synthesis.started account=%s offer=%s items=%d",
            account_id, offer_id, len(items),
        )

        # Step 2: Get offer context for relevance scoring
        offer_memories = await recall_for_worker(
            "research_synthesis", account_id,
            "offer mechanism audience niche product target category",
            offer_id=offer_id, top_k=10,
        )
        offer_context = "\n".join(
            m.get("content", "")[:200] for m in offer_memories
        )

        # Step 3: Cheap LLM scores relevance for ALL items
        scored_items = await self._score_relevance(items, offer_context)

        # Step 4: Filter — only synthesize items above threshold
        synthesis_candidates = [
            (item, score_data)
            for item, score_data in scored_items
            if score_data.get("score", 0) >= MIN_SCORE_FOR_SYNTHESIS
        ]

        score_distribution = {
            "high (8-10)": sum(1 for _, s in scored_items if s.get("score", 0) >= 8),
            "medium (6-7)": sum(1 for _, s in scored_items if 6 <= s.get("score", 0) < 8),
            "low (3-5)": sum(1 for _, s in scored_items if 3 <= s.get("score", 0) < 6),
            "noise (<3)": sum(1 for _, s in scored_items if s.get("score", 0) < 3),
        }
        logger.info(
            "research_synthesis.scored account=%s distribution=%s candidates=%d",
            account_id, score_distribution, len(synthesis_candidates),
        )

        # Step 5: Premium LLM synthesizes the high-relevance items
        synthesis_result: dict[str, Any] = {}
        retained_count = 0

        if synthesis_candidates:
            synthesis_result = await self._synthesize(
                synthesis_candidates, offer_context,
            )

            # Step 6: Retain findings to appropriate banks
            retained_count = await self._retain_findings(
                synthesis_result, account_id, offer_id, synthesis_candidates,
            )

        # Step 7: Mark inbox items as processed + cleanup
        processed_ids: list[str] = []
        delete_ids: list[str] = []

        async with async_session_factory() as db:
            now = datetime.now(timezone.utc)

            for item, score_data in scored_items:
                score = score_data.get("score", 0)

                if score < MIN_SCORE_TO_RETAIN_RAW:
                    # Delete irrelevant items immediately
                    delete_ids.append(item.id)
                else:
                    # Mark processed but keep for audit
                    processed_ids.append(item.id)
                    item_update = (
                        update(ResearchInbox)
                        .where(ResearchInbox.id == item.id)
                        .values(
                            processed=True,
                            processed_at=now,
                            relevance_score=score,
                            relevance_reason=score_data.get("reason", "")[:500],
                            synthesized_to_bank=score_data.get("bank_target")
                                if score >= MIN_SCORE_FOR_SYNTHESIS else None,
                        )
                    )
                    await db.execute(item_update)

            if delete_ids:
                await db.execute(
                    delete(ResearchInbox).where(ResearchInbox.id.in_(delete_ids))
                )

            # Cleanup: delete processed items older than 30 days
            old_cutoff = now - timedelta(days=PROCESSED_RETENTION_DAYS)
            old_delete = await db.execute(
                delete(ResearchInbox).where(
                    ResearchInbox.account_id == account_id,
                    ResearchInbox.processed.is_(True),
                    ResearchInbox.processed_at < old_cutoff,
                )
            )
            cleanup_count = old_delete.rowcount or 0

            await db.commit()

        logger.info(
            "research_synthesis.complete account=%s scored=%d synthesized=%d "
            "retained=%d kept=%d deleted_irrelevant=%d cleanup=%d",
            account_id, len(scored_items), len(synthesis_candidates),
            retained_count, len(processed_ids), len(delete_ids), cleanup_count,
        )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "items_processed": len(scored_items),
                "synthesis_candidates": len(synthesis_candidates),
                "findings_retained": retained_count,
                "deleted_irrelevant": len(delete_ids),
                "cleanup_old_processed": cleanup_count,
                "score_distribution": score_distribution,
                "weekly_summary": synthesis_result.get("weekly_summary", ""),
                "themes": synthesis_result.get("themes", []),
            },
            requires_review=any(
                f.get("regulatory_flag")
                for f in synthesis_result.get("findings", [])
            ),
        )

    async def _score_relevance(
        self,
        items: list[ResearchInbox],
        offer_context: str,
    ) -> list[tuple[ResearchInbox, dict[str, Any]]]:
        """Use cheap LLM to score each item's relevance to the offer."""
        # Batch items to keep prompt size manageable (~30 items per call)
        batch_size = 30
        scored: list[tuple[ResearchInbox, dict[str, Any]]] = []

        for batch_start in range(0, len(items), batch_size):
            batch = items[batch_start:batch_start + batch_size]
            items_summary = [
                {
                    "id": item.id,
                    "source": item.source,
                    "title": (item.title or "")[:200],
                    "summary": (item.summary or "")[:400],
                }
                for item in batch
            ]

            try:
                result = await router.generate(
                    capability=Capability.CLASSIFICATION,
                    system_prompt=(
                        "You are a Research Relevance Scorer. For each item, "
                        "score 1-10 how relevant it is to the offer described.\n\n"
                        "Score guide:\n"
                        "- 9-10: Highly specific, actionable evidence/insight\n"
                        "- 7-8: Strong relevance, direct application\n"
                        "- 5-6: Tangential but useful context\n"
                        "- 3-4: Weak signal, mostly noise\n"
                        "- 1-2: Irrelevant, drop\n\n"
                        "For each, also pick bank_target: research | voc | culture | drop\n"
                        "Be HARSH — most items are noise. Score 7+ should be earned."
                    ),
                    user_prompt=(
                        f"OFFER CONTEXT:\n{offer_context[:3000]}\n\n"
                        f"ITEMS TO SCORE ({len(items_summary)}):\n"
                        f"{json.dumps(items_summary, indent=1)}"
                    ),
                    temperature=0.1,
                    max_tokens=4000,
                    json_schema=RELEVANCE_SCHEMA,
                )

                # Build id → score map from result
                score_map = {
                    r["id"]: r for r in result.get("items", [])
                    if r.get("id")
                }

                for item in batch:
                    score_data = score_map.get(item.id, {"score": 0, "reason": "no score returned"})
                    scored.append((item, score_data))

            except Exception as exc:
                logger.warning(
                    "research_synthesis.scoring_failed batch=%d error=%s",
                    batch_start, exc,
                )
                for item in batch:
                    scored.append((item, {"score": 0, "reason": "scoring failed"}))

        return scored

    async def _synthesize(
        self,
        candidates: list[tuple[ResearchInbox, dict[str, Any]]],
        offer_context: str,
    ) -> dict[str, Any]:
        """Premium LLM synthesizes the high-relevance items into structured findings."""
        items_for_synthesis = [
            {
                "inbox_id": item.id,
                "source": item.source,
                "title": item.title,
                "summary": item.summary,
                "source_url": item.source_url,
                "score": score_data.get("score", 0),
                "score_reason": score_data.get("reason", ""),
            }
            for item, score_data in candidates[:50]
        ]

        return await router.generate(
            capability=Capability.SYNTHESIS,
            system_prompt=(
                "You are a Research Synthesizer. Convert high-relevance research "
                "items into structured findings. For each finding:\n"
                "- inbox_id: the source item ID\n"
                "- claim: the specific claim or fact\n"
                "- evidence_strength: strong | moderate | weak\n"
                "- source: human-readable citation\n"
                "- bank_target: research | voc | culture\n"
                "- confidence: 0-1\n"
                "- regulatory_flag: true if health/regulatory\n\n"
                "Cross-reference items. Flag contradictions. Group related items.\n"
                "Also produce: weekly_summary (3-4 sentences) + themes (top 3-5)."
            ),
            user_prompt=(
                f"OFFER CONTEXT:\n{offer_context[:3000]}\n\n"
                f"HIGH-RELEVANCE ITEMS ({len(items_for_synthesis)}):\n"
                f"{json.dumps(items_for_synthesis, indent=1)[:12000]}"
            ),
            temperature=0.2,
            max_tokens=6000,
            json_schema=SYNTHESIS_SCHEMA,
        )

    async def _retain_findings(
        self,
        synthesis: dict[str, Any],
        account_id: str,
        offer_id: str | None,
        candidates: list[tuple[ResearchInbox, dict[str, Any]]],
    ) -> int:
        """Retain findings to appropriate Hindsight banks."""
        bank_map = {
            "research": BankType.RESEARCH,
            "voc": BankType.VOC,
            "culture": BankType.CULTURE,
        }
        retained = 0

        # Build inbox_id → item map for source URL lookup
        item_lookup = {item.id: item for item, _ in candidates}

        for finding in synthesis.get("findings", []):
            bank_key = finding.get("bank_target", "research")
            bank_type = bank_map.get(bank_key, BankType.RESEARCH)

            inbox_id = finding.get("inbox_id")
            source_item = item_lookup.get(inbox_id)
            source_url = source_item.source_url if source_item else ""

            content = (
                f"{finding.get('claim', '')} "
                f"[{finding.get('evidence_strength', 'unknown')}] "
                f"Source: {finding.get('source', 'unknown')}"
            )

            try:
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=bank_type,
                    content=content,
                    offer_id=offer_id,
                    source_type=source_item.source if source_item else "webhook",
                    source_url=source_url,
                    evidence_type="weekly_synthesis_finding",
                    confidence_score=finding.get("confidence", 0.5),
                )
                if result and source_item:
                    # Stamp the inbox item with the memory ID for traceability
                    from app.db.session import async_session_factory
                    async with async_session_factory() as db:
                        await db.execute(
                            update(ResearchInbox)
                            .where(ResearchInbox.id == source_item.id)
                            .values(hindsight_memory_id=result.get("id"))
                        )
                        await db.commit()
                    retained += 1
            except Exception as exc:
                logger.debug(
                    "research_synthesis.retain_failed finding=%s error=%s",
                    finding.get("claim", "")[:50], exc,
                )

        return retained
