"""Video download and transcription service.

Steps 4-5 of the landing page processing pipeline:
  4. Download or reference media asset
  5. Run ASR and optional scene segmentation
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    start: float  # seconds
    end: float
    text: str
    topic: str | None = None
    speaker: str | None = None


@dataclass
class TranscriptResult:
    source_url: str
    language: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    full_text: str = ""
    duration_seconds: float = 0.0


async def download_video(url: str, *, output_dir: str | None = None) -> Path:
    """Download video using yt-dlp. Supports YouTube, Vimeo, Wistia, Loom,
    and direct media URLs.

    Returns path to downloaded media file.
    """
    out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    output_template = str(out_dir / "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--write-info-json",
        "-f", "bestaudio[ext=m4a]/bestaudio/best",
        "-o", output_template,
        url,
    ]

    logger.info("transcript.download url=%s", url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        logger.error("transcript.download_failed stderr=%s", result.stderr[:500])
        raise RuntimeError(f"yt-dlp failed: {result.stderr[:200]}")

    # Find the downloaded file
    files = list(out_dir.glob("*.*"))
    media_files = [f for f in files if f.suffix in (".m4a", ".mp4", ".webm", ".mp3", ".wav", ".opus")]
    if not media_files:
        raise FileNotFoundError(f"No media file found in {out_dir}")

    return media_files[0]


async def transcribe(
    media_path: Path,
    *,
    source_url: str = "",
    model_size: str = "base",
) -> TranscriptResult:
    """Transcribe audio using OpenAI Whisper (local model).

    For production, consider Whisper API or a faster engine like
    faster-whisper for reduced latency.
    """
    try:
        import whisper
    except ImportError:
        logger.warning("transcript.whisper_not_available — returning empty transcript")
        return TranscriptResult(source_url=source_url, language="en")

    logger.info("transcript.transcribe path=%s model=%s", media_path, model_size)
    model = whisper.load_model(model_size)
    result = model.transcribe(str(media_path))

    segments = [
        TranscriptSegment(
            start=seg["start"],
            end=seg["end"],
            text=seg["text"].strip(),
        )
        for seg in result.get("segments", [])
    ]

    return TranscriptResult(
        source_url=source_url,
        language=result.get("language", "en"),
        segments=segments,
        full_text=result.get("text", ""),
        duration_seconds=segments[-1].end if segments else 0.0,
    )


def chunk_transcript(
    transcript: TranscriptResult,
    chunk_duration_seconds: float = 60.0,
) -> list[dict[str, Any]]:
    """Chunk transcript into time-based windows for retention.

    Each chunk becomes a separate memory-ready payload.
    """
    if not transcript.segments:
        return []

    chunks: list[dict[str, Any]] = []
    current_chunk_start = 0.0
    current_texts: list[str] = []

    for seg in transcript.segments:
        current_texts.append(seg.text)

        if seg.end - current_chunk_start >= chunk_duration_seconds:
            chunks.append({
                "start": current_chunk_start,
                "end": seg.end,
                "text": " ".join(current_texts),
                "source_url": transcript.source_url,
            })
            current_chunk_start = seg.end
            current_texts = []

    # Flush remaining
    if current_texts:
        last_end = transcript.segments[-1].end
        chunks.append({
            "start": current_chunk_start,
            "end": last_end,
            "text": " ".join(current_texts),
            "source_url": transcript.source_url,
        })

    return chunks
