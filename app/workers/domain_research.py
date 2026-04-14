"""Domain Research Worker

Input:  News, reports, PubMed, regulation signals
Output: Domain developments and proof opportunities
Banks:  retain to research bank
Guard:  Every external claim must cite source
"""

from __future__ import annotations

from typing import Any

from app.services.acquisition.research import search_pubmed
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class DomainResearchWorker(BaseWorker):
    contract = SkillContract(
        skill_name="domain_research",
        purpose="Monitor domain developments, scientific evidence, and proof opportunities",
        accepted_input_types=["research_query", "domain_topic", "pubmed_query"],
        recall_scope=[BankType.RESEARCH],
        write_scope=[BankType.RESEARCH],
        steps=[
            "execute_research_queries",
            "filter_relevant_results",
            "extract_key_findings",
            "verify_source_citations",
            "retain_research_facts",
        ],
        quality_checks=[
            "every_claim_must_cite_source",
            "publication_date_must_be_recorded",
            "findings_must_distinguish_correlation_from_causation",
        ],
        escalation_rule="Escalate health claims that may require regulatory review",
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params
        observations: list[dict[str, Any]] = []
        requires_review = False

        queries = params.get("queries", [])
        domain = params.get("domain", "general")

        all_results: list[dict[str, Any]] = []

        for query in queries:
            if domain in ("health", "medical", "supplement"):
                pubmed_results = await search_pubmed(query, max_results=5)
                for r in pubmed_results:
                    result = await retain_observation(
                        account_id=account_id,
                        bank_type=BankType.RESEARCH,
                        content=f"Research finding: {r.title}. {r.summary}",
                        offer_id=offer_id,
                        source_type="research",
                        source_url=r.url,
                        evidence_type="research_finding",
                        confidence_score=0.8,
                        domain_risk_level="elevated" if domain == "health" else "standard",
                        extra_metadata=r.metadata,
                    )
                    if result:
                        observations.append({
                            "type": "research_finding",
                            "title": r.title,
                            "url": r.url,
                            "memory_ref": result.get("id"),
                        })
                    all_results.append({"source": "pubmed", "title": r.title, "url": r.url})

                if domain == "health":
                    requires_review = True

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "queries_executed": len(queries),
                "results_found": len(all_results),
                "results": all_results,
            },
            observations=observations,
            requires_review=requires_review,
        )
