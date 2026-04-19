"""Offer Intelligence Worker — LLM-powered offer decomposition.

Input:  Offer form, PDP, founder notes
Output: Offer map, mechanism, CTA schema, constraints
Banks:  retain to core and offer banks
Guard:  Cannot invent mechanism or proof
"""

from __future__ import annotations

from typing import Any

from app.prompts.systems import OFFER_INTELLIGENCE_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.knowledge.base_training import get_training_context
from app.services.llm.router import Capability, router
from app.services.llm.schemas import OFFER_ANALYSIS_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class OfferIntelligenceWorker(BaseWorker):
    contract = SkillContract(
        skill_name="offer_intelligence",
        purpose="Capture mechanism, CTA, constraints, proof, and buyer context from offer inputs",
        accepted_input_types=["offer_form", "pdp_url", "founder_notes"],
        recall_scope=[BankType.CORE, BankType.OFFER],
        write_scope=[BankType.CORE, BankType.OFFER],
        steps=[
            "assemble_offer_context",
            "llm_analyze_offer",
            "extract_mechanism_and_cta",
            "identify_constraints_and_risks",
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

        # Assemble all offer context into a single document
        context_parts: list[str] = []
        for field in ("mechanism", "cta", "target_audience", "product_url",
                       "founder_notes", "pdp_text", "faqs", "pricing_info"):
            val = params.get(field)
            if val:
                context_parts.append(f"## {field.replace('_', ' ').title()}\n{val}")

        offer_context = "\n\n".join(context_parts) if context_parts else str(params)

        # LLM analysis — router selects best model for text extraction
        training_context = get_training_context()
        analysis = await router.generate(
            capability=Capability.TEXT_EXTRACTION,
            system_prompt=f"{OFFER_INTELLIGENCE_SYSTEM}\n\n{training_context}",
            user_prompt=(
                f"Analyze the following offer and decompose it into its strategic components.\n\n"
                f"OFFER DATA:\n{offer_context}"
            ),
            temperature=0.2,
            json_schema=OFFER_ANALYSIS_SCHEMA,
        )

        if analysis.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM response"],
            )

        observations: list[dict[str, Any]] = []

        # Retain mechanism
        mechanism = analysis.get("mechanism", {})
        if mechanism.get("what_it_does"):
            mechanism_text = (
                f"Mechanism: {mechanism['what_it_does']}. "
                f"How it works: {mechanism.get('how_it_works', 'not specified')}. "
                f"Why believable: {mechanism.get('why_its_believable', 'not specified')}. "
                f"Unique factor: {mechanism.get('unique_factor', 'not specified')}."
            )
            result = await retain_observation(
                account_id=account_id,
                bank_type=BankType.OFFER,
                content=mechanism_text,
                offer_id=offer_id,
                source_type="manual",
                evidence_type="mechanism_insight",
                confidence_score=0.9,
            )
            if result:
                observations.append({"type": "mechanism", "memory_ref": result.get("id")})

        # Retain CTA analysis
        cta = analysis.get("cta_analysis", {})
        if cta.get("primary_cta"):
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.OFFER,
                content=(
                    f"Primary CTA: {cta['primary_cta']}. "
                    f"Type: {cta.get('cta_type', 'n/a')}. "
                    f"Friction: {cta.get('friction_level', 'n/a')}. "
                    f"Risk reversal: {cta.get('risk_reversal', 'n/a')}."
                ),
                offer_id=offer_id,
                source_type="manual",
                evidence_type="offer_truth",
                confidence_score=0.95,
            )

        # Retain constraints
        for constraint in analysis.get("constraints", []):
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.OFFER,
                content=f"Constraint ({constraint.get('category', 'general')}): {constraint.get('constraint', '')}",
                offer_id=offer_id,
                source_type="manual",
                evidence_type="offer_truth",
                confidence_score=0.9,
                domain_risk_level="elevated" if constraint.get("severity") == "high" else "standard",
            )

        # Retain proof basis items
        for proof in analysis.get("proof_basis", []):
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.OFFER,
                content=f"Proof ({proof.get('proof_type', 'general')}): {proof.get('claim', '')}. Source: {proof.get('source', 'unspecified')}. Strength: {proof.get('strength', 'unknown')}.",
                offer_id=offer_id,
                source_type="manual",
                evidence_type="proof_claim",
                confidence_score=0.85,
            )

        # Retain buyer context
        buyer = analysis.get("buyer_context", {})
        if buyer.get("primary_audience"):
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.CORE,
                content=(
                    f"Target audience: {buyer['primary_audience']}. "
                    f"Awareness: {buyer.get('awareness_level', 'unknown')}. "
                    f"Motivation: {buyer.get('buying_motivation', 'unknown')}."
                ),
                offer_id=offer_id,
                source_type="manual",
                evidence_type="offer_truth",
                confidence_score=0.9,
            )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={"offer_analysis": analysis},
            observations=observations,
        )
