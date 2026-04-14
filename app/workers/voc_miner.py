"""VOC Miner Worker

Input:  Comments, reviews, FAQs, tickets
Output: Pain clusters, desire language, objections
Banks:  retain to VOC bank
Guard:  Exact snippets must be preserved
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class VOCMinerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="voc_miner",
        purpose="Mine voice-of-customer data for pains, desires, objections, and exact language",
        accepted_input_types=["comment_dump", "review_dump", "faq_list", "support_tickets"],
        recall_scope=[BankType.VOC],
        write_scope=[BankType.VOC],
        steps=[
            "parse_raw_comments",
            "classify_sentiment_and_intent",
            "cluster_pain_themes",
            "extract_desire_language",
            "extract_objections",
            "preserve_exact_snippets",
            "retain_voc_observations",
        ],
        quality_checks=[
            "exact_customer_language_must_be_preserved",
            "clusters_must_have_minimum_evidence_count",
            "objections_must_be_real_not_inferred",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params
        observations: list[dict[str, Any]] = []

        comments = params.get("comments", [])
        source_url = params.get("source_url", "")
        artifact_id = params.get("artifact_id")

        pain_clusters: dict[str, list[str]] = {}
        desire_phrases: list[str] = []
        objections: list[str] = []

        for comment in comments:
            text = comment if isinstance(comment, str) else comment.get("text", "")
            if not text.strip():
                continue

            category, snippet = _classify_voc(text)

            if category == "pain":
                theme = _extract_theme(text)
                pain_clusters.setdefault(theme, []).append(snippet)
            elif category == "desire":
                desire_phrases.append(snippet)
            elif category == "objection":
                objections.append(snippet)

            # Retain every meaningful comment
            if category != "noise":
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.VOC,
                    content=f"Customer {category}: \"{snippet}\"",
                    offer_id=offer_id,
                    artifact_id=artifact_id,
                    source_type="upload",
                    source_url=source_url,
                    evidence_type=f"audience_{category}",
                    confidence_score=0.8,
                    extra_metadata={"exact_snippet": snippet, "category": category},
                )
                if result:
                    observations.append({
                        "type": category,
                        "snippet": snippet[:100],
                        "memory_ref": result.get("id"),
                    })

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "total_comments": len(comments),
                "pain_clusters": {k: len(v) for k, v in pain_clusters.items()},
                "desire_count": len(desire_phrases),
                "objection_count": len(objections),
                "pain_details": pain_clusters,
                "desires": desire_phrases,
                "objections": objections,
            },
            observations=observations,
        )


def _classify_voc(text: str) -> tuple[str, str]:
    text_lower = text.lower()
    snippet = text.strip()[:500]

    pain_signals = ["problem", "struggle", "frustrated", "annoyed", "hate", "wish",
                    "can't", "doesn't work", "disappointed", "pain", "suffering"]
    desire_signals = ["want", "need", "looking for", "hoping", "would love",
                      "dream", "finally", "perfect", "amazing", "love"]
    objection_signals = ["but", "however", "expensive", "scam", "doubt", "skeptic",
                         "doesn't seem", "too good", "worried", "concern", "trust"]

    if any(s in text_lower for s in objection_signals):
        return "objection", snippet
    if any(s in text_lower for s in pain_signals):
        return "pain", snippet
    if any(s in text_lower for s in desire_signals):
        return "desire", snippet
    if len(text.strip()) > 20:
        return "general", snippet
    return "noise", snippet


def _extract_theme(text: str) -> str:
    """Simple keyword-based theme extraction."""
    text_lower = text.lower()
    themes = {
        "side_effects": ["side effect", "reaction", "symptom"],
        "price": ["expensive", "cost", "price", "afford"],
        "effectiveness": ["doesn't work", "no results", "waste"],
        "trust": ["scam", "fake", "doubt", "trust"],
        "convenience": ["hard to use", "complicated", "confusing"],
    }
    for theme, keywords in themes.items():
        if any(k in text_lower for k in keywords):
            return theme
    return "general"
