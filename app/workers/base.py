"""Universal skill contract for all strategy workers.

Every worker conforms to one contract shape so the orchestrator can reason
about execution consistently. Workers should not chat with memory casually —
they invoke memory operations as explicit workflow steps.

Architecture: Extractors and Analysts are SEPARATE concerns.
- Extractors (app/workers/extractors/) pull data from raw sources
- Analysts (this level) reason about extracted data
- Both share this base contract

Contract fields:
  skill_name       — stable worker identifier
  purpose          — narrow scope statement
  accepted_inputs  — typed input objects only
  recall_scope     — allowed bank set and metadata filters
  write_scope      — allowed bank writes and whether approval is required
  steps            — deterministic stages
  output_schema    — exact JSON response shape
  quality_checks   — validation rules
  escalation_rule  — when human review is required
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.services.hindsight.banks import BankType

logger = logging.getLogger(__name__)


@dataclass
class WorkerInput:
    """Base input payload for all workers."""

    account_id: str
    offer_id: str | None = None
    artifact_ids: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerOutput:
    """Base output payload for all workers."""

    worker_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    observations: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    quality_warnings: list[str] = field(default_factory=list)
    requires_review: bool = False


@dataclass
class SkillContract:
    """Declarative description of a worker's capabilities and constraints."""

    skill_name: str
    purpose: str
    accepted_input_types: list[str]
    recall_scope: list[BankType]
    write_scope: list[BankType]
    requires_approval: bool = False
    steps: list[str] = field(default_factory=list)
    quality_checks: list[str] = field(default_factory=list)
    escalation_rule: str = "escalate on low confidence or regulated content"


class BaseWorker(ABC):
    """Abstract base class for all strategy workers.

    Subclasses must implement:
      - contract: class-level SkillContract
      - execute(): the worker's main logic
      - validate_output(): post-execution quality checks
    """

    contract: SkillContract

    @abstractmethod
    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        """Run the worker's primary task.

        Workers MUST:
          1. Only recall from banks in their contract's recall_scope.
          2. Only write to banks in their contract's write_scope.
          3. Produce typed output matching their output schema.
          4. Set requires_review=True when confidence is low or content
             is in a regulated category.
        """

    async def validate_output(self, output: WorkerOutput) -> WorkerOutput:
        """Run quality checks on the output. Override for custom checks."""
        if not output.data and output.success:
            output.quality_warnings.append("Worker reported success but produced no data")
        return output

    async def run(self, worker_input: WorkerInput) -> WorkerOutput:
        """Full execution pipeline: execute -> validate -> log."""
        logger.info(
            "worker.start name=%s account=%s offer=%s",
            self.contract.skill_name,
            worker_input.account_id,
            worker_input.offer_id,
        )
        try:
            output = await self.execute(worker_input)
            output = await self.validate_output(output)
        except Exception as exc:
            logger.exception("worker.failed name=%s", self.contract.skill_name)
            output = WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=[str(exc)],
            )

        logger.info(
            "worker.complete name=%s success=%s observations=%d warnings=%d",
            self.contract.skill_name,
            output.success,
            len(output.observations),
            len(output.quality_warnings),
        )
        return output
