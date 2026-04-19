"""Skill composer — hybrid composable skill retrieval.

The core function: given a task context (what are we making, for whom,
in what format), compose a relevant set of skill components.

Each ad generation task can pull DIFFERENT skills. A video UGC ad might pull:
  - hook.ugc.pattern_interrupt
  - visual.authentic.phone_quality
  - copy.conversational.problem_aware
  - structure.hook_first.15s
  - dr_tag.pain_point

While a static scientific ad might pull:
  - hook.authority.study_led
  - visual.clean.infographic
  - copy.data_driven.solution_aware
  - structure.proof_stack
  - dr_tag.authority

Retrieval is two-phase:
  1. Filter by structural tags (domain, format, awareness, platform)
  2. Semantic rank by embedding similarity to the task description

This produces composed skill context precisely fit to the task.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.skill_component import SkillComponent, SkillComposition
from app.services.intelligence.embeddings import embedding_service

logger = logging.getLogger(__name__)


@dataclass
class TaskContext:
    """The context of a creative task — used to select relevant skills."""

    task_type: str            # hook_generation | copy_generation | image_concept | video_script
    worker_name: str          # which worker is running

    # Filters (structural matching)
    format_type: str | None = None
    awareness_level: str | None = None
    platform: str | None = None
    segment: str | None = None

    # Semantic query (natural language description of the task)
    task_description: str = ""

    # Which domains to pull from (empty = all)
    include_domains: list[str] = field(default_factory=list)

    # Max components per domain
    max_per_domain: int = 3

    # Total cap
    max_total: int = 15


@dataclass
class ComposedSkills:
    """The result of skill composition for a task."""

    components: list[SkillComponent]
    composition_id: str
    prompt_text: str           # formatted for LLM injection

    def by_domain(self) -> dict[str, list[SkillComponent]]:
        """Group composed skills by domain."""
        grouped: dict[str, list[SkillComponent]] = {}
        for c in self.components:
            grouped.setdefault(c.domain, []).append(c)
        return grouped


class SkillComposer:
    """Composes skill components per-task."""

    async def compose(
        self,
        db: AsyncSession,
        account_id: str,
        context: TaskContext,
    ) -> ComposedSkills:
        """Compose relevant skill components for a task.

        Two-phase retrieval:
        1. Structural filter by domain/format/awareness tags
        2. Semantic rank by embedding similarity to task description
        """
        # Phase 1: Get task embedding for semantic ranking
        task_embedding = None
        if context.task_description:
            task_embedding = await embedding_service.embed_text(
                context.task_description
            )

        # Phase 2: Pull candidate skills across domains
        components: list[SkillComponent] = []

        domains_to_search = context.include_domains or [
            "hook", "copy", "visual", "structure", "dr_tag",
            "psychology", "format", "awareness", "mechanism",
            "proof", "audience", "platform",
        ]

        for domain in domains_to_search:
            # Build filter conditions
            conditions = [
                SkillComponent.is_active == True,
                SkillComponent.domain == domain,
            ]

            # Account-scoped skills OR global skills
            conditions.append(
                (SkillComponent.account_id == account_id)
                | (SkillComponent.scope == "global")
            )

            stmt = select(SkillComponent).where(and_(*conditions))

            # Semantic ranking if we have an embedding
            if task_embedding is not None:
                stmt = stmt.order_by(
                    SkillComponent.embedding.cosine_distance(task_embedding)
                )

            stmt = stmt.limit(context.max_per_domain * 3)  # over-fetch for post-filter

            result = await db.execute(stmt)
            candidates = list(result.scalars().all())

            # Post-filter by format/awareness/platform (arrays contain any)
            filtered = []
            for c in candidates:
                if context.format_type and c.applies_to_formats:
                    if context.format_type not in c.applies_to_formats and "all" not in c.applies_to_formats:
                        continue
                if context.awareness_level and c.applies_to_awareness:
                    if context.awareness_level not in c.applies_to_awareness and "all" not in c.applies_to_awareness:
                        continue
                if context.platform and c.applies_to_platforms:
                    if context.platform not in c.applies_to_platforms and "all" not in c.applies_to_platforms:
                        continue
                filtered.append(c)

                if len(filtered) >= context.max_per_domain:
                    break

            components.extend(filtered)

            if len(components) >= context.max_total:
                break

        components = components[:context.max_total]

        # Record the composition for learning
        composition_id = f"sc_{uuid4().hex[:12]}"
        composition = SkillComposition(
            id=composition_id,
            account_id=account_id,
            task_type=context.task_type,
            worker_name=context.worker_name,
            component_ids=[c.id for c in components],
            context={
                "format_type": context.format_type,
                "awareness_level": context.awareness_level,
                "platform": context.platform,
                "segment": context.segment,
                "task_description": context.task_description[:500],
            },
            outcome="pending",
        )
        db.add(composition)
        await db.commit()

        # Format as prompt text
        prompt_text = self._format_for_prompt(components)

        logger.info(
            "skills.composed account=%s task=%s components=%d domains=%d",
            account_id, context.task_type, len(components),
            len(set(c.domain for c in components)),
        )

        return ComposedSkills(
            components=components,
            composition_id=composition_id,
            prompt_text=prompt_text,
        )

    def _format_for_prompt(self, components: list[SkillComponent]) -> str:
        """Format composed skills as LLM prompt injection."""
        if not components:
            return ""

        # Group by domain
        by_domain: dict[str, list[SkillComponent]] = {}
        for c in components:
            by_domain.setdefault(c.domain, []).append(c)

        lines = ["## Active Skill Components (composed for this task)\n"]

        for domain, skills in by_domain.items():
            lines.append(f"### {domain.replace('_', ' ').title()} Skills\n")
            for s in skills:
                lines.append(f"**{s.name}** ({s.subdomain or 'general'}):")
                if s.trigger_conditions:
                    lines.append(f"  *Use when:* {s.trigger_conditions}")
                lines.append(f"  {s.summary}")
                lines.append(f"  {s.content[:800]}")
                lines.append("")

        return "\n".join(lines)

    async def attribute_outcome(
        self,
        db: AsyncSession,
        composition_id: str,
        outcome: str,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Attribute a performance outcome to a skill composition.

        When an ad performs, we update the composition record so the
        system can learn which skill combinations drive results.
        """
        stmt = select(SkillComposition).where(SkillComposition.id == composition_id)
        result = await db.execute(stmt)
        composition = result.scalar_one_or_none()

        if not composition:
            return

        composition.outcome = outcome
        composition.outcome_metrics = metrics
        await db.commit()

        # Cascade: update the confidence/evidence count on each component
        if composition.component_ids:
            stmt = select(SkillComponent).where(
                SkillComponent.id.in_(composition.component_ids)
            )
            result = await db.execute(stmt)
            for component in result.scalars():
                component.evidence_count += 1

                # Update confidence based on outcome
                if outcome in ("winner", "strong"):
                    # Increase confidence, capped at 0.99
                    component.confidence = min(0.99, component.confidence + 0.02)
                elif outcome in ("weak", "loser"):
                    # Decrease confidence
                    component.confidence = max(0.1, component.confidence - 0.02)

            await db.commit()

        logger.info(
            "skills.attributed composition=%s outcome=%s components=%d",
            composition_id, outcome,
            len(composition.component_ids or []),
        )


# Module-level singleton
skill_composer = SkillComposer()
