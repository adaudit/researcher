"""Fine-tuning data collection pipeline.

Captures input→output pairs from every worker execution to build
training datasets for fine-tuning custom models. The pipeline:

1. Intercepts worker runs and logs (system_prompt, user_prompt, response)
2. Captures quality scores from the evaluator
3. Filters for high-quality pairs (approved outputs, score ≥ 70)
4. Formats data for each provider's fine-tuning API
5. Supports distillation: train a fast model to mimic a powerful one

Why fine-tune:
- Extraction models: 10x cheaper, 3x faster, same accuracy on YOUR data
- Analysis models: learn your brand's strategic language and frameworks
- Platform extractors: learn platform-specific patterns from your corrections

The training loop:
  Deploy → Collect pairs → Filter quality → Fine-tune → Deploy improved → Repeat
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class TrainingPair:
    """One input→output pair for fine-tuning."""

    id: str
    worker_name: str
    capability: str          # which Capability was used
    provider: str            # which Provider generated this
    model: str               # which model generated this

    # The actual training data
    system_prompt: str
    user_prompt: str
    response: str            # raw model response

    # Quality signals
    quality_score: int = 0   # 0-100 from evaluator
    human_approved: bool = False
    human_corrections: str | None = None  # if human corrected the output

    # Metadata
    account_id: str = ""
    offer_id: str | None = None
    timestamp: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class TrainingDataset:
    """Collection of training pairs for one fine-tuning job."""

    name: str
    target_capability: str
    pairs: list[TrainingPair] = field(default_factory=list)
    min_quality_score: int = 70
    created_at: str = ""

    @property
    def qualified_pairs(self) -> list[TrainingPair]:
        """Pairs that meet the quality threshold."""
        return [p for p in self.pairs if p.quality_score >= self.min_quality_score]


class TrainingDataCollector:
    """Collects and stores training pairs from worker executions."""

    def __init__(self, storage_dir: str = "/tmp/researcher_training_data") -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._buffer: list[TrainingPair] = []

    def capture(
        self,
        *,
        worker_name: str,
        capability: str,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        quality_score: int = 0,
        account_id: str = "",
        offer_id: str | None = None,
        tags: list[str] | None = None,
    ) -> TrainingPair:
        """Capture a training pair from a worker execution."""
        pair = TrainingPair(
            id=f"tp_{uuid4().hex[:12]}",
            worker_name=worker_name,
            capability=capability,
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            quality_score=quality_score,
            account_id=account_id,
            offer_id=offer_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tags=tags or [],
        )

        self._buffer.append(pair)

        # Auto-flush every 100 pairs
        if len(self._buffer) >= 100:
            self.flush()

        logger.info(
            "training.pair_captured worker=%s quality=%d provider=%s",
            worker_name, quality_score, provider,
        )
        return pair

    def mark_approved(self, pair_id: str, corrections: str | None = None) -> None:
        """Mark a pair as human-approved, optionally with corrections."""
        for pair in self._buffer:
            if pair.id == pair_id:
                pair.human_approved = True
                pair.human_corrections = corrections
                if corrections:
                    pair.response = corrections  # Use corrected version for training
                break

    def flush(self) -> Path:
        """Write buffered pairs to disk."""
        if not self._buffer:
            return self._storage_dir

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filepath = self._storage_dir / f"pairs_{timestamp}.jsonl"

        with open(filepath, "a") as f:
            for pair in self._buffer:
                f.write(json.dumps(asdict(pair), default=str) + "\n")

        logger.info("training.flush pairs=%d path=%s", len(self._buffer), filepath)
        self._buffer.clear()
        return filepath

    def build_dataset(
        self,
        name: str,
        *,
        target_capability: str,
        worker_names: list[str] | None = None,
        min_quality: int = 70,
        only_approved: bool = False,
    ) -> TrainingDataset:
        """Build a filtered training dataset from stored pairs."""
        all_pairs = self._load_all_pairs()

        filtered = []
        for pair in all_pairs:
            if pair.quality_score < min_quality:
                continue
            if target_capability and pair.capability != target_capability:
                continue
            if worker_names and pair.worker_name not in worker_names:
                continue
            if only_approved and not pair.human_approved:
                continue
            filtered.append(pair)

        dataset = TrainingDataset(
            name=name,
            target_capability=target_capability,
            pairs=filtered,
            min_quality_score=min_quality,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(
            "training.dataset_built name=%s pairs=%d qualified=%d",
            name, len(filtered), len(dataset.qualified_pairs),
        )
        return dataset

    def export_anthropic_format(self, dataset: TrainingDataset) -> str:
        """Export dataset in Anthropic fine-tuning JSONL format."""
        filepath = self._storage_dir / f"{dataset.name}_anthropic.jsonl"

        with open(filepath, "w") as f:
            for pair in dataset.qualified_pairs:
                entry = {
                    "messages": [
                        {"role": "system", "content": pair.system_prompt},
                        {"role": "user", "content": pair.user_prompt},
                        {"role": "assistant", "content": pair.response},
                    ]
                }
                f.write(json.dumps(entry) + "\n")

        logger.info("training.exported format=anthropic path=%s pairs=%d", filepath, len(dataset.qualified_pairs))
        return str(filepath)

    def export_openai_format(self, dataset: TrainingDataset) -> str:
        """Export dataset in OpenAI fine-tuning JSONL format."""
        filepath = self._storage_dir / f"{dataset.name}_openai.jsonl"

        with open(filepath, "w") as f:
            for pair in dataset.qualified_pairs:
                entry = {
                    "messages": [
                        {"role": "system", "content": pair.system_prompt},
                        {"role": "user", "content": pair.user_prompt},
                        {"role": "assistant", "content": pair.response},
                    ]
                }
                f.write(json.dumps(entry) + "\n")

        logger.info("training.exported format=openai path=%s pairs=%d", filepath, len(dataset.qualified_pairs))
        return str(filepath)

    def export_gemini_format(self, dataset: TrainingDataset) -> str:
        """Export dataset in Google Gemini fine-tuning format."""
        filepath = self._storage_dir / f"{dataset.name}_gemini.jsonl"

        with open(filepath, "w") as f:
            for pair in dataset.qualified_pairs:
                entry = {
                    "systemInstruction": pair.system_prompt,
                    "contents": [
                        {"role": "user", "parts": [{"text": pair.user_prompt}]},
                        {"role": "model", "parts": [{"text": pair.response}]},
                    ],
                }
                f.write(json.dumps(entry) + "\n")

        logger.info("training.exported format=gemini path=%s pairs=%d", filepath, len(dataset.qualified_pairs))
        return str(filepath)

    def _load_all_pairs(self) -> list[TrainingPair]:
        """Load all stored training pairs."""
        pairs: list[TrainingPair] = []

        for filepath in sorted(self._storage_dir.glob("pairs_*.jsonl")):
            with open(filepath) as f:
                for line in f:
                    data = json.loads(line)
                    pairs.append(TrainingPair(**{
                        k: v for k, v in data.items()
                        if k in TrainingPair.__dataclass_fields__
                    }))

        # Also include buffered pairs
        pairs.extend(self._buffer)
        return pairs


# Module-level singleton
training_collector = TrainingDataCollector()
