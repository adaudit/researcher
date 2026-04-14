"""Landing Page Analyzer Worker — LLM-powered page decomposition.

Input:  URL, HTML, screenshot
Output: Page structure, claims, proof inventory, friction map
Banks:  retain to page bank, recall offer bank
Guard:  Must separate visible claims from inference
"""

from __future__ import annotations

from typing import Any

from app.prompts.systems import LANDING_PAGE_ANALYZER_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.services.llm.client import ModelTier, llm_client
from app.services.llm.schemas import LANDING_PAGE_ANALYSIS_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class LandingPageAnalyzerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="landing_page_analyzer",
        purpose="Analyze landing page structure, extract claims, proof, and identify friction",
        accepted_input_types=["page_capture", "html", "screenshot"],
        recall_scope=[BankType.LANDING_PAGE, BankType.OFFER],
        write_scope=[BankType.LANDING_PAGE],
        steps=[
            "recall_offer_context",
            "assemble_page_content",
            "llm_analyze_page_structure",
            "llm_extract_claims_and_proof",
            "llm_identify_friction",
            "retain_page_observations",
        ],
        quality_checks=[
            "claims_must_be_from_visible_page_text",
            "inferred_meaning_must_be_labeled_as_inference",
            "proof_elements_must_cite_page_section",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params
        observations: list[dict[str, Any]] = []

        text_blocks = params.get("text_blocks", [])
        page_url = params.get("url", "")
        artifact_id = params.get("artifact_id")

        # Recall offer context for comparison
        offer_memories = await recall_for_worker(
            "landing_page_analyzer",
            account_id,
            "offer mechanism CTA proof basis constraints target audience",
            offer_id=offer_id,
            top_k=10,
        )
        offer_context = "\n".join(
            f"- {m.get('content', '')}" for m in offer_memories
        ) if offer_memories else "No offer context available yet."

        # Assemble page content for analysis
        page_content = "\n".join(
            f"[{b.get('tag', 'p')}] {b.get('text', '')}"
            for b in text_blocks
            if b.get("text")
        )

        if not page_content:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No page content to analyze"],
            )

        # LLM analysis — STANDARD tier for thorough page decomposition
        analysis = await llm_client.generate(
            system_prompt=LANDING_PAGE_ANALYZER_SYSTEM,
            user_prompt=(
                f"Analyze this landing page.\n\n"
                f"PAGE URL: {page_url}\n\n"
                f"KNOWN OFFER CONTEXT:\n{offer_context}\n\n"
                f"PAGE CONTENT (tag + text):\n{page_content}"
            ),
            tier=ModelTier.STANDARD,
            temperature=0.2,
            max_tokens=6000,
            json_schema=LANDING_PAGE_ANALYSIS_SCHEMA,
            context_documents=[page_content] if len(page_content) > 2000 else None,
        )

        if analysis.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM page analysis"],
            )

        # Retain claims as observations
        for claim in analysis.get("claims", []):
            claim_text = claim.get("claim_text", "")
            if claim_text:
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.LANDING_PAGE,
                    content=(
                        f"Page claim ({claim.get('claim_type', 'general')}): \"{claim_text}\". "
                        f"Section: {claim.get('section', 'unknown')}. "
                        f"Supported by: {claim.get('supported_by', 'none')}. "
                        f"Risk: {claim.get('risk_level', 'standard')}."
                    ),
                    offer_id=offer_id,
                    artifact_id=artifact_id,
                    source_type="crawler",
                    source_url=page_url,
                    evidence_type="landing_page_claim",
                    confidence_score=0.9,
                )
                if result:
                    observations.append({"type": "claim", "memory_ref": result.get("id")})

        # Retain proof elements
        for proof in analysis.get("proof_elements", []):
            element = proof.get("element", "")
            if element:
                await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.LANDING_PAGE,
                    content=(
                        f"Page proof ({proof.get('proof_type', 'general')}): \"{element}\". "
                        f"Placement: {proof.get('placement', 'unknown')}. "
                        f"Effectiveness: {proof.get('effectiveness', 'unknown')}."
                    ),
                    offer_id=offer_id,
                    artifact_id=artifact_id,
                    source_type="crawler",
                    source_url=page_url,
                    evidence_type="proof_claim",
                    confidence_score=0.85,
                )

        # Retain friction points
        for friction in analysis.get("friction_points", []):
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.LANDING_PAGE,
                content=(
                    f"Friction ({friction.get('impact', 'medium')}): {friction.get('friction', '')}. "
                    f"Location: {friction.get('location', 'unknown')}. "
                    f"Fix: {friction.get('fix', 'not specified')}."
                ),
                offer_id=offer_id,
                artifact_id=artifact_id,
                source_type="crawler",
                source_url=page_url,
                evidence_type="friction_point",
                confidence_score=0.8,
            )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={"page_analysis": analysis},
            observations=observations,
        )
