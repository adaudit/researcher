"""Offer Intelligence Worker

Input:  Offer form, PDP, founder notes
Output: Offer map, mechanism, CTA schema, constraints
Banks:  retain to core and offer banks
Guard:  Cannot invent mechanism or proof
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class OfferIntelligenceWorker(BaseWorker):
    contract = SkillContract(
        skill_name="offer_intelligence",
        purpose="Capture mechanism, CTA, constraints, proof, and buyer context from offer inputs",
        accepted_input_types=["offer_form", "pdp_url", "founder_notes"],
        recall_scope=[BankType.CORE, BankType.OFFER],
        write_scope=[BankType.CORE, BankType.OFFER],
        steps=[
            "parse_offer_inputs",
            "extract_mechanism",
            "extract_cta_schema",
            "identify_constraints",
            "map_proof_basis",
            "identify_buyer_context",
            "retain_offer_truths",
        ],
        quality_checks=[
            "mechanism_must_be_from_source",
            "proof_claims_must_cite_evidence",
            "no_invented_mechanisms",
        ],
        escalation_rule="Escalate if mechanism is unclear or claim constraints are ambiguous",
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        offer_map: dict[str, Any] = {
            "mechanism": params.get("mechanism"),
            "cta": params.get("cta"),
            "price_point": params.get("price_point"),
            "price_model": params.get("price_model"),
            "claim_constraints": params.get("claim_constraints", {}),
            "target_audience": params.get("target_audience"),
            "awareness_level": params.get("awareness_level"),
            "proof_basis": params.get("proof_basis", {}),
            "product_url": params.get("product_url"),
        }

        observations: list[dict[str, Any]] = []

        # Retain core offer truths
        if offer_map["mechanism"]:
            result = await retain_observation(
                account_id=account_id,
                bank_type=BankType.OFFER,
                content=f"Offer mechanism: {offer_map['mechanism']}",
                offer_id=offer_id,
                source_type="manual",
                evidence_type="mechanism_insight",
                confidence_score=0.9,
            )
            if result:
                observations.append({"type": "mechanism", "memory_ref": result.get("id")})

        if offer_map["cta"]:
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.OFFER,
                content=f"Primary CTA: {offer_map['cta']}",
                offer_id=offer_id,
                source_type="manual",
                evidence_type="offer_truth",
                confidence_score=0.95,
            )

        if offer_map["target_audience"]:
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.CORE,
                content=f"Target audience: {offer_map['target_audience']}",
                offer_id=offer_id,
                source_type="manual",
                evidence_type="offer_truth",
                confidence_score=0.9,
            )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={"offer_map": offer_map},
            observations=observations,
        )
