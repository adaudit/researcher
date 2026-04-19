"""Skill files system — per-account learnable knowledge that evolves.

Skills are structured markdown that workers load as context. Unlike
primers (which are examples of winning output), skills are KNOWLEDGE
about how to produce winning output for this specific business.

Example skills:
  - "Hook patterns that work for this audience" (updated when hooks win/lose)
  - "Visual styles this account responds to" (updated from ad performance)
  - "Awareness level distribution" (updated from coverage matrix results)
  - "Proof strategies that convert" (updated from landing page analysis)

Skills evolve through two mechanisms:
  1. Performance feedback: when ads with specific attributes perform well,
     the relevant skill gets updated with that learning
  2. Reflection promotion: when memory_reflection surfaces a durable pattern,
     it can be promoted into a skill file

Skills exist at two levels:
  - Per-account: specific to one business (stored in account SKILLS bank)
  - Global: cross-business patterns (stored in GLOBAL bank, loaded by all)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.services.hindsight.banks import BankType, bank_id_for
from app.services.hindsight.client import hindsight_client
from app.services.hindsight.memory import retain_observation
from app.services.llm.router import Capability, router

logger = logging.getLogger(__name__)


class SkillDomain(str, Enum):
    """Domains that skills can cover."""

    HOOKS = "hooks"                  # What hook patterns work
    COPY = "copy"                    # What copy approaches work
    VISUALS = "visuals"              # What visual styles work
    PROOF = "proof"                  # What proof strategies convert
    AUDIENCE = "audience"            # Audience behavior patterns
    FORMAT = "format"                # What ad formats perform
    AWARENESS = "awareness"          # Awareness level tactics
    MECHANISM = "mechanism"          # How to present the mechanism
    OBJECTIONS = "objections"        # How to handle objections
    CREATIVE_DIVERSITY = "diversity" # Coverage patterns and gaps


@dataclass
class SkillFile:
    """A single learnable skill."""

    domain: SkillDomain
    account_id: str
    content: str
    version: int = 1
    learnings_count: int = 0
    last_updated: str = ""
    memory_id: str | None = None


SKILL_UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "updated_skill": {"type": "string"},
        "changes_made": {
            "type": "array",
            "items": {"type": "string"},
        },
        "confidence": {"type": "number"},
    },
}


class SkillManager:
    """Manages per-account skill files that learn and evolve."""

    async def get_skill(
        self,
        account_id: str,
        domain: SkillDomain,
    ) -> str | None:
        """Recall the current skill file for a domain."""
        bank_id = bank_id_for(account_id, BankType.SKILLS)
        try:
            results = await hindsight_client.recall(
                bank_id=bank_id,
                query=f"{domain.value} skill knowledge patterns",
                top_k=1,
                metadata_filter={"skill_domain": domain.value},
            )
            if results:
                return results[0].get("content")
        except Exception:
            logger.debug("skill.recall_failed account=%s domain=%s", account_id, domain.value)
        return None

    async def get_all_skills(self, account_id: str) -> dict[str, str]:
        """Get all skill files for an account as a dict of domain → content."""
        skills: dict[str, str] = {}
        for domain in SkillDomain:
            content = await self.get_skill(account_id, domain)
            if content:
                skills[domain.value] = content
        return skills

    async def get_skills_for_prompt(
        self,
        account_id: str,
        domains: list[SkillDomain],
    ) -> str:
        """Load relevant skills and format for prompt injection.

        Returns a combined text block suitable for appending to a worker's
        system prompt alongside base training and primers.
        """
        sections: list[str] = []
        for domain in domains:
            content = await self.get_skill(account_id, domain)
            if content:
                label = domain.value.replace("_", " ").title()
                sections.append(f"## Account Skill: {label}\n\n{content}")

        if not sections:
            return ""

        return "## Per-Account Learned Skills\n\n" + "\n\n---\n\n".join(sections)

    async def save_skill(
        self,
        account_id: str,
        domain: SkillDomain,
        content: str,
    ) -> dict[str, Any]:
        """Save or update a skill file."""
        result = await retain_observation(
            account_id=account_id,
            bank_type=BankType.SKILLS,
            content=content,
            source_type="skill_update",
            evidence_type="skill_file",
            confidence_score=0.95,
            extra_metadata={
                "skill_domain": domain.value,
            },
        )
        logger.info("skill.saved account=%s domain=%s", account_id, domain.value)
        return result or {}

    async def initialize_skills(self, account_id: str) -> dict[str, str]:
        """Create default skill files for a new account.

        New accounts start with generic skills that get personalized
        over time as the system learns what works for this business.
        """
        defaults: dict[SkillDomain, str] = {
            SkillDomain.HOOKS: (
                "No account-specific hook patterns learned yet.\n"
                "The system will update this skill as hooks are tested and performance data arrives.\n"
                "Use base training hook frameworks until account-specific patterns emerge."
            ),
            SkillDomain.COPY: (
                "No account-specific copy patterns learned yet.\n"
                "The system will learn preferred copy length, tone, structure, and proof density.\n"
                "Use base training principles until account data compounds."
            ),
            SkillDomain.VISUALS: (
                "No account-specific visual patterns learned yet.\n"
                "The system will learn which image styles, colors, formats, and visual triggers\n"
                "perform best for this audience. Use SCRAWLS diversity until patterns emerge."
            ),
            SkillDomain.AUDIENCE: (
                "No account-specific audience patterns learned yet.\n"
                "The system will learn segment responsiveness, awareness level distribution,\n"
                "and which audience × message combinations drive results."
            ),
        }

        created: dict[str, str] = {}
        for domain, content in defaults.items():
            await self.save_skill(account_id, domain, content)
            created[domain.value] = content

        logger.info("skill.initialized account=%s domains=%d", account_id, len(created))
        return created

    async def learn_from_performance(
        self,
        account_id: str,
        domain: SkillDomain,
        performance_data: dict[str, Any],
        creative_attributes: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a skill file based on new performance evidence.

        This is the core self-learning mechanism. When performance data
        arrives, the system:
        1. Recalls the current skill for this domain
        2. Feeds the skill + new evidence to the LLM
        3. Gets an updated skill that incorporates the new learning
        4. Saves the updated skill

        Args:
            account_id: Which business
            domain: Which skill domain to update
            performance_data: Metrics (CTR, CPA, ROAS, spend, etc.)
            creative_attributes: What the ad looked like (hook type, format,
                visual style, awareness level, etc.)
        """
        current_skill = await self.get_skill(account_id, domain) or "No existing skill data."

        perf_text = json.dumps(performance_data, indent=1, default=str)[:2000]
        attrs_text = json.dumps(creative_attributes, indent=1, default=str)[:2000]

        result = await router.generate(
            capability=Capability.REFLECTION,
            system_prompt=(
                "You are a Skill Learning Engine. You update per-business skill files "
                "based on new performance evidence.\n\n"
                "Rules:\n"
                "- Incorporate new evidence without losing existing learnings\n"
                "- Be specific: 'curiosity hooks with exact numbers outperform generic benefit hooks 2:1'\n"
                "- Include confidence levels and evidence counts\n"
                "- Note what's confirmed vs what's emerging\n"
                "- The skill should read like a strategic brief for future workers"
            ),
            user_prompt=(
                f"Update this skill based on new performance evidence.\n\n"
                f"CURRENT SKILL ({domain.value}):\n{current_skill}\n\n"
                f"NEW PERFORMANCE DATA:\n{perf_text}\n\n"
                f"CREATIVE ATTRIBUTES:\n{attrs_text}\n\n"
                f"Return the updated skill content."
            ),
            temperature=0.2,
            max_tokens=4000,
            json_schema=SKILL_UPDATE_SCHEMA,
        )

        if result.get("_parse_error"):
            return {"success": False, "error": "Failed to parse skill update"}

        updated_content = result.get("updated_skill", "")
        if updated_content:
            await self.save_skill(account_id, domain, updated_content)

        logger.info(
            "skill.learned account=%s domain=%s changes=%d",
            account_id, domain.value, len(result.get("changes_made", [])),
        )

        return {
            "success": True,
            "domain": domain.value,
            "changes": result.get("changes_made", []),
        }

    async def promote_reflection_to_skill(
        self,
        account_id: str,
        reflection_content: str,
        domain: SkillDomain,
    ) -> dict[str, Any]:
        """Promote a durable reflection into a skill file.

        When memory_reflection surfaces a pattern strong enough to be
        a durable lesson, it can be promoted into the relevant skill file.
        """
        return await self.learn_from_performance(
            account_id=account_id,
            domain=domain,
            performance_data={"source": "reflection_promotion"},
            creative_attributes={"reflection": reflection_content},
        )


# Module-level singleton
skill_manager = SkillManager()
