"""Output quality scoring and self-evaluation system.

Every strategy output gets scored before publication. The evaluator
uses a separate LLM call (independent of the generation call) to
assess quality — this prevents the generator from grading its own work.

Scores are on a 0-100 scale with explicit criteria.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.llm.client import ModelTier, llm_client

logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    overall: int  # 0-100
    specificity: int  # 0-100: are claims specific or generic?
    evidence_coverage: int  # 0-100: how much is backed by evidence?
    proof_density: int  # 0-100: proof elements per claim
    mechanism_presence: int  # 0-100: is the mechanism clear?
    anti_generic: int  # 0-100: absence of generic language
    actionability: int  # 0-100: can someone act on this output?
    flags: list[str] = field(default_factory=list)
    recommendation: str = ""  # approve | revise | reject


EVALUATION_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {"type": "integer"},
        "specificity_score": {"type": "integer"},
        "evidence_coverage_score": {"type": "integer"},
        "proof_density_score": {"type": "integer"},
        "mechanism_presence_score": {"type": "integer"},
        "anti_generic_score": {"type": "integer"},
        "actionability_score": {"type": "integer"},
        "flags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommendation": {"type": "string"},
        "reasoning": {"type": "string"},
    },
}


async def evaluate_output(
    output_type: str,
    output_content: dict[str, Any],
    *,
    evidence_count: int = 0,
    context: str = "",
) -> QualityScore:
    """Evaluate a strategy output independently.

    Uses STANDARD tier (not the same model that generated the output)
    to provide independent quality assessment.
    """
    import json

    content_str = json.dumps(output_content, indent=1, default=str)[:6000]

    result = await llm_client.generate(
        system_prompt=(
            "You are an independent quality evaluator for creative strategy outputs. "
            "You did NOT create this output — you are reviewing it objectively.\n\n"
            "Score each dimension 0-100:\n"
            "- Specificity: Are claims specific to this offer, or could they apply to any competitor?\n"
            "- Evidence coverage: What percentage of assertions are backed by cited evidence?\n"
            "- Proof density: Is there sufficient proof for the claims being made?\n"
            "- Mechanism presence: Is the offer's mechanism clearly explained and connected?\n"
            "- Anti-generic: Is the language specific and concrete, or full of buzzwords and filler?\n"
            "- Actionability: Could a copywriter use this output to write better copy immediately?\n\n"
            "Recommendation: 'approve' (score >= 70), 'revise' (40-69), 'reject' (< 40)"
        ),
        user_prompt=(
            f"Evaluate this {output_type} output.\n\n"
            f"Evidence items used: {evidence_count}\n"
            f"Context: {context}\n\n"
            f"OUTPUT:\n{content_str}"
        ),
        tier=ModelTier.STANDARD,
        temperature=0.1,
        max_tokens=2000,
        json_schema=EVALUATION_SCHEMA,
    )

    if result.get("_parse_error"):
        logger.warning("quality.evaluation_parse_failed output_type=%s", output_type)
        return QualityScore(
            overall=50,
            specificity=50,
            evidence_coverage=50,
            proof_density=50,
            mechanism_presence=50,
            anti_generic=50,
            actionability=50,
            flags=["Evaluation parse failed — manual review required"],
            recommendation="revise",
        )

    return QualityScore(
        overall=result.get("overall_score", 50),
        specificity=result.get("specificity_score", 50),
        evidence_coverage=result.get("evidence_coverage_score", 50),
        proof_density=result.get("proof_density_score", 50),
        mechanism_presence=result.get("mechanism_presence_score", 50),
        anti_generic=result.get("anti_generic_score", 50),
        actionability=result.get("actionability_score", 50),
        flags=result.get("flags", []),
        recommendation=result.get("recommendation", "revise"),
    )


async def evaluate_and_gate(
    output_type: str,
    output_content: dict[str, Any],
    *,
    evidence_count: int = 0,
    min_score: int = 60,
    context: str = "",
) -> tuple[QualityScore, bool]:
    """Evaluate and return (score, passes_gate).

    Used in workflows to automatically gate publications.
    """
    score = await evaluate_output(
        output_type,
        output_content,
        evidence_count=evidence_count,
        context=context,
    )

    passes = score.overall >= min_score and score.recommendation != "reject"

    logger.info(
        "quality.gate output_type=%s overall=%d recommendation=%s passes=%s",
        output_type,
        score.overall,
        score.recommendation,
        passes,
    )

    return score, passes
