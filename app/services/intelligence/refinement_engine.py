"""Multi-pass refinement engine — iterative improvement with grading.

The "push harder" system. Every generation task can run up to N passes
where each pass:
  1. Takes the current output
  2. Evaluates it against quality criteria (grading)
  3. Generates a refinement that addresses the weaknesses
  4. Grades again
  5. Repeats until quality threshold is met or max passes reached

This replaces the simple "generate once" pattern. Instead of:
  generate → done

It becomes:
  generate → grade → if below threshold: refine → grade → if below: refine → ...

The grading system scores each output on multiple dimensions.
Passing score and max passes are configurable per task type.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.llm.router import Capability, router

logger = logging.getLogger(__name__)


@dataclass
class GradingCriteria:
    """Defines how output quality is measured."""

    name: str
    description: str
    weight: float = 1.0   # how much this dimension counts
    min_score: int = 1     # minimum acceptable score
    max_score: int = 10


@dataclass
class GradeResult:
    """Result of grading one output."""

    scores: dict[str, int]         # criteria name → score (1-10)
    overall_score: float           # weighted average
    weaknesses: list[str]          # specific things to improve
    strengths: list[str]           # what's working (preserve these)
    passes_threshold: bool
    pass_number: int


@dataclass
class RefinementResult:
    """Final result after all refinement passes."""

    final_output: dict[str, Any]
    final_grade: GradeResult
    passes_completed: int
    all_grades: list[GradeResult]
    all_outputs: list[dict[str, Any]]
    improved: bool  # did it get better across passes?


# ── Standard grading criteria per task type ──────────────────────

HOOK_CRITERIA = [
    GradingCriteria("specificity", "Uses exact numbers, times, quotes — not vague language", 2.0),
    GradingCriteria("proof_anchor", "Hook is backed by a real proof element", 1.5),
    GradingCriteria("mechanism_connection", "Hook connects to the product's mechanism", 1.5),
    GradingCriteria("anti_generic", "Couldn't be used by a competitor unchanged", 2.0),
    GradingCriteria("emotional_impact", "Creates a visceral emotional response", 1.0),
    GradingCriteria("awareness_match", "Calibrated to the target awareness level", 1.0),
]

COPY_CRITERIA = [
    GradingCriteria("hook_strength", "Opening line stops the scroll", 2.0),
    GradingCriteria("mechanism_bridge", "Clear path from promise to product mechanism", 2.0),
    GradingCriteria("proof_density", "Claims are supported by evidence throughout", 1.5),
    GradingCriteria("anti_generic", "Couldn't be used by a competitor unchanged", 1.5),
    GradingCriteria("emotional_arc", "Designed emotional progression", 1.0),
    GradingCriteria("cta_earned", "Sufficient belief transfer before the ask", 1.0),
    GradingCriteria("compression", "Every sentence earns its place — no filler", 1.0),
]

IMAGE_CONCEPT_CRITERIA = [
    GradingCriteria("scroll_stop", "Would make someone stop scrolling at 11pm brain-dead", 2.0),
    GradingCriteria("native_feed", "Looks like organic content, not a polished ad", 2.0),
    GradingCriteria("emotional_trigger", "Creates a visceral reaction (curiosity, discomfort, WTF)", 1.5),
    GradingCriteria("uniqueness", "Different from typical ads in the category", 1.5),
    GradingCriteria("concept_diversity", "Concepts come from multiple SCRAWLS sources", 1.0),
    GradingCriteria("copy_alignment", "Image concept reinforces the ad copy", 1.0),
]

CRITERIA_MAP: dict[str, list[GradingCriteria]] = {
    "hook_generation": HOOK_CRITERIA,
    "copy_generation": COPY_CRITERIA,
    "image_concept_generation": IMAGE_CONCEPT_CRITERIA,
}

GRADE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "additionalProperties": {"type": "integer"},
        },
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "overall_assessment": {"type": "string"},
    },
}


class RefinementEngine:
    """Runs iterative refinement with grading."""

    async def refine(
        self,
        *,
        task_type: str,
        initial_output: dict[str, Any],
        system_prompt: str,
        context: str,
        max_passes: int = 3,
        threshold: float = 7.0,
        criteria: list[GradingCriteria] | None = None,
    ) -> RefinementResult:
        """Run the refinement loop.

        Args:
            task_type: hook_generation | copy_generation | image_concept_generation
            initial_output: The first-pass generation result
            system_prompt: The worker's system prompt (for refinement)
            context: Brief/evidence context (for refinement)
            max_passes: Maximum refinement passes (up to 10)
            threshold: Overall score needed to stop early (1-10 scale)
            criteria: Custom grading criteria (defaults to task-type standard)
        """
        max_passes = min(max_passes, 10)
        criteria = criteria or CRITERIA_MAP.get(task_type, HOOK_CRITERIA)

        all_outputs: list[dict[str, Any]] = [initial_output]
        all_grades: list[GradeResult] = []
        current_output = initial_output

        for pass_num in range(1, max_passes + 1):
            # Grade current output
            grade = await self._grade(current_output, criteria, pass_num)
            all_grades.append(grade)

            logger.info(
                "refinement.graded task=%s pass=%d score=%.1f threshold=%.1f",
                task_type, pass_num, grade.overall_score, threshold,
            )

            if grade.passes_threshold:
                return RefinementResult(
                    final_output=current_output,
                    final_grade=grade,
                    passes_completed=pass_num,
                    all_grades=all_grades,
                    all_outputs=all_outputs,
                    improved=pass_num > 1,
                )

            # Refine based on weaknesses
            if pass_num < max_passes:
                refined = await self._refine_pass(
                    current_output, grade, system_prompt, context, pass_num,
                )
                if refined and not refined.get("_parse_error"):
                    current_output = refined
                    all_outputs.append(refined)

        # Return best output across all passes
        best_idx = max(range(len(all_grades)), key=lambda i: all_grades[i].overall_score)

        return RefinementResult(
            final_output=all_outputs[best_idx],
            final_grade=all_grades[best_idx],
            passes_completed=max_passes,
            all_grades=all_grades,
            all_outputs=all_outputs,
            improved=best_idx > 0,
        )

    async def _grade(
        self,
        output: dict[str, Any],
        criteria: list[GradingCriteria],
        pass_number: int,
    ) -> GradeResult:
        """Grade an output against criteria."""
        output_text = json.dumps(output, indent=1, default=str)[:6000]
        criteria_text = "\n".join(
            f"- {c.name} (weight {c.weight}): {c.description}"
            for c in criteria
        )

        result = await router.generate(
            capability=Capability.COPY_ANALYSIS,
            system_prompt=(
                "You are a Creative Quality Grader. Score output against specific criteria.\n\n"
                "Rules:\n"
                "- Score each criterion 1-10 (1=terrible, 5=mediocre, 7=good, 9=excellent, 10=perfect)\n"
                "- Be HARSH. A score of 7+ should mean genuinely good work.\n"
                "- List specific weaknesses (things to fix) and strengths (things to keep)\n"
                "- Weaknesses should be actionable: 'hook uses generic language' not 'could be better'\n"
                "- A 5 is average. Most first-pass AI output is a 4-6. Getting to 8+ requires work."
            ),
            user_prompt=(
                f"Grade this output (pass {pass_number}):\n\n"
                f"CRITERIA:\n{criteria_text}\n\n"
                f"OUTPUT:\n{output_text}\n\n"
                f"Score each criterion 1-10. List specific weaknesses and strengths."
            ),
            temperature=0.2,
            max_tokens=3000,
            json_schema=GRADE_SCHEMA,
        )

        scores = result.get("scores", {})
        total_weight = sum(c.weight for c in criteria)
        weighted_sum = sum(
            scores.get(c.name, 5) * c.weight for c in criteria
        )
        overall = weighted_sum / max(total_weight, 1)

        return GradeResult(
            scores=scores,
            overall_score=overall,
            weaknesses=result.get("weaknesses", []),
            strengths=result.get("strengths", []),
            passes_threshold=overall >= 7.0,
            pass_number=pass_number,
        )

    async def _refine_pass(
        self,
        current_output: dict[str, Any],
        grade: GradeResult,
        system_prompt: str,
        context: str,
        pass_number: int,
    ) -> dict[str, Any]:
        """Generate a refined version addressing the graded weaknesses."""
        output_text = json.dumps(current_output, indent=1, default=str)[:5000]
        weaknesses_text = "\n".join(f"- {w}" for w in grade.weaknesses)
        strengths_text = "\n".join(f"- {s}" for s in grade.strengths)

        return await router.generate(
            capability=Capability.CREATIVE_GENERATION,
            system_prompt=system_prompt,
            user_prompt=(
                f"REFINEMENT PASS {pass_number + 1}\n\n"
                f"PREVIOUS OUTPUT (scored {grade.overall_score:.1f}/10):\n{output_text}\n\n"
                f"STRENGTHS (preserve these):\n{strengths_text}\n\n"
                f"WEAKNESSES (fix these):\n{weaknesses_text}\n\n"
                f"CONTEXT:\n{context[:3000]}\n\n"
                f"Generate an IMPROVED version that:\n"
                f"1. Keeps everything that's working (strengths)\n"
                f"2. Fixes every listed weakness\n"
                f"3. Pushes harder on specificity, proof anchoring, and emotional impact\n"
                f"Return the same JSON structure as the original."
            ),
            temperature=0.5 + (pass_number * 0.05),  # Slightly increase creativity each pass
            max_tokens=6000,
        )


# Module-level singleton
refinement_engine = RefinementEngine()
