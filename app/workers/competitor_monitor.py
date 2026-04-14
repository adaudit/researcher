"""Competitor Monitor Worker

Input:  Swipes, ad references, page snapshots
Output: Competitor themes and style changes
Banks:  retain to creative and research banks
Guard:  Must label freshness and source coverage
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class CompetitorMonitorWorker(BaseWorker):
    contract = SkillContract(
        skill_name="competitor_monitor",
        purpose="Track competitor creative themes, style shifts, and market positioning",
        accepted_input_types=["ad_reference", "page_snapshot", "swipe_file"],
        recall_scope=[BankType.CREATIVE, BankType.RESEARCH],
        write_scope=[BankType.CREATIVE, BankType.RESEARCH],
        steps=[
            "classify_competitor_assets",
            "extract_themes_and_angles",
            "detect_style_changes",
            "compare_with_prior_observations",
            "retain_competitive_signals",
        ],
        quality_checks=[
            "freshness_must_be_labeled",
            "source_coverage_must_be_stated",
            "competitor_identity_must_be_clear",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params
        observations: list[dict[str, Any]] = []

        competitors = params.get("competitors", [])

        for comp in competitors:
            name = comp.get("name", "unknown")
            assets = comp.get("assets", [])

            for asset in assets:
                theme = asset.get("theme", "")
                angle = asset.get("angle", "")
                source_url = asset.get("source_url", "")

                if theme:
                    result = await retain_observation(
                        account_id=account_id,
                        bank_type=BankType.CREATIVE,
                        content=f"Competitor ({name}) theme: {theme}. Angle: {angle}",
                        offer_id=offer_id,
                        source_type="manual",
                        source_url=source_url,
                        evidence_type="competitive_signal",
                        confidence_score=0.7,
                        extra_metadata={"competitor": name},
                    )
                    if result:
                        observations.append({
                            "type": "competitive_theme",
                            "competitor": name,
                            "memory_ref": result.get("id"),
                        })

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={"competitors_analyzed": len(competitors)},
            observations=observations,
        )
