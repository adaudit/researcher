"""Copy Shape Police Worker

Input:  Draft copy plus strategy
Output: Flagged generic patterns and rewrite targets
Banks:  recall approved strategic outputs
Guard:  Must enforce anti-generic policy
"""

from __future__ import annotations

import re
from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

# Patterns that signal generic LLM-style copy
GENERIC_PATTERNS = [
    r"\bin today'?s (?:world|society|age|fast-paced)\b",
    r"\bunlock (?:the|your) (?:full |true )?potential\b",
    r"\bgame[- ]?changer\b",
    r"\brevolutionary\b",
    r"\bcutting[- ]?edge\b",
    r"\bseamless(?:ly)?\b",
    r"\bholistic\b",
    r"\bsynerg(?:y|istic|ize)\b",
    r"\bleverage\b",
    r"\btransformative\b",
    r"\bone[- ]?stop[- ]?shop\b",
    r"\bnext[- ]?level\b",
    r"\bworld[- ]?class\b",
    r"\bstate[- ]?of[- ]?the[- ]?art\b",
    r"\bparadigm[- ]?shift\b",
    r"\brobust\b",
    r"\bsupercharge\b",
    r"\bempowering\b",
    r"\bimagine (?:a world|if|being)\b",
    r"\bare you (?:tired|sick) of\b",
]


class CopyShapePoliceWorker(BaseWorker):
    contract = SkillContract(
        skill_name="copy_shape_police",
        purpose="Detect and flag generic patterns in draft copy, enforce anti-generic policy",
        accepted_input_types=["draft_copy", "strategy_reference"],
        recall_scope=[BankType.OFFER, BankType.CREATIVE],
        write_scope=[],
        steps=[
            "scan_for_generic_patterns",
            "check_proof_density",
            "check_mechanism_presence",
            "check_specificity_level",
            "recall_approved_strategy",
            "generate_rewrite_targets",
        ],
        quality_checks=[
            "must_enforce_anti_generic_policy",
            "flagged_patterns_must_include_alternatives",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        draft_text = params.get("draft_text", "")
        if not draft_text:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No draft text provided"],
            )

        # Scan for generic patterns
        flags: list[dict[str, Any]] = []
        for pattern in GENERIC_PATTERNS:
            matches = list(re.finditer(pattern, draft_text, re.IGNORECASE))
            for match in matches:
                flags.append({
                    "pattern": pattern,
                    "matched_text": match.group(),
                    "position": match.start(),
                    "context": draft_text[max(0, match.start() - 50):match.end() + 50],
                    "severity": "high",
                    "suggestion": "Replace with specific, evidence-backed language",
                })

        # Check specificity
        word_count = len(draft_text.split())
        specificity_score = max(0, 1.0 - (len(flags) / max(word_count / 50, 1)))

        # Recall strategy for suggested replacements
        strategy_context = await recall_for_worker(
            "copy_shape_police",
            account_id,
            "mechanism proof specific language evidence",
            offer_id=offer_id,
            top_k=10,
        )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "generic_flags": flags,
                "flag_count": len(flags),
                "word_count": word_count,
                "specificity_score": round(specificity_score, 2),
                "strategy_alternatives_available": len(strategy_context),
            },
        )
