"""Research Agent — contextual multi-step research planner.

Unlike domain_research (single-shot, you tell it what to search), the research
agent PLANS what to research based on brand context + known gaps. It:
  1. Recalls what the system already knows (OFFER, RESEARCH, VOC, CREATIVE, CULTURE)
  2. Decomposes the research goal into sub-questions
  3. Routes each sub-question to the best tool via the tool manifest
  4. Executes searches (free tools first, paid fallback)
  5. Extracts structured findings per source type
  6. Evaluates sufficiency — loops if insufficient (max 3 depth)
  7. Synthesizes cross-referenced findings
  8. Retains to appropriate Hindsight banks

Input:  research_goal (str) OR proof_gaps (from proof_inventory)
Output: Structured findings retained to RESEARCH/VOC/CULTURE banks
Banks:  recall from OFFER, RESEARCH, VOC, CREATIVE, CULTURE
        write to RESEARCH, VOC, CULTURE
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.knowledge.base_training import get_training_context
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.services.llm.router import Capability, router
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)

MAX_RESEARCH_DEPTH = 3

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sub_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "question_type": {"type": "string"},
                    "search_queries": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "string"},
                },
            },
        },
    },
}

SUFFICIENCY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sufficient": {"type": "boolean"},
        "gaps_remaining": {"type": "array", "items": {"type": "string"}},
        "follow_up_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "question_type": {"type": "string"},
                    "search_queries": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

SYNTHESIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "evidence_strength": {"type": "string"},
                    "source": {"type": "string"},
                    "source_type": {"type": "string"},
                    "confidence": {"type": "number"},
                    "bank_target": {"type": "string"},
                    "contradicted_by": {"type": "string"},
                    "regulatory_flag": {"type": "boolean"},
                },
            },
        },
        "proof_gaps_closed": {"type": "array", "items": {"type": "string"}},
        "proof_gaps_remaining": {"type": "array", "items": {"type": "string"}},
        "cultural_signals": {"type": "array", "items": {"type": "string"}},
        "audience_language_found": {"type": "array", "items": {"type": "string"}},
    },
}


class ResearchAgentWorker(BaseWorker):
    contract = SkillContract(
        skill_name="research_agent",
        purpose="Plan and execute contextual multi-step research based on brand context and known gaps",
        accepted_input_types=["research_goal", "proof_gaps", "cultural_scan"],
        recall_scope=[
            BankType.OFFER, BankType.RESEARCH, BankType.VOC,
            BankType.CREATIVE, BankType.CULTURE,
        ],
        write_scope=[BankType.RESEARCH, BankType.VOC, BankType.CULTURE],
        requires_approval=False,
        steps=[
            "recall_brand_context_and_known_research",
            "decompose_goal_into_sub_questions",
            "route_questions_to_tools",
            "execute_searches",
            "extract_findings",
            "evaluate_sufficiency",
            "synthesize_and_cross_reference",
            "retain_to_banks",
        ],
        quality_checks=[
            "every_finding_must_cite_source",
            "contradictions_must_be_flagged",
            "regulatory_content_must_be_flagged",
        ],
        escalation_rule="escalate on health claims or regulatory findings",
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        research_goal = params.get("research_goal", "")
        proof_gaps = params.get("proof_gaps", [])

        if proof_gaps and not research_goal:
            research_goal = "Fill the following proof gaps: " + "; ".join(proof_gaps)

        # Recall what the system already knows
        memories = await recall_for_worker(
            "research_agent", account_id,
            "research evidence study finding proof mechanism audience competitor trend",
            offer_id=offer_id,
            top_k=30,
        )

        known_context = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] "
            f"{m.get('content', '')[:300]}"
            for m in memories
        )

        # Step 1: PLAN — decompose into sub-questions
        plan = await self._plan(research_goal, known_context, proof_gaps)
        sub_questions = plan.get("sub_questions", [])

        if not sub_questions:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=True,
                data={"message": "No actionable research questions generated"},
            )

        # Step 2-4: EXECUTE searches for each sub-question
        all_raw_results: list[dict[str, Any]] = []
        for depth in range(MAX_RESEARCH_DEPTH):
            batch_results = await self._execute_batch(
                sub_questions, account_id, offer_id,
            )
            all_raw_results.extend(batch_results)

            # Step 5: EVALUATE sufficiency
            if depth < MAX_RESEARCH_DEPTH - 1:
                sufficiency = await self._evaluate_sufficiency(
                    research_goal, all_raw_results, proof_gaps,
                )
                if sufficiency.get("sufficient", True):
                    break

                follow_ups = sufficiency.get("follow_up_questions", [])
                if not follow_ups:
                    break
                sub_questions = follow_ups
                logger.info(
                    "research_agent.depth_increase depth=%d follow_ups=%d",
                    depth + 1, len(follow_ups),
                )

        # Step 6: SYNTHESIZE
        synthesis = await self._synthesize(
            research_goal, all_raw_results, known_context,
        )

        # Step 7: RETAIN to appropriate banks
        retained_count = await self._retain_findings(
            synthesis, account_id, offer_id,
        )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "research_goal": research_goal,
                "questions_asked": len(plan.get("sub_questions", [])),
                "total_raw_results": len(all_raw_results),
                "findings_count": len(synthesis.get("findings", [])),
                "retained_count": retained_count,
                "proof_gaps_closed": synthesis.get("proof_gaps_closed", []),
                "proof_gaps_remaining": synthesis.get("proof_gaps_remaining", []),
                "cultural_signals": synthesis.get("cultural_signals", []),
                "synthesis": synthesis,
            },
            requires_review=any(
                f.get("regulatory_flag")
                for f in synthesis.get("findings", [])
            ),
        )

    async def _plan(
        self,
        goal: str,
        known_context: str,
        proof_gaps: list[str],
    ) -> dict[str, Any]:
        """Decompose research goal into sub-questions with tool routing."""
        from app.services.acquisition.tool_manifest import TOOL_PRIORITY

        available_types = list(TOOL_PRIORITY.keys())
        gaps_text = "\n".join(f"- {g}" for g in proof_gaps) if proof_gaps else "None specified"

        return await router.generate(
            capability=Capability.STRATEGIC_REASONING,
            system_prompt=(
                "You are a Research Planner. Decompose a research goal into "
                "specific, searchable sub-questions. Each question must have:\n"
                "- question: the specific thing to search for\n"
                "- question_type: one of " + str(available_types) + "\n"
                "- search_queries: 2-3 actual search strings to use\n"
                "- priority: high | medium | low\n\n"
                "Focus on what's NOT already known. Don't re-research "
                "things that appear in the known context below."
            ),
            user_prompt=(
                f"RESEARCH GOAL:\n{goal}\n\n"
                f"KNOWN PROOF GAPS:\n{gaps_text}\n\n"
                f"WHAT THE SYSTEM ALREADY KNOWS ({len(known_context)} chars):\n"
                f"{known_context[:4000]}\n\n"
                f"Decompose into 3-8 sub-questions. Skip anything already covered."
            ),
            temperature=0.3,
            max_tokens=4000,
            json_schema=PLAN_SCHEMA,
        )

    async def _execute_batch(
        self,
        questions: list[dict[str, Any]],
        account_id: str,
        offer_id: str | None,
    ) -> list[dict[str, Any]]:
        """Execute searches for a batch of sub-questions."""
        results: list[dict[str, Any]] = []

        for q in questions[:8]:
            question_type = q.get("question_type", "audience_language")
            search_queries = q.get("search_queries", [q.get("question", "")])

            for query in search_queries[:3]:
                raw = await self._search(question_type, query)
                if raw:
                    results.append({
                        "question": q.get("question", ""),
                        "question_type": question_type,
                        "query": query,
                        "results": raw,
                    })

        return results

    async def _search(
        self,
        question_type: str,
        query: str,
    ) -> list[dict[str, Any]]:
        """Execute a single search using the best available tool."""
        from app.services.acquisition.tool_manifest import TOOL_PRIORITY, ToolName

        tool_chain = TOOL_PRIORITY.get(question_type, [])
        results: list[dict[str, Any]] = []

        for tool_name in tool_chain:
            try:
                if tool_name == ToolName.PUBMED:
                    results = await self._search_pubmed(query)
                elif tool_name == ToolName.SERPAPI_SCHOLAR:
                    results = await self._search_scholar(query)
                elif tool_name == ToolName.PRAW_REDDIT:
                    results = await self._search_reddit(query)
                elif tool_name == ToolName.GOOGLE_NEWS_RSS:
                    results = await self._search_news(query)
                elif tool_name == ToolName.GOOGLE_TRENDS:
                    results = await self._search_trends(query)
                elif tool_name == ToolName.TADDY_PODCASTS:
                    results = await self._search_podcasts(query)
                elif tool_name == ToolName.SCRAPECREATORS:
                    results = await self._search_scrapecreators(query)
                elif tool_name == ToolName.SCRAPLING:
                    results = await self._search_scrapling(query)
                elif tool_name in (ToolName.FDA_API, ToolName.FTC_API):
                    results = await self._search_regulatory(query, tool_name.value)
                elif tool_name == ToolName.BROWSER_HARNESS:
                    results = await self._search_browser_agent(query, question_type)

                if results:
                    logger.info(
                        "research_agent.search tool=%s query=%s results=%d",
                        tool_name.value, query[:50], len(results),
                    )
                    return results
            except Exception as exc:
                logger.debug(
                    "research_agent.tool_failed tool=%s query=%s error=%s",
                    tool_name.value, query[:50], exc,
                )
                continue

        return results

    async def _search_pubmed(self, query: str) -> list[dict[str, Any]]:
        from app.services.acquisition.research import search_pubmed
        return await search_pubmed(query, max_results=5)

    async def _search_scholar(self, query: str) -> list[dict[str, Any]]:
        from app.services.acquisition.connectors.google_scholar import scholar_client
        results = await scholar_client.search_papers(query, num=5)
        return [r.__dict__ if hasattr(r, "__dict__") else r for r in results]

    async def _search_reddit(self, query: str) -> list[dict[str, Any]]:
        from app.services.acquisition.connectors.reddit_client import reddit_client
        return await reddit_client.search(query, limit=10)

    async def _search_news(self, query: str) -> list[dict[str, Any]]:
        from app.services.acquisition.connectors.news_client import news_client
        return await news_client.search(query, max_results=10)

    async def _search_trends(self, query: str) -> list[dict[str, Any]]:
        from app.services.acquisition.connectors.trends_client import trends_client
        return await trends_client.interest_over_time(query)

    async def _search_podcasts(self, query: str) -> list[dict[str, Any]]:
        from app.services.acquisition.connectors.podcast_client import podcast_client
        return await podcast_client.search_episodes(query, limit=5)

    async def _search_scrapecreators(self, query: str) -> list[dict[str, Any]]:
        from app.services.acquisition.connectors.scrapecreators import scrapecreators_client
        result = await scrapecreators_client.reddit.search_posts(query, limit=10)
        return result.data

    async def _search_scrapling(self, query: str) -> list[dict[str, Any]]:
        from app.services.acquisition.connectors.web_scraper import web_scraper
        urls = await web_scraper.discover_forum_threads(
            f"https://www.google.com/search?q={query}",
            max_threads=5,
        )
        return [{"url": u, "type": "forum_thread"} for u in urls]

    async def _search_regulatory(
        self, query: str, source: str,
    ) -> list[dict[str, Any]]:
        from app.services.acquisition.connectors.regulatory_client import regulatory_client
        return await regulatory_client.search(query, source=source, limit=5)

    async def _search_browser_agent(
        self, query: str, question_type: str,
    ) -> list[dict[str, Any]]:
        """Use browser-harness as universal fallback for sites APIs can't reach."""
        from app.services.acquisition.connectors.browser_agent import browser_agent
        from urllib.parse import quote_plus

        # Construct a targeted search URL based on question type
        url = f"https://duckduckgo.com/?q={quote_plus(query)}&t=h_"
        result = await browser_agent.navigate_and_extract(
            url=url,
            goal=f"Extract {question_type} information related to: {query}. "
                 "Capture the most relevant results with their URLs and snippets.",
            capture_screenshot=False,
        )

        if not result.success:
            return []

        data = result.extracted_data
        if isinstance(data.get("data"), list):
            return data["data"]
        return [data]

    async def _evaluate_sufficiency(
        self,
        goal: str,
        raw_results: list[dict[str, Any]],
        proof_gaps: list[str],
    ) -> dict[str, Any]:
        results_summary = json.dumps(raw_results, default=str)[:6000]
        gaps_text = "\n".join(f"- {g}" for g in proof_gaps) if proof_gaps else "None"

        return await router.generate(
            capability=Capability.STRATEGIC_REASONING,
            system_prompt=(
                "Evaluate whether the research results are sufficient to "
                "answer the original goal. If not, generate follow-up "
                "questions to fill remaining gaps. Be specific."
            ),
            user_prompt=(
                f"GOAL: {goal}\n\n"
                f"PROOF GAPS TO CLOSE:\n{gaps_text}\n\n"
                f"RESULTS SO FAR:\n{results_summary}\n\n"
                f"Are these results sufficient?"
            ),
            temperature=0.2,
            max_tokens=3000,
            json_schema=SUFFICIENCY_SCHEMA,
        )

    async def _synthesize(
        self,
        goal: str,
        raw_results: list[dict[str, Any]],
        known_context: str,
    ) -> dict[str, Any]:
        results_text = json.dumps(raw_results, default=str)[:10000]

        return await router.generate(
            capability=Capability.SYNTHESIS,
            system_prompt=(
                "Synthesize research findings into structured output. For each finding:\n"
                "- claim: the specific claim or fact\n"
                "- evidence_strength: strong (RCT/meta-analysis) | moderate (observational) | weak (anecdotal)\n"
                "- source: where it came from\n"
                "- source_type: academic | review | forum | news | expert | competitor\n"
                "- confidence: 0-1\n"
                "- bank_target: research | voc | culture (which bank to store in)\n"
                "- contradicted_by: note if another finding contradicts this\n"
                "- regulatory_flag: true if this involves health/regulatory claims\n\n"
                "Cross-reference findings. Flag contradictions. Separate strong vs weak evidence."
            ),
            user_prompt=(
                f"RESEARCH GOAL: {goal}\n\n"
                f"RAW RESULTS:\n{results_text}\n\n"
                f"ALREADY KNOWN:\n{known_context[:3000]}\n\n"
                f"Synthesize into structured findings. Don't repeat what's already known."
            ),
            temperature=0.2,
            max_tokens=6000,
            json_schema=SYNTHESIS_SCHEMA,
        )

    async def _retain_findings(
        self,
        synthesis: dict[str, Any],
        account_id: str,
        offer_id: str | None,
    ) -> int:
        """Route findings to appropriate Hindsight banks."""
        retained = 0

        bank_map = {
            "research": BankType.RESEARCH,
            "voc": BankType.VOC,
            "culture": BankType.CULTURE,
        }

        for finding in synthesis.get("findings", []):
            bank_key = finding.get("bank_target", "research")
            bank_type = bank_map.get(bank_key, BankType.RESEARCH)

            content = (
                f"{finding.get('claim', '')} "
                f"[{finding.get('evidence_strength', 'unknown')}] "
                f"Source: {finding.get('source', 'unknown')}"
            )

            try:
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=bank_type,
                    content=content,
                    offer_id=offer_id,
                    source_type=finding.get("source_type", "research"),
                    source_url=finding.get("source", ""),
                    evidence_type="research_finding",
                    confidence_score=finding.get("confidence", 0.5),
                )
                if result:
                    retained += 1
            except Exception as exc:
                logger.debug(
                    "research_agent.retain_failed claim=%s error=%s",
                    finding.get("claim", "")[:50], exc,
                )

        return retained
