"""Landing page decomposition workflow.

Trigger: URL submission
Main Hindsight operations: retain, recall
Output: Page map, claims, proof, friction, transcript

Pipeline:
  1. Fetch rendered HTML and static HTML → raw page capture
  2. Parse visible content and DOM blocks → page map and text blocks
  3. Detect embedded video elements and media URLs → video asset registry
  4. Download or reference media asset → stored media object
  5. Run ASR and optional scene segmentation → transcript and scene markers
  6. Extract spoken claims, hooks, proof, objections, CTA → normalized observations
  7. Link transcript evidence back to page sections → auditable page intelligence
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from app.orchestrator.engine import build_step_log_entry, celery_app
from app.services.acquisition.page_crawler import fetch_page
from app.services.acquisition.transcript import (
    TranscriptResult,
    chunk_transcript,
    download_video,
    transcribe,
)
from app.workers.base import WorkerInput
from app.workers.landing_page_analyzer import LandingPageAnalyzerWorker
from app.workers.video_transcript import VideoTranscriptWorker

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.orchestrator.workflows.landing_page_decomposition.run_decomposition",
    bind=True,
)
def run_decomposition(
    self,
    account_id: str,
    offer_id: str,
    url: str,
    extract_video: bool = True,
) -> dict[str, Any]:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_decomposition_async(self.request.id, account_id, offer_id, url, extract_video)
    )


async def _run_decomposition_async(
    task_id: str,
    account_id: str,
    offer_id: str,
    url: str,
    extract_video: bool,
) -> dict[str, Any]:
    step_log: list[dict] = []
    results: dict[str, Any] = {}

    # Step 1-2: Fetch and parse page
    step_log.append(build_step_log_entry("page_fetch", "started"))
    try:
        page_capture = await fetch_page(url)
        results["page_capture"] = {
            "url": page_capture.url,
            "title": page_capture.title,
            "content_hash": page_capture.content_hash,
            "text_blocks_count": len(page_capture.text_blocks),
            "embedded_videos_count": len(page_capture.embedded_videos),
        }
        step_log.append(build_step_log_entry("page_fetch", "completed"))
    except Exception as exc:
        step_log.append(build_step_log_entry("page_fetch", "failed", str(exc)))
        return {"workflow_id": task_id, "status": "failed", "error": str(exc), "step_log": step_log}

    # Step 3: Analyze page structure
    step_log.append(build_step_log_entry("page_analysis", "started"))
    analyzer = LandingPageAnalyzerWorker()
    analysis_input = WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={
            "url": url,
            "text_blocks": page_capture.text_blocks,
            "artifact_id": f"art_{uuid4().hex[:8]}",
        },
    )
    analysis_result = await analyzer.run(analysis_input)
    results["page_analysis"] = analysis_result.data
    step_log.append(build_step_log_entry("page_analysis", "completed"))

    # Steps 4-7: Video processing
    if extract_video and page_capture.embedded_videos:
        step_log.append(build_step_log_entry("video_processing", "started"))
        transcript_results: list[dict[str, Any]] = []

        for video in page_capture.embedded_videos:
            video_url = video.get("source_url", "")
            if not video_url:
                continue

            try:
                # Download
                media_path = await download_video(video_url)

                # Transcribe
                transcript = await transcribe(media_path, source_url=video_url)

                # Chunk for memory retention
                chunks = chunk_transcript(transcript)

                # Run transcript worker
                transcript_worker = VideoTranscriptWorker()
                transcript_input = WorkerInput(
                    account_id=account_id,
                    offer_id=offer_id,
                    params={
                        "transcript_chunks": chunks,
                        "source_url": video_url,
                        "target_bank": "pages",
                    },
                )
                transcript_output = await transcript_worker.run(transcript_input)
                transcript_results.append(transcript_output.data)
            except Exception as exc:
                logger.warning("video.processing_failed url=%s error=%s", video_url, exc)
                transcript_results.append({"error": str(exc), "url": video_url})

        results["transcripts"] = transcript_results
        step_log.append(build_step_log_entry("video_processing", "completed"))

    return {
        "workflow_id": task_id,
        "status": "completed",
        "results": results,
        "step_log": step_log,
    }
