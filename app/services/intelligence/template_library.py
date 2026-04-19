"""Semantic template library — format categories that evolve.

Templates are NOT rigid prompts. They are semantic categories of
ad formats stored in Hindsight, searchable by attributes, and evolvable
from performance data.

Base categories ship with the system. Per-account, the system learns
which categories work and creates new ones from winners.

Categories are tagged with:
  - format_type: static | video | carousel | ugc | email | vsl | landing_page
  - style: template | native | hybrid
  - awareness_fit: unaware | problem_aware | solution_aware | product_aware | most_aware
  - complexity: simple | moderate | complex
  - platform: meta | tiktok | youtube | instagram | linkedin | email | web
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.services.hindsight.banks import BankType, bank_id_for
from app.services.hindsight.client import hindsight_client
from app.services.hindsight.memory import retain_observation

logger = logging.getLogger(__name__)

# Platform account for global templates
GLOBAL_ACCOUNT_ID = "_platform_global"


@dataclass
class TemplateCategory:
    """A semantic template category."""

    name: str
    description: str
    format_type: str          # static | video | carousel | ugc | email | vsl
    style: str                # template | native | hybrid
    awareness_fit: list[str]  # which awareness levels it works for
    platforms: list[str]      # which platforms it works on
    structure: str            # how the format is structured
    visual_direction: str     # general visual guidance for this format
    examples: list[str]       # reference descriptions


# ── Base Template Categories ────────────────────────────────────────
# These ship with the system. Accounts inherit them all and can evolve them.

BASE_TEMPLATES: list[TemplateCategory] = [
    # Static formats
    TemplateCategory("headline_plus_image", "Bold headline text over/alongside a striking image", "static", "template", ["product_aware", "most_aware"], ["meta", "instagram"], "Large text headline + supporting image. Text is the hero.", "Bold typography, high contrast, minimal design. Text readable at thumbnail size.", ["Product claim in large text over dark background"]),
    TemplateCategory("before_after", "Side-by-side or top-bottom comparison showing transformation", "static", "template", ["solution_aware", "product_aware"], ["meta", "instagram"], "Two panels: before state (pain) and after state (result). Clear visual contrast.", "Split composition. Before: muted/dark. After: bright/vibrant. Same subject both sides.", ["Skin comparison, weight loss progress, desk organization"]),
    TemplateCategory("infographic", "Data-driven visual with statistics, charts, or numbered lists", "static", "template", ["problem_aware", "solution_aware"], ["meta", "linkedin"], "Key statistic or numbered list with supporting visuals. Information hierarchy.", "Clean layout, branded colors, readable fonts. Data visualization if applicable.", ["'3 signs of cortisol imbalance' with icons"]),
    TemplateCategory("testimonial_card", "Customer quote with name/photo, designed as a card", "static", "template", ["product_aware", "most_aware"], ["meta", "instagram"], "Customer quote in large text, attribution below. Optional photo.", "Quote marks, clean typography, trust-building design. Photo adds credibility.", ["'I lost 23 lbs in 90 days' — Sarah M."]),
    TemplateCategory("meme_style", "Meme format adapted for advertising — relatable humor", "static", "native", ["unaware", "problem_aware"], ["meta", "instagram", "tiktok"], "Top text / bottom text over relevant image, or reaction meme format.", "Lo-fi, not polished. Must look native to feed. Humor must land for target audience.", ["'Me at 3am staring at the ceiling' format"]),
    TemplateCategory("screenshot_chat", "Screenshot of a text conversation, DM, or notification", "static", "native", ["unaware", "problem_aware"], ["meta", "instagram"], "Realistic phone screenshot showing a conversation about the product/problem.", "Must look like a real phone screenshot. iMessage or Instagram DM format. Realistic.", ["Text thread about experiencing the product result"]),
    TemplateCategory("ugc_selfie", "UGC-style selfie with natural look, text overlay optional", "static", "native", ["problem_aware", "product_aware"], ["meta", "instagram", "tiktok"], "Real-looking selfie from target demographic, with or without text overlay.", "iPhone quality, natural lighting, not posed. Must pass the 'real person' test.", ["Person holding product with genuine expression"]),
    TemplateCategory("note_from_founder", "Handwritten or typed note styled as personal message", "static", "template", ["product_aware", "most_aware"], ["meta", "instagram"], "Personal note format — handwritten or typed on paper/phone notes app.", "Notes app screenshot, or handwritten on paper. Personal, authentic feel.", ["iPhone notes app with founder message about product mission"]),
    TemplateCategory("scientific_study", "Clinical study results or scientific data visualization", "static", "template", ["solution_aware", "product_aware"], ["meta", "linkedin"], "Key finding from a study with journal name, sample size, result.", "Clean, authoritative. Medical/scientific aesthetic. Cites real source.", ["'40% cortisol reduction (n=200, double-blind)' with journal citation"]),
    TemplateCategory("comparison_chart", "Product vs competitors or product vs alternative approaches", "static", "template", ["solution_aware", "product_aware"], ["meta", "linkedin"], "Two-column comparison: us vs them, or this approach vs that approach.", "Checkmarks vs X marks. Clear advantage visualization. Not directly naming competitors unless legal.", ["Feature comparison grid with checkmarks"]),

    # Video formats
    TemplateCategory("talking_head_ugc", "Person talking to camera in UGC style", "video", "native", ["problem_aware", "solution_aware", "product_aware"], ["meta", "tiktok", "youtube", "instagram"], "Person speaks directly to camera. Hook in first 1-3 seconds. Text overlays reinforce key points.", "Natural lighting, home/office environment, phone-quality video. Authentic not produced.", ["Customer testimonial filmed on phone"]),
    TemplateCategory("problem_solution_video", "Opens with problem, transitions to solution/mechanism", "video", "template", ["problem_aware", "solution_aware"], ["meta", "tiktok", "youtube"], "Problem statement (5-10s) → Mechanism explanation (10-20s) → Proof (5-10s) → CTA (5s).", "Start dark/tense, brighten at solution. B-roll of problem scenes. Product reveal at mechanism.", ["Showing the '3am wakeup' then the science of why"]),
    TemplateCategory("listicle_video", "Numbered list format — '3 things you didn't know about...'", "video", "template", ["unaware", "problem_aware"], ["tiktok", "instagram", "youtube"], "Numbered items with visual transitions. Each item 5-10 seconds. Hook promises the list.", "Quick cuts, text overlays for each number, trending audio optional.", ["'3 signs your cortisol is wrecking your sleep'"]),
    TemplateCategory("in_feed_vsl", "Short-form video sales letter for in-feed consumption", "video", "template", ["problem_aware", "solution_aware"], ["meta", "youtube"], "Condensed VSL: Hook (3s) → Problem (10s) → Mechanism (15s) → Proof (10s) → CTA (5s). 30-60 seconds total.", "Mix of talking head, B-roll, text overlays, product shots. Fast-paced but logical.", ["Compressed sales argument in under 60 seconds"]),
    TemplateCategory("green_screen_explainer", "Person over slides/images explaining a concept", "video", "native", ["problem_aware", "solution_aware"], ["tiktok", "instagram"], "Person on green screen with images/charts behind them. Educational feel.", "TikTok-native format. Green screen effect, pointing at content. Informal tone.", ["Person pointing at a study result behind them"]),

    # Carousel formats
    TemplateCategory("story_carousel", "Multi-card narrative that builds to a conclusion", "carousel", "template", ["unaware", "problem_aware"], ["meta", "instagram", "linkedin"], "5-10 cards telling a story. Card 1 = hook. Last card = CTA. Each card earns the next swipe.", "Consistent visual style across cards. Each card has one clear message. Progress indicator.", ["Customer transformation story across 7 cards"]),
    TemplateCategory("educational_carousel", "Teaching format — each card delivers one insight", "carousel", "template", ["problem_aware", "solution_aware"], ["instagram", "linkedin"], "5-8 cards with one fact/insight per card. Title card + content cards + CTA card.", "Clean, branded design. One point per card. Numbered or themed.", ["'5 reasons your sleep supplement isn't working'"]),

    # Email formats
    TemplateCategory("story_email", "Email built around a narrative or personal story", "email", "template", ["problem_aware", "solution_aware"], ["email"], "Subject line (curiosity) → Personal story opening → Problem identification → Mechanism bridge → Proof → CTA.", "Minimal images. Text-first. Reads like a personal letter, not marketing.", ["Founder story about discovering the mechanism"]),
    TemplateCategory("proof_stack_email", "Email that stacks proof elements one after another", "email", "template", ["product_aware", "most_aware"], ["email"], "Subject line (proof-led) → Lead testimonial → Study data → Before/after → Social proof → CTA.", "Strategic proof ordering. Each proof element earns belief for the next. CTA after sufficient belief.", ["Email with testimonial → study → reviews → offer"]),
]


class TemplateLibrary:
    """Manages the semantic template library."""

    async def initialize_global_templates(self) -> int:
        """Seed the GLOBAL bank with base template categories.

        Called once during platform setup. Idempotent — checks for existing.
        """
        count = 0
        for tmpl in BASE_TEMPLATES:
            content = (
                f"Template: {tmpl.name}\n"
                f"Format: {tmpl.format_type} | Style: {tmpl.style}\n"
                f"Description: {tmpl.description}\n"
                f"Structure: {tmpl.structure}\n"
                f"Visual direction: {tmpl.visual_direction}\n"
                f"Awareness fit: {', '.join(tmpl.awareness_fit)}\n"
                f"Platforms: {', '.join(tmpl.platforms)}"
            )
            await retain_observation(
                account_id=GLOBAL_ACCOUNT_ID,
                bank_type=BankType.GLOBAL,
                content=content,
                source_type="base_template",
                evidence_type="template_category",
                confidence_score=0.9,
                extra_metadata={
                    "template_name": tmpl.name,
                    "format_type": tmpl.format_type,
                    "style": tmpl.style,
                    "awareness_fit": tmpl.awareness_fit,
                    "platforms": tmpl.platforms,
                },
            )
            count += 1

        logger.info("templates.initialized count=%d", count)
        return count

    async def search_templates(
        self,
        query: str,
        *,
        format_type: str | None = None,
        awareness_level: str | None = None,
        platform: str | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search templates by query and optional filters."""
        bank_id = bank_id_for(GLOBAL_ACCOUNT_ID, BankType.GLOBAL)
        metadata_filter: dict[str, Any] = {"evidence_type": "template_category"}
        if format_type:
            metadata_filter["format_type"] = format_type

        try:
            results = await hindsight_client.recall(
                bank_id=bank_id,
                query=query,
                top_k=top_k,
                metadata_filter=metadata_filter,
            )
            # Post-filter by awareness and platform if needed
            if awareness_level:
                results = [
                    r for r in results
                    if awareness_level in r.get("metadata", {}).get("awareness_fit", [])
                ]
            if platform:
                results = [
                    r for r in results
                    if platform in r.get("metadata", {}).get("platforms", [])
                ]
            return results
        except Exception:
            return []

    async def get_templates_for_prompt(
        self,
        format_type: str | None = None,
        awareness_level: str | None = None,
        top_k: int = 8,
    ) -> str:
        """Get relevant templates formatted for prompt injection."""
        query = f"{format_type or 'all'} template format creative"
        results = await self.search_templates(
            query,
            format_type=format_type,
            awareness_level=awareness_level,
            top_k=top_k,
        )
        if not results:
            return ""

        lines = ["## Available Template Formats\n"]
        for r in results:
            lines.append(f"- {r.get('content', '')}\n")

        return "\n".join(lines)

    async def create_account_template(
        self,
        account_id: str,
        name: str,
        description: str,
        format_type: str,
        structure: str,
        visual_direction: str,
        awareness_fit: list[str],
        platforms: list[str],
    ) -> dict[str, Any]:
        """Create a new template category for a specific account.

        This happens when the system discovers a winning format pattern
        that doesn't match any base template — it creates a new category.
        """
        content = (
            f"Account template: {name}\n"
            f"Format: {format_type}\n"
            f"Description: {description}\n"
            f"Structure: {structure}\n"
            f"Visual direction: {visual_direction}\n"
            f"Awareness fit: {', '.join(awareness_fit)}\n"
            f"Platforms: {', '.join(platforms)}"
        )
        result = await retain_observation(
            account_id=account_id,
            bank_type=BankType.CREATIVE,
            content=content,
            source_type="learned_template",
            evidence_type="template_category",
            confidence_score=0.75,
            extra_metadata={
                "template_name": name,
                "format_type": format_type,
                "awareness_fit": awareness_fit,
                "platforms": platforms,
            },
        )
        logger.info("templates.account_created account=%s name=%s", account_id, name)
        return result or {}


# Module-level singleton
template_library = TemplateLibrary()
