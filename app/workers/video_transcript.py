"""Video Transcript Worker

Input:  Embedded page video or direct media
Output: Transcript, scene markers, spoken claims, hooks
Banks:  retain transcript segments to page or creative bank
Guard:  Raw transcript must be stored first
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class VideoTranscriptWorker(BaseWorker):
    contract = SkillContract(
        skill_name="video_transcript",
        purpose="Transcribe video content and extract spoken claims, hooks, and proof",
        accepted_input_types=["video_url", "media_file", "embedded_video"],
        recall_scope=[BankType.LANDING_PAGE, BankType.CREATIVE],
        write_scope=[BankType.LANDING_PAGE, BankType.CREATIVE],
        steps=[
            "download_or_reference_media",
            "run_asr_transcription",
            "segment_by_topic",
            "extract_spoken_claims",
            "extract_spoken_hooks",
            "identify_proof_references",
            "identify_objection_handling",
            "retain_transcript_segments",
        ],
        quality_checks=[
            "raw_transcript_must_exist_before_analysis",
            "timestamps_must_be_accurate",
            "claims_must_reference_transcript_segment",
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

        spoken_claims: list[dict[str, Any]] = []
        spoken_hooks: list[dict[str, Any]] = []

        for chunk in transcript_chunks:
            text = chunk.get("text", "")
            start = chunk.get("start", 0)
            end = chunk.get("end", 0)

            # Retain each chunk as a transcript segment
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

            # Detect spoken claims
            if _contains_claim_language(text):
                spoken_claims.append({
                    "text": text,
                    "start": start,
                    "end": end,
                    "source_url": source_url,
                })

            # Detect hooks (typically at the start)
            if start < 30 and len(text) > 10:
                spoken_hooks.append({
                    "text": text,
                    "start": start,
                    "end": end,
                })

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "total_chunks": len(transcript_chunks),
                "spoken_claims": spoken_claims,
                "spoken_hooks": spoken_hooks,
                "source_url": source_url,
            },
            observations=observations,
        )


def _contains_claim_language(text: str) -> bool:
    signals = ["proven", "clinically", "study", "results show", "guaranteed",
               "scientifically", "doctor", "research", "evidence"]
    text_lower = text.lower()
    return any(s in text_lower for s in signals)
