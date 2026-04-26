"""Landing Page Analyzer Worker — multi-model page decomposition.

Uses Gemini for screenshot visual analysis (layout, design, trust signals)
and Claude for strategic text analysis (claims, proof, belief transfer).
Extraction frameworks define exactly what to look for.

Input:  URL, HTML, screenshot
Output: Page structure, claims, proof inventory, friction map
Banks:  retain to page bank, recall offer bank
Guard:  Must separate visible claims from inference
"""

from __future__ import annotations

import logging
from typing import Any

from app.knowledge.base_training import get_training_context
from app.knowledge.extraction_frameworks import get_framework_prompt
from app.prompts.systems import LANDING_PAGE_ANALYZER_SYSTEM
from app.services.hindsight.banks import BankType

logger = logging.getLogger(__name__)
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.services.llm.router import Capability, router
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
            "gemini_visual_analysis",
            "claude_strategic_analysis",
            "merge_visual_and_text",
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
        screenshot = params.get("screenshot")  # bytes

        # ── Recall offer context ──
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

        # Assemble page text
        page_content = "\n".join(
            f"[{b.get('tag', 'p')}] {b.get('text', '')}"
            for b in text_blocks if b.get("text")
        )

        if not page_content:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No page content to analyze"],
            )

        # ── Step 1: Visual analysis via Gemini (if screenshot available) ──
        visual_analysis: dict[str, Any] = {}
        if screenshot:
            try:
                visual_analysis = await router.generate(
                    capability=Capability.IMAGE_ANALYSIS,
                    system_prompt=(
                        "You are a landing page visual analyst. "
                        "Analyze this page screenshot for design and trust signals.\n\n"
                        "Extract: layout structure, visual hierarchy, color psychology, "
                        "trust signals (badges, seals, photos), CTA button design, "
                        "above-fold content, visual proof elements, "
                        "and any design friction (clutter, confusing layout, hard-to-find CTA)."
                    ),
                    user_prompt="Analyze this landing page screenshot for visual persuasion elements.",
                    images=[screenshot],
                    temperature=0.2,
                    max_tokens=3000,
                    json_schema={
                        "type": "object",
                        "properties": {
                            "layout_assessment": {"type": "string"},
                            "visual_hierarchy": {"type": "string"},
                            "trust_signals": {"type": "array", "items": {"type": "string"}},
                            "cta_design": {"type": "object", "properties": {
                                "visibility": {"type": "string"},
                                "color_contrast": {"type": "string"},
                                "placement": {"type": "string"},
                            }},
                            "above_fold_assessment": {"type": "string"},
                            "visual_proof_elements": {"type": "array", "items": {"type": "string"}},
                            "design_friction": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                )
            except Exception as exc:
                # Visual analysis is supplementary — fall back to text-only
                # analysis below. Log so model/quota issues are visible.
                logger.warning(
                    "landing_page.visual_analysis_failed error=%s", exc,
                )
                visual_analysis = {"note": "Visual analysis unavailable"}

        # ── Step 2: Strategic text analysis via Claude ──
        training_context = get_training_context(include_examples=True)
        extraction_framework = get_framework_prompt("landing_page")

        analysis = await router.generate(
            capability=Capability.STRATEGIC_REASONING,
            system_prompt=(
                LANDING_PAGE_ANALYZER_SYSTEM + "\n\n"
                + training_context + "\n\n"
                + extraction_framework
            ),
            user_prompt=(
                f"Analyze this landing page using the extraction framework.\n\n"
                f"PAGE URL: {page_url}\n\n"
                f"KNOWN OFFER CONTEXT:\n{offer_context}\n\n"
                f"PAGE CONTENT (tag + text):\n{page_content}"
            ),
            temperature=0.2,
            max_tokens=6000,
            json_schema=LANDING_PAGE_ANALYSIS_SCHEMA,
            context_documents=[training_context, extraction_framework],
        )

        if analysis.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM page analysis"],
            )

        # Merge visual analysis into result
        if visual_analysis and not visual_analysis.get("note"):
            analysis["visual_analysis"] = visual_analysis

        # ── Step 3: Retain observations ──
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
