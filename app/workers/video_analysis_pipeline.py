"""Video Analysis Pipeline Worker — full ad video processing.

Pipeline: Upload → Gemini analysis → timestamp validation →
          ffmpeg clip cutting → S3 storage → structured dataset

Input:  Video file (via S3 key or direct bytes) + optional performance data
Output: Timestamped storyboard, labeled clips, DR tags, training-ready JSONL
Banks:  write to CREATIVE
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.knowledge.base_training import get_training_context
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.services.llm.router import Capability, router
from app.services.storage.object_store import object_store
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)

VIDEO_STORYBOARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "total_duration_seconds": {"type": "number"},
        "overall_structure": {"type": "string"},
        "overall_dr_assessment": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clip_id": {"type": "integer"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "segment_type": {"type": "string"},
                    "spoken": {"type": "string"},
                    "visual": {"type": "string"},
                    "text_overlays": {"type": "array", "items": {"type": "string"}},
                    "dr_tags": {"type": "array", "items": {"type": "string"}},
                    "emotion": {"type": "string"},
                    "urgency": {"type": "string"},
                    "hook_type": {"type": "string"},
                    "camera_movement": {"type": "string"},
                    "transition_type": {"type": "string"},
                    "psychology_notes": {"type": "string"},
                },
            },
        },
        "hooks_identified": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hook_text": {"type": "string"},
                    "hook_type": {"type": "string"},
                    "timestamp": {"type": "string"},
                    "effectiveness_notes": {"type": "string"},
                },
            },
        },
        "visual_style_tags": {"type": "array", "items": {"type": "string"}},
        "format_classification": {"type": "string"},
        "awareness_level": {"type": "string"},
        "overall_effectiveness": {"type": "integer"},
    },
}


class VideoAnalysisPipelineWorker(BaseWorker):
    contract = SkillContract(
        skill_name="video_analysis_pipeline",
        purpose="Full video analysis: Gemini storyboard → timestamp validation → clip cutting → structured dataset",
        accepted_input_types=["video_file", "s3_key"],
        recall_scope=[BankType.CREATIVE, BankType.OFFER],
        write_scope=[BankType.CREATIVE],
        steps=[
            "download_video",
            "gemini_analyze_video",
            "validate_timestamps",
            "cut_clips",
            "upload_clips",
            "build_manifest",
            "retain_to_memory",
        ],
        quality_checks=[
            "every_scene_must_have_segment_type",
            "timestamps_must_be_validated",
            "clips_must_be_frame_accurate",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        s3_bucket = params.get("storage_bucket", "researcher-media")
        s3_key = params.get("storage_key", "")
        video_bytes = params.get("video_bytes")
        asset_id = params.get("asset_id", f"vid_{uuid4().hex[:12]}")

        # Step 1: Get video data
        if not video_bytes and s3_key:
            video_bytes = await object_store.download(s3_bucket, s3_key)

        if not video_bytes:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No video data — provide storage_key or video_bytes"],
            )

        # Write to temp file for processing
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            video_path = Path(tmp.name)

        try:
            # Get video duration via ffprobe
            duration = _get_video_duration(video_path)

            # Step 2: Gemini analysis — upload video and get storyboard
            # Upload to Gemini via router's video_uri support
            # For now, use the S3 presigned URL as the video reference
            training_context = get_training_context(include_examples=False)

            storyboard = await router.generate(
                capability=Capability.VIDEO_ANALYSIS,
                system_prompt=(
                    "You are a Direct Response Ad Video Analyst. Analyze this video "
                    "and produce a timestamped storyboard with DR tags.\n\n"
                    "For EVERY scene segment, provide:\n"
                    "- Exact start/end timestamps (HH:MM:SS.mmm)\n"
                    "- Segment type: HOOK, PROBLEM_AGITATE, SOLUTION, DEMO, SOCIAL_PROOF, "
                    "OBJECTION_HANDLE, CTA, TRANSITION, B_ROLL\n"
                    "- Spoken words (exact transcript)\n"
                    "- Visual description (what's shown)\n"
                    "- Text overlays (on-screen text)\n"
                    "- DR tags: pain_point, curiosity, pattern_interrupt, social_proof, urgency, "
                    "scarcity, free_trial, guarantee, authority, transformation, fear, FOMO\n"
                    "- Emotion and psychology notes\n"
                    "- Camera movement and transitions\n\n"
                    "Also identify: all hooks, overall format classification, visual style, "
                    "awareness level, and rate overall effectiveness (1-10).\n\n"
                    "The 13 reptile triggers: Ultra Real, Bizarre, Voyeur, Suffering/Pain, "
                    "Gory/Visceral, Sexual, Primal Fear, Inside Joke, Old/Vintage, Victory Lap, "
                    "Selfie/Demographic, Uncanny Object, Wildcard\n\n"
                    f"{training_context}"
                ),
                user_prompt=(
                    f"Analyze this {duration:.1f}-second ad video. "
                    f"Produce a complete timestamped storyboard with DR tags for every scene."
                ),
                temperature=0.2,
                max_tokens=8000,
                json_schema=VIDEO_STORYBOARD_SCHEMA,
                video_uri=params.get("video_uri") or s3_key,
            )

            if storyboard.get("_parse_error"):
                return WorkerOutput(
                    worker_name=self.contract.skill_name,
                    success=False,
                    errors=["Gemini analysis failed to parse"],
                )

            # Step 3: Validate timestamps with PySceneDetect
            scenes = storyboard.get("scenes", [])
            validated_scenes = await _validate_timestamps(video_path, scenes, duration)
            storyboard["scenes"] = validated_scenes

            # Step 4: Cut clips with ffmpeg
            clips_info: list[dict[str, Any]] = []
            for scene in validated_scenes:
                clip_id = scene.get("clip_id", 0)
                start = scene.get("start", "00:00:00.000")
                end = scene.get("end", "00:00:01.000")
                seg_type = scene.get("segment_type", "UNKNOWN")

                clip_filename = f"clip_{clip_id:03d}_{seg_type}.mp4"
                clip_path = video_path.parent / clip_filename

                success = _cut_clip(video_path, clip_path, start, end)
                if success and clip_path.exists():
                    # Upload clip to S3
                    clip_key = f"clips/{account_id}/{asset_id}/{clip_filename}"
                    clip_bytes = clip_path.read_bytes()
                    upload_result = await object_store.upload_media(
                        key=clip_key,
                        data=clip_bytes,
                        content_type="video/mp4",
                    )

                    clips_info.append({
                        "clip_id": clip_id,
                        "segment_type": seg_type,
                        "start": start,
                        "end": end,
                        "storage_key": clip_key,
                        "size_bytes": len(clip_bytes),
                        "dr_tags": scene.get("dr_tags", []),
                        "spoken": scene.get("spoken", ""),
                        "visual": scene.get("visual", ""),
                    })

                    clip_path.unlink(missing_ok=True)

            # Step 5: Build manifest
            manifest = {
                "asset_id": asset_id,
                "account_id": account_id,
                "offer_id": offer_id,
                "duration_seconds": duration,
                "storyboard": storyboard,
                "clips": clips_info,
                "clip_count": len(clips_info),
                "format": storyboard.get("format_classification"),
                "awareness_level": storyboard.get("awareness_level"),
                "effectiveness_score": storyboard.get("overall_effectiveness"),
            }

            # Upload manifest
            manifest_key = f"clips/{account_id}/{asset_id}/manifest.json"
            await object_store.upload_artifact(
                key=manifest_key,
                data=json.dumps(manifest, indent=2).encode(),
                content_type="application/json",
            )

            # Step 6: Retain to CREATIVE memory bank
            hooks = storyboard.get("hooks_identified", [])
            hook_summary = "; ".join(
                f"{h.get('hook_type', '?')}: {h.get('hook_text', '')[:80]}"
                for h in hooks[:5]
            )

            await retain_observation(
                account_id=account_id,
                bank_type=BankType.CREATIVE,
                content=(
                    f"Video analysis ({storyboard.get('format_classification', 'unknown')}): "
                    f"{len(validated_scenes)} scenes, {len(clips_info)} clips. "
                    f"Hooks: {hook_summary}. "
                    f"Style: {', '.join(storyboard.get('visual_style_tags', [])[:5])}. "
                    f"Awareness: {storyboard.get('awareness_level', '?')}. "
                    f"Effectiveness: {storyboard.get('overall_effectiveness', '?')}/10."
                ),
                offer_id=offer_id,
                source_type="video_analysis",
                evidence_type="creative_analysis",
                confidence_score=0.85,
                extra_metadata={
                    "asset_id": asset_id,
                    "manifest_key": manifest_key,
                    "format": storyboard.get("format_classification"),
                    "clip_count": len(clips_info),
                },
            )

            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=True,
                data={
                    "manifest": manifest,
                    "storyboard": storyboard,
                    "clips": clips_info,
                },
            )

        finally:
            video_path.unlink(missing_ok=True)


def _get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-show_entries",
                "format=duration", "-of", "csv=p=0", str(video_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _cut_clip(
    video_path: Path,
    output_path: Path,
    start: str,
    end: str,
) -> bool:
    """Cut a clip from video with frame-accurate boundaries."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video_path),
                "-ss", start, "-to", end,
                "-c:v", "libx264", "-c:a", "aac",
                "-avoid_negative_ts", "make_zero",
                str(output_path),
            ],
            capture_output=True, timeout=120,
        )
        return output_path.exists()
    except Exception as exc:
        logger.warning("ffmpeg.clip_failed start=%s end=%s error=%s", start, end, exc)
        return False


async def _validate_timestamps(
    video_path: Path,
    scenes: list[dict[str, Any]],
    duration: float,
) -> list[dict[str, Any]]:
    """Validate and snap Gemini timestamps to real scene cuts.

    Uses PySceneDetect's AdaptiveDetector to find real frame-level
    cut points, then snaps each Gemini timestamp to the nearest
    real cut within a 0.8s tolerance window.
    """
    SNAP_TOLERANCE = 0.8

    # Detect real scene cuts
    real_cuts: list[float] = [0.0]
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import AdaptiveDetector

        video = open_video(str(video_path))
        scene_manager = SceneManager()
        scene_manager.add_detector(AdaptiveDetector())
        scene_manager.detect_scenes(video)

        scene_list = scene_manager.get_scene_list()
        for scene_start, scene_end in scene_list:
            real_cuts.append(scene_start.get_seconds())
        real_cuts.append(duration)
        real_cuts = sorted(set(real_cuts))

    except ImportError:
        logger.warning("pyscenedetect not available — using Gemini timestamps as-is")
        return scenes
    except Exception as exc:
        logger.warning("scenedetect.failed error=%s — using Gemini timestamps", exc)
        return scenes

    # Snap each Gemini timestamp to nearest real cut
    for scene in scenes:
        start_sec = _ts_to_seconds(scene.get("start", "00:00:00.000"))
        end_sec = _ts_to_seconds(scene.get("end", "00:00:01.000"))

        snapped_start = _snap_to_nearest(start_sec, real_cuts, SNAP_TOLERANCE)
        snapped_end = _snap_to_nearest(end_sec, real_cuts, SNAP_TOLERANCE)

        # Fix inversions
        if snapped_end <= snapped_start:
            snapped_end = snapped_start + 0.5

        # Clamp to duration
        snapped_end = min(snapped_end, duration)

        scene["start"] = _seconds_to_ts(snapped_start)
        scene["end"] = _seconds_to_ts(snapped_end)
        scene["_snapped"] = True

    # Fix overlaps between consecutive scenes
    for i in range(1, len(scenes)):
        prev_end = _ts_to_seconds(scenes[i - 1].get("end", "0"))
        curr_start = _ts_to_seconds(scenes[i].get("start", "0"))
        if curr_start < prev_end:
            scenes[i]["start"] = scenes[i - 1]["end"]

    return scenes


def _snap_to_nearest(timestamp: float, cuts: list[float], tolerance: float) -> float:
    """Snap a timestamp to the nearest real cut within tolerance."""
    best = timestamp
    best_dist = tolerance + 1
    for cut in cuts:
        dist = abs(timestamp - cut)
        if dist < best_dist:
            best_dist = dist
            best = cut
    return best if best_dist <= tolerance else timestamp


def _ts_to_seconds(ts: str) -> float:
    """Convert HH:MM:SS.mmm to seconds."""
    try:
        parts = ts.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return float(ts)
    except (ValueError, IndexError):
        return 0.0


def _seconds_to_ts(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"
