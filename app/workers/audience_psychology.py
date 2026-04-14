"""Audience Psychology Worker

Input:  Normalized evidence
Output: Desire map, fear map, awareness map
Banks:  recall from offer, VOC, creative, reflection banks
Guard:  Must not exceed evidence coverage
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class AudiencePsychologyWorker(BaseWorker):
    contract = SkillContract(
        skill_name="audience_psychology",
        purpose="Map audience desires, fears, identity motives, and awareness levels from evidence",
        accepted_input_types=["evidence_set", "recall_query"],
        recall_scope=[BankType.OFFER, BankType.VOC, BankType.CREATIVE, BankType.REFLECTION],
        write_scope=[],  # produces strategy outputs, does not retain directly
        steps=[
            "recall_audience_evidence",
            "cluster_desires",
            "cluster_fears",
            "identify_identity_motives",
            "map_awareness_levels",
            "validate_coverage",
            "produce_desire_map",
        ],
        quality_checks=[
            "every_desire_must_cite_evidence",
            "fears_must_distinguish_stated_from_implied",
            "awareness_map_must_cover_spectrum",
            "must_not_exceed_evidence_coverage",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id

        # Recall audience-relevant memories
        memories = await recall_for_worker(
            "audience_psychology",
            account_id,
            "audience desires fears pain objections motivation identity",
            offer_id=offer_id,
            top_k=30,
        )

        desires: list[dict[str, Any]] = []
        fears: list[dict[str, Any]] = []
        identity_motives: list[dict[str, Any]] = []

        for mem in memories:
            content = mem.get("content", "")
            metadata = mem.get("metadata", {})
            evidence_type = metadata.get("evidence_type", "")
            ref = mem.get("id", "")

            if evidence_type == "audience_desire":
                desires.append({"statement": content, "evidence_ref": ref})
            elif evidence_type == "audience_objection":
                fears.append({"statement": content, "evidence_ref": ref, "type": "objection"})
            elif "pain" in evidence_type:
                fears.append({"statement": content, "evidence_ref": ref, "type": "pain"})

        desire_map = {
            "wants": desires,
            "pain_escapes": [f for f in fears if f.get("type") == "pain"],
            "identity_motives": identity_motives,
            "objections": [f for f in fears if f.get("type") == "objection"],
            "evidence_count": len(memories),
        }

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={"desire_map": desire_map},
        )
