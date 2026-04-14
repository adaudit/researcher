"""Landing Page Analyzer Worker

Input:  URL, HTML, screenshot
Output: Page structure, claims, proof inventory, friction map
Banks:  retain to page bank, recall offer bank
Guard:  Must separate visible claims from inference
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class LandingPageAnalyzerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="landing_page_analyzer",
        purpose="Analyze landing page structure, extract claims, proof, and identify friction",
        accepted_input_types=["page_capture", "html", "screenshot"],
        recall_scope=[BankType.LANDING_PAGE, BankType.OFFER],
        write_scope=[BankType.LANDING_PAGE],
        steps=[
            "parse_page_structure",
            "extract_headline_hierarchy",
            "identify_visible_claims",
            "inventory_proof_elements",
            "map_friction_points",
            "detect_cta_patterns",
            "recall_offer_context",
            "compare_claims_to_offer",
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
        offer_context = await recall_for_worker(
            "landing_page_analyzer",
            account_id,
            "offer mechanism CTA proof basis constraints",
            offer_id=offer_id,
            top_k=10,
        )

        # Extract headline hierarchy
        headlines = [b for b in text_blocks if b.get("tag", "").startswith("h")]
        page_structure = {
            "url": page_url,
            "headline_hierarchy": headlines,
            "total_text_blocks": len(text_blocks),
            "sections": _group_by_section(text_blocks),
        }

        # Extract claims (from headlines and strong text blocks)
        claims: list[dict[str, Any]] = []
        for block in text_blocks:
            text = block.get("text", "")
            if _looks_like_claim(text):
                claims.append({
                    "text": text,
                    "tag": block.get("tag"),
                    "section": block.get("parent_class"),
                    "type": "visible_claim",
                })

        # Identify proof elements
        proof_elements: list[dict[str, Any]] = []
        for block in text_blocks:
            text = block.get("text", "")
            if _looks_like_proof(text):
                proof_elements.append({
                    "text": text,
                    "section": block.get("parent_class"),
                    "proof_type": _classify_proof(text),
                })

        # Retain key observations
        for claim in claims[:20]:
            result = await retain_observation(
                account_id=account_id,
                bank_type=BankType.LANDING_PAGE,
                content=f"Landing page claim: {claim['text']}",
                offer_id=offer_id,
                artifact_id=artifact_id,
                source_type="crawler",
                source_url=page_url,
                evidence_type="landing_page_claim",
                confidence_score=0.85,
            )
            if result:
                observations.append({"type": "claim", "memory_ref": result.get("id")})

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "page_structure": page_structure,
                "claims": claims,
                "proof_elements": proof_elements,
                "offer_context_used": len(offer_context),
            },
            observations=observations,
        )


def _group_by_section(blocks: list[dict]) -> list[dict]:
    sections: dict[str, list] = {}
    for b in blocks:
        key = b.get("parent_class", "unknown")
        sections.setdefault(key, []).append(b)
    return [{"section": k, "blocks": v} for k, v in sections.items()]


def _looks_like_claim(text: str) -> bool:
    if len(text) < 10 or len(text) > 300:
        return False
    claim_signals = ["will", "can", "proven", "guaranteed", "results", "transform",
                     "discover", "secret", "breakthrough", "finally", "solution"]
    text_lower = text.lower()
    return any(s in text_lower for s in claim_signals)


def _looks_like_proof(text: str) -> bool:
    proof_signals = ["study", "clinical", "published", "doctor", "certified",
                     "tested", "verified", "%", "customers", "reviews", "rated",
                     "award", "patent", "research"]
    text_lower = text.lower()
    return any(s in text_lower for s in proof_signals)


def _classify_proof(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["study", "clinical", "research", "published"]):
        return "scientific"
    if any(w in text_lower for w in ["customer", "review", "testimonial", "rated"]):
        return "social"
    if any(w in text_lower for w in ["doctor", "certified", "expert", "award"]):
        return "authority"
    return "general"
