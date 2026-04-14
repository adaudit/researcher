"""Creative Ingest Worker

Input:  Winning ads, uploads, exports, links
Output: Normalized creative observations
Banks:  retain to creative bank
Guard:  Must preserve source linkage
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class CreativeIngestWorker(BaseWorker):
    contract = SkillContract(
        skill_name="creative_ingest",
        purpose="Ingest winning creatives and extract structured observations",
        accepted_input_types=["ad_export", "creative_link", "screenshot", "upload"],
        recall_scope=[BankType.CREATIVE],
        write_scope=[BankType.CREATIVE],
        steps=[
            "classify_creative_type",
            "extract_hook",
            "extract_angle",
            "extract_structure",
            "identify_proof_elements",
            "retain_observations",
        ],
        quality_checks=[
            "every_observation_must_link_to_source",
            "hook_extraction_must_preserve_exact_text",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params
        observations: list[dict[str, Any]] = []

        creatives = params.get("creatives", [])
        for creative in creatives:
            source_url = creative.get("source_url", "")
            artifact_id = creative.get("artifact_id")
            creative_type = creative.get("type", "unknown")  # image | video | text | carousel
            headline = creative.get("headline", "")
            body_text = creative.get("body_text", "")

            # Retain headline as hook pattern
            if headline:
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.CREATIVE,
                    content=f"Winning creative hook ({creative_type}): {headline}",
                    offer_id=offer_id,
                    artifact_id=artifact_id,
                    source_type="upload",
                    source_url=source_url,
                    evidence_type="hook_pattern",
                    confidence_score=0.8,
                )
                if result:
                    observations.append({
                        "type": "hook_pattern",
                        "source": source_url,
                        "memory_ref": result.get("id"),
                    })

            # Retain body text as creative structure observation
            if body_text:
                await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.CREATIVE,
                    content=f"Creative body structure ({creative_type}): {body_text[:500]}",
                    offer_id=offer_id,
                    artifact_id=artifact_id,
                    source_type="upload",
                    source_url=source_url,
                    evidence_type="creative_structure",
                    confidence_score=0.7,
                )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={"ingested_count": len(creatives)},
            observations=observations,
        )
