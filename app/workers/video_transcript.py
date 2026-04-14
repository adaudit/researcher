"""Video Transcript Worker — multi-model video analysis.

Uses Gemini for video understanding (visual analysis, scene detection)
and Claude for strategic extraction (claims, hooks, proof).

Input:  Embedded page video or direct media
Output: Transcript, visual analysis, spoken claims, hooks
Banks:  retain transcript segments to page or creative bank
Guard:  Raw transcript must be stored first
"""

from __future__ import annotations

from typing import Any

from app.knowledge.base_training import get_training_context
from app.knowledge.extraction_frameworks import get_framework_prompt
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.services.llm.router import Capability, router
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class VideoTranscriptWorker(BaseWorker):
    contract = SkillContract(
        skill_name="video_transcript",
        purpose="Transcribe and analyze video content for strategic elements using multimodal AI",
        accepted_input_types=["video_url", "media_file", "embedded_video"],
        recall_scope=[BankType.LANDING_PAGE, BankType.CREATIVE],
        write_scope=[BankType.LANDING_PAGE, BankType.CREATIVE],
        steps=[
            "download_or_reference_media",
            "gemini_visual_analysis",
            "run_asr_transcription",
            "claude_strategic_extraction",
            "retain_transcript_segments",
        ],
        quality_checks=[
            "raw_transcript_must_exist_before_analysis",
            "timestamps_must_be_accurate",
            "claims_must_reference_transcript_segment",
            "visual_proof_elements_must_be_noted",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params
        observations: list[dict[str, Any]] = []

        transcript_chunks = params.get("transcript_chunks", [])
        source_url = params.get("source_url", "")
        target_bank = BankType(params.get("target_bank", BankType.LANDING_PAGE.value))
        artifact_id = params.get("artifact_id")
        video_uri = params.get("video_uri")  # For Gemini direct video analysis

        # ── Step 1: Gemini visual analysis (if video URI available) ──
        visual_analysis: dict[str, Any] = {}
        if video_uri:
            try:
                visual_analysis = await router.generate(
                    capability=Capability.VIDEO_ANALYSIS,
                    system_prompt=(
                        "You are a video analysis specialist for marketing research. "
                        "Analyze this video for persuasion elements.\n\n"
                        + get_framework_prompt("video")
                    ),
                    user_prompt=(
                        "Analyze this video. Extract:\n"
                        "1. Opening hook technique and timestamp\n"
                        "2. All visual proof elements (graphs, before/after, certifications)\n"
                        "3. Speaker authority signals\n"
                        "4. Emotional beats with timestamps\n"
                        "5. Mechanism reveal moment\n"
                        "6. B-roll and visual metaphors used\n"
                        "7. Pacing assessment — where would viewers drop off?\n\n"
                        "Return structured JSON."
                    ),
                    video_uri=video_uri,
                    temperature=0.2,
                    max_tokens=4000,
                    json_schema={
                        "type": "object",
                        "properties": {
                            "opening_hook": {"type": "object", "properties": {
                                "technique": {"type": "string"},
                                "timestamp": {"type": "string"},
                                "text": {"type": "string"},
                            }},
                            "visual_proof_elements": {"type": "array", "items": {"type": "object", "properties": {
                                "element": {"type": "string"},
                                "timestamp": {"type": "string"},
                                "proof_type": {"type": "string"},
                            }}},
                            "emotional_beats": {"type": "array", "items": {"type": "object", "properties": {
                                "emotion": {"type": "string"},
                                "trigger": {"type": "string"},
                                "timestamp": {"type": "string"},
                            }}},
                            "mechanism_reveal": {"type": "object", "properties": {
                                "timestamp": {"type": "string"},
                                "method": {"type": "string"},
                                "clarity": {"type": "string"},
                            }},
                            "pacing_assessment": {"type": "string"},
                            "drop_off_risk_points": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                )
            except Exception as exc:
                visual_analysis = {"error": str(exc), "note": "Video analysis unavailable — using transcript only"}

        # ── Step 2: Strategic extraction from transcript (Claude) ──
        transcript_text = "\n".join(
            f"[{c.get('start', 0):.0f}s-{c.get('end', 0):.0f}s] {c.get('text', '')}"
            for c in transcript_chunks
        )

        strategic_extraction: dict[str, Any] = {}
        if transcript_text:
            training_context = get_training_context(include_examples=True)

            strategic_extraction = await router.generate(
                capability=Capability.SYNTHESIS,
                system_prompt=(
                    "You are a video transcript strategist extracting "
                    "marketing intelligence from spoken content.\n\n"
                    + training_context + "\n\n"
                    + get_framework_prompt("video")
                ),
                user_prompt=(
                    f"Analyze this video transcript for strategic elements.\n\n"
                    f"TRANSCRIPT:\n{transcript_text}\n\n"
                    f"Extract spoken claims, hooks, proof references, "
                    f"objection handling, and mechanism explanations. "
                    f"Preserve exact quotes with timestamps."
                ),
                temperature=0.2,
                max_tokens=5000,
                context_documents=[training_context],
                json_schema={
                    "type": "object",
                    "properties": {
                        "spoken_claims": {"type": "array", "items": {"type": "object", "properties": {
                            "text": {"type": "string"},
                            "timestamp": {"type": "string"},
                            "claim_type": {"type": "string"},
                            "proof_support": {"type": "string"},
                        }}},
                        "hooks": {"type": "array", "items": {"type": "object", "properties": {
                            "text": {"type": "string"},
                            "timestamp": {"type": "string"},
                            "hook_type": {"type": "string"},
                        }}},
                        "mechanism_explanations": {"type": "array", "items": {"type": "object", "properties": {
                            "text": {"type": "string"},
                            "timestamp": {"type": "string"},
                            "clarity": {"type": "string"},
                        }}},
                        "objection_handling": {"type": "array", "items": {"type": "object", "properties": {
                            "objection": {"type": "string"},
                            "response": {"type": "string"},
                            "timestamp": {"type": "string"},
                        }}},
                    },
                },
            )

        # ── Step 3: Retain observations ──
        # Retain transcript chunks
        for chunk in transcript_chunks:
            text = chunk.get("text", "")
            start = chunk.get("start", 0)
            end = chunk.get("end", 0)

            result = await retain_observation(
                account_id=account_id,
                bank_type=target_bank,
                content=f"Transcript [{start:.0f}s-{end:.0f}s]: {text}",
                offer_id=offer_id,
                artifact_id=artifact_id,
                source_type="transcript",
                source_url=source_url,
                evidence_type="transcript_highlight",
                confidence_score=0.75,
                extra_metadata={"start": start, "end": end},
            )
            if result:
                observations.append({
                    "type": "transcript_segment",
                    "start": start,
                    "end": end,
                    "memory_ref": result.get("id"),
                })

        # Retain spoken claims
        for claim in strategic_extraction.get("spoken_claims", []):
            await retain_observation(
                account_id=account_id,
                bank_type=target_bank,
                content=f"Spoken claim: \"{claim.get('text', '')}\" at {claim.get('timestamp', '?')}. Type: {claim.get('claim_type', 'general')}.",
                offer_id=offer_id,
                artifact_id=artifact_id,
                source_type="transcript",
                source_url=source_url,
                evidence_type="proof_claim",
                confidence_score=0.8,
            )

        # Retain visual proof elements (from Gemini)
        for vp in visual_analysis.get("visual_proof_elements", []):
            await retain_observation(
                account_id=account_id,
                bank_type=target_bank,
                content=f"Visual proof ({vp.get('proof_type', 'general')}): {vp.get('element', '')} at {vp.get('timestamp', '?')}",
                offer_id=offer_id,
                artifact_id=artifact_id,
                source_type="transcript",
                source_url=source_url,
                evidence_type="proof_claim",
                confidence_score=0.7,
            )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "visual_analysis": visual_analysis,
                "strategic_extraction": strategic_extraction,
                "total_chunks": len(transcript_chunks),
                "source_url": source_url,
            },
            observations=observations,
        )
