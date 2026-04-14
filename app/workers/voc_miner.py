"""VOC Miner Worker — LLM-powered voice-of-customer intelligence.

Input:  Comments, reviews, FAQs, tickets
Output: Pain clusters, desire language, objections with exact snippets
Banks:  retain to VOC bank
Guard:  Exact snippets must be preserved
"""

from __future__ import annotations

from typing import Any

from app.prompts.systems import VOC_MINER_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.services.llm.client import ModelTier, llm_client
from app.services.llm.schemas import VOC_ANALYSIS_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class VOCMinerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="voc_miner",
        purpose="Mine voice-of-customer data for pains, desires, objections, and exact language",
        accepted_input_types=["comment_dump", "review_dump", "faq_list", "support_tickets"],
        recall_scope=[BankType.VOC],
        write_scope=[BankType.VOC],
        steps=[
            "assemble_raw_voc_data",
            "llm_mine_desires_pains_objections",
            "preserve_exact_snippets",
            "cluster_by_theme",
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

        if not comments:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No comments provided"],
            )

        # Format comments for analysis
        comment_text = "\n---\n".join(
            c if isinstance(c, str) else c.get("text", "")
            for c in comments
        )

        # LLM analysis — STANDARD for deep VOC mining
        analysis = await llm_client.generate(
            system_prompt=VOC_MINER_SYSTEM,
            user_prompt=(
                f"Analyze these {len(comments)} customer comments/reviews. "
                f"Extract desire clusters, pain clusters, objections, and language patterns.\n\n"
                f"COMMENTS:\n{comment_text}"
            ),
            tier=ModelTier.STANDARD,
            temperature=0.2,
            max_tokens=6000,
            json_schema=VOC_ANALYSIS_SCHEMA,
            context_documents=[comment_text] if len(comment_text) > 3000 else None,
        )

        if analysis.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse VOC analysis"],
            )

        # Retain desire clusters with exact phrases
        for cluster in analysis.get("desire_clusters", []):
            phrases = cluster.get("exact_phrases", [])
            result = await retain_observation(
                account_id=account_id,
                bank_type=BankType.VOC,
                content=(
                    f"Desire cluster: {cluster.get('theme', 'unspecified')} "
                    f"(intensity: {cluster.get('intensity', 'medium')}). "
                    f"Exact phrases: {'; '.join(phrases[:5])}"
                ),
                offer_id=offer_id,
                artifact_id=artifact_id,
                source_type="upload",
                source_url=source_url,
                evidence_type="audience_desire",
                confidence_score=0.85,
                extra_metadata={
                    "exact_phrases": phrases,
                    "frequency": cluster.get("frequency", 0),
                    "theme": cluster.get("theme"),
                },
            )
            if result:
                observations.append({
                    "type": "desire",
                    "theme": cluster.get("theme"),
                    "memory_ref": result.get("id"),
                })

        # Retain pain clusters
        for cluster in analysis.get("pain_clusters", []):
            phrases = cluster.get("exact_phrases", [])
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.VOC,
                content=(
                    f"Pain cluster: {cluster.get('theme', 'unspecified')} "
                    f"(intensity: {cluster.get('intensity', 'medium')}). "
                    f"Exact phrases: {'; '.join(phrases[:5])}"
                ),
                offer_id=offer_id,
                artifact_id=artifact_id,
                source_type="upload",
                source_url=source_url,
                evidence_type="audience_pain",
                confidence_score=0.85,
                extra_metadata={"exact_phrases": phrases, "theme": cluster.get("theme")},
            )

        # Retain objections
        for obj in analysis.get("objections", []):
            phrases = obj.get("exact_phrases", [])
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.VOC,
                content=(
                    f"Objection: {obj.get('objection', '')}. "
                    f"Underlying fear: {obj.get('underlying_fear', 'unknown')}. "
                    f"Exact phrases: {'; '.join(phrases[:3])}"
                ),
                offer_id=offer_id,
                artifact_id=artifact_id,
                source_type="upload",
                source_url=source_url,
                evidence_type="audience_objection",
                confidence_score=0.8,
                extra_metadata={"exact_phrases": phrases},
            )

        # Retain language patterns
        lang = analysis.get("language_patterns", {})
        if lang.get("words_they_use"):
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.VOC,
                content=(
                    f"Customer language patterns — "
                    f"Key words: {', '.join(lang['words_they_use'][:10])}. "
                    f"Metaphors: {', '.join(lang.get('metaphors', [])[:5])}. "
                    f"Emotional triggers: {', '.join(lang.get('emotional_triggers', [])[:5])}."
                ),
                offer_id=offer_id,
                source_type="upload",
                evidence_type="language_pattern",
                confidence_score=0.8,
            )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={"voc_analysis": analysis},
            observations=observations,
        )
