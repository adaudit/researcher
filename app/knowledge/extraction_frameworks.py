"""Extraction frameworks — what to look for in each artifact type.

These frameworks define the EXTRACTION TARGETS for each artifact type.
When a worker analyzes a landing page, video, comment, or ad, it needs
to know exactly what to extract. Not "analyze this page" but
"extract these 14 specific things from this page."

Each framework is a structured checklist that workers inject into their
prompts alongside the base training corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExtractionTarget:
    """One thing to look for in an artifact."""

    name: str
    description: str
    evidence_type: str  # maps to Hindsight metadata
    priority: str  # critical | high | medium | low
    examples: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractionFramework:
    """Complete extraction guide for one artifact type."""

    artifact_type: str
    purpose: str
    targets: list[ExtractionTarget]
    reasoning_questions: list[str]  # questions to reason about after extraction
    anti_patterns: list[str]  # common mistakes to avoid


# ── Landing Page Framework ──────────────────────────────────────────

LANDING_PAGE_FRAMEWORK = ExtractionFramework(
    artifact_type="landing_page",
    purpose="Extract the complete persuasion architecture of a landing page",
    targets=[
        ExtractionTarget(
            "above_fold_promise",
            "The primary promise visible without scrolling. Is it specific or generic?",
            "landing_page_claim",
            "critical",
            ["'Lose 10lbs in 30 days' (specific)", "'Transform your health' (generic)"],
        ),
        ExtractionTarget(
            "headline_hierarchy",
            "Every H1-H4 in order — this reveals the page's argument structure",
            "landing_page_claim",
            "critical",
        ),
        ExtractionTarget(
            "explicit_claims",
            "Every factual assertion the page makes. Exact text, not paraphrased.",
            "landing_page_claim",
            "critical",
            ["'Clinically proven to reduce cortisol by 40%'", "'Over 50,000 customers served'"],
        ),
        ExtractionTarget(
            "implied_claims",
            "What the page IMPLIES without stating directly. Label as inference.",
            "landing_page_claim",
            "high",
            ["Before/after photos imply typical results", "Doctor photo implies medical backing"],
        ),
        ExtractionTarget(
            "proof_elements",
            "Every piece of evidence: studies, testimonials, certifications, stats, awards",
            "proof_claim",
            "critical",
        ),
        ExtractionTarget(
            "unsupported_claims",
            "Claims that have no adjacent proof element",
            "friction_point",
            "high",
        ),
        ExtractionTarget(
            "mechanism_explanation",
            "How the product works. Is the mechanism explained clearly? Where on the page?",
            "mechanism_insight",
            "critical",
        ),
        ExtractionTarget(
            "cta_inventory",
            "Every CTA: button text, placement, what belief setup precedes it",
            "landing_page_claim",
            "high",
        ),
        ExtractionTarget(
            "friction_points",
            "Where attention leaks: jargon, broken trust, generic language, confusion",
            "friction_point",
            "high",
        ),
        ExtractionTarget(
            "objection_handling",
            "Where and how the page addresses buyer objections",
            "landing_page_claim",
            "medium",
        ),
        ExtractionTarget(
            "risk_reversal",
            "Guarantees, free trials, money-back promises and their terms",
            "landing_page_claim",
            "medium",
        ),
        ExtractionTarget(
            "urgency_and_scarcity",
            "Timers, stock counters, limited offers — real or manufactured",
            "landing_page_claim",
            "medium",
        ),
        ExtractionTarget(
            "social_proof_placement",
            "Where testimonials, reviews, and trust signals appear relative to claims",
            "proof_claim",
            "medium",
        ),
        ExtractionTarget(
            "embedded_media",
            "Videos, interactive elements, calculators — what role do they play?",
            "landing_page_claim",
            "medium",
        ),
    ],
    reasoning_questions=[
        "Does the page build a belief transfer chain, or just stack claims?",
        "Is there a clear mechanism bridge between the promise and the product?",
        "Where does the proof-to-claim ratio break down?",
        "What awareness level is this page optimized for? Does it match the likely visitor?",
        "Could a competitor swap in their product and use this page unchanged?",
        "What is the page's strongest proof element? Is it above the fold?",
        "Where would a skeptical reader stop believing?",
    ],
    anti_patterns=[
        "Paraphrasing page text instead of quoting exactly",
        "Listing claims without evaluating their support",
        "Ignoring the SEQUENCE of elements (order matters for belief transfer)",
        "Treating all testimonials as equal proof regardless of specificity",
        "Missing mechanism absence — many pages never explain HOW the product works",
    ],
)


# ── Video / VSL Framework ──────────────────────────────────────────

VIDEO_FRAMEWORK = ExtractionFramework(
    artifact_type="video",
    purpose="Extract persuasion elements from video content (VSLs, testimonials, demos)",
    targets=[
        ExtractionTarget(
            "opening_hook",
            "First 5-10 seconds. What pattern interrupt or curiosity trigger is used?",
            "hook_pattern",
            "critical",
            ["'What your doctor isn't testing for…' (curiosity + authority gap)"],
        ),
        ExtractionTarget(
            "spoken_claims",
            "Every factual assertion made verbally. Timestamp + exact words.",
            "transcript_highlight",
            "critical",
        ),
        ExtractionTarget(
            "visual_proof",
            "What's shown on screen: graphs, before/after, product demos, certifications",
            "proof_claim",
            "critical",
        ),
        ExtractionTarget(
            "emotional_beats",
            "Moments designed to create emotional response. What emotion? What trigger?",
            "creative_structure",
            "high",
        ),
        ExtractionTarget(
            "mechanism_reveal",
            "When and how the mechanism is explained. Timestamp and method.",
            "mechanism_insight",
            "critical",
        ),
        ExtractionTarget(
            "objection_handling_moments",
            "Where the video anticipates and addresses doubts",
            "transcript_highlight",
            "high",
        ),
        ExtractionTarget(
            "speaker_authority",
            "Who is speaking? What credentials are claimed or implied?",
            "proof_claim",
            "high",
        ),
        ExtractionTarget(
            "pacing_and_retention",
            "Where would viewers likely drop off? What keeps them watching?",
            "creative_structure",
            "medium",
        ),
        ExtractionTarget(
            "cta_setup",
            "What beliefs are established before the call to action?",
            "landing_page_claim",
            "high",
        ),
        ExtractionTarget(
            "b_roll_and_visuals",
            "What visual metaphors, product shots, or lifestyle imagery is used?",
            "creative_structure",
            "medium",
        ),
    ],
    reasoning_questions=[
        "Does the video build belief progressively or dump information?",
        "Is the mechanism explained BEFORE the product is revealed?",
        "Would the video still work with the product swapped? (anti-generic test)",
        "What emotion does the viewer feel at each major beat?",
        "Where is the video strongest? Where does it lose credibility?",
    ],
    anti_patterns=[
        "Transcribing without analyzing what the visuals add",
        "Ignoring the pacing — WHEN claims appear matters as much as WHAT they say",
        "Missing the emotional arc in favor of just listing claims",
        "Not noting what's SHOWN vs what's SAID (visual-verbal alignment)",
    ],
)


# ── Ad Creative Framework ──────────────────────────────────────────

AD_CREATIVE_FRAMEWORK = ExtractionFramework(
    artifact_type="ad_creative",
    purpose="Extract strategic elements from winning ad creatives",
    targets=[
        ExtractionTarget(
            "primary_hook",
            "First line or visual that captures attention. Type and technique.",
            "hook_pattern",
            "critical",
            ["Curiosity hook", "Pain-call-out hook", "Contrarian hook", "Story hook", "Proof hook"],
        ),
        ExtractionTarget(
            "angle",
            "The strategic angle — what lens is the product seen through?",
            "creative_structure",
            "critical",
            ["Health angle", "Cost-of-inaction angle", "Authority angle", "Social proof angle"],
        ),
        ExtractionTarget(
            "format_structure",
            "Creative format: UGC, talking head, text overlay, carousel, listicle, story",
            "creative_structure",
            "high",
        ),
        ExtractionTarget(
            "proof_in_ad",
            "Any proof elements shown directly in the ad creative",
            "proof_claim",
            "high",
        ),
        ExtractionTarget(
            "audience_signal",
            "Who is this ad targeting based on language, imagery, and assumptions?",
            "audience_desire",
            "high",
        ),
        ExtractionTarget(
            "cta_text_and_urgency",
            "Call to action language and any urgency/scarcity elements",
            "landing_page_claim",
            "medium",
        ),
        ExtractionTarget(
            "competitor_differentiation",
            "Does the ad differentiate from alternatives? How?",
            "competitive_signal",
            "medium",
        ),
        ExtractionTarget(
            "performance_signals",
            "Engagement metrics if visible (likes, comments, shares, spend indicators)",
            "performance_signal",
            "medium",
        ),
    ],
    reasoning_questions=[
        "What desire does this hook tap into? Is it surface or deep?",
        "What awareness level is this ad calibrated for?",
        "Why would this ad outperform a generic alternative?",
        "What can we learn from this format/structure for our own creatives?",
        "Does this ad pass the anti-generic test?",
    ],
    anti_patterns=[
        "Describing what the ad looks like without analyzing WHY it works",
        "Ignoring the ANGLE in favor of just cataloging elements",
        "Not identifying the awareness level the ad targets",
        "Treating all winning ads as equal — some win on spend, not on strategy",
    ],
)


# ── VOC (Comments/Reviews) Framework ───────────────────────────────

VOC_FRAMEWORK = ExtractionFramework(
    artifact_type="voc",
    purpose="Mine customer language for desires, pains, objections, and exact phrases",
    targets=[
        ExtractionTarget(
            "exact_desire_phrases",
            "Direct quotes expressing what the customer wants. Preserve exact words.",
            "audience_desire",
            "critical",
            ["'I just want to sleep through the night'", "'Looking for something that actually works'"],
        ),
        ExtractionTarget(
            "exact_pain_phrases",
            "Direct quotes describing suffering, frustration, or problems.",
            "audience_pain",
            "critical",
            ["'I've tried everything and nothing works'", "'The crash at 2pm is killing me'"],
        ),
        ExtractionTarget(
            "exact_objection_phrases",
            "Direct quotes expressing doubt, skepticism, or barriers to purchase.",
            "audience_objection",
            "critical",
            ["'Sounds too good to be true'", "'At that price I'd expect a miracle'"],
        ),
        ExtractionTarget(
            "intensity_markers",
            "Words showing emotional intensity: caps, exclamation, superlatives, repetition.",
            "language_pattern",
            "high",
            ["ALL CAPS words", "Multiple exclamation marks", "'literally', 'actually', 'finally'"],
        ),
        ExtractionTarget(
            "recurring_metaphors",
            "Figurative language customers use to describe their experience.",
            "language_pattern",
            "high",
            ["'hit a wall'", "'running on empty'", "'at the end of my rope'"],
        ),
        ExtractionTarget(
            "desire_contradictions",
            "When customers want two things that conflict.",
            "audience_desire",
            "medium",
            ["Want results but don't want to change diet", "Want natural but want fast-acting"],
        ),
        ExtractionTarget(
            "competitor_mentions",
            "When customers name or describe alternatives they've tried.",
            "competitive_signal",
            "high",
        ),
        ExtractionTarget(
            "trigger_events",
            "What caused them to start searching for a solution NOW.",
            "audience_desire",
            "high",
            ["'After my doctor told me…'", "'When I couldn't fit into…'"],
        ),
        ExtractionTarget(
            "outcome_descriptions",
            "How customers describe the result they want in their own words.",
            "audience_desire",
            "high",
        ),
        ExtractionTarget(
            "trust_signals",
            "What made them trust or distrust. What convinced or deterred them.",
            "audience_objection",
            "medium",
        ),
    ],
    reasoning_questions=[
        "What is the dominant pain theme? Does one theme massively outweigh others?",
        "What language patterns recur? These become headline raw material.",
        "What objections appear BEFORE purchase vs AFTER purchase?",
        "Are there desire clusters that the current marketing isn't addressing?",
        "What trigger events suggest timing-based targeting opportunities?",
    ],
    anti_patterns=[
        "Paraphrasing customer language — the exact words ARE the value",
        "Counting themes without preserving the phrases that define them",
        "Treating all comments as equal — intensity and frequency matter",
        "Missing the underlying fear behind objections",
        "Ignoring positive reviews — they reveal what convinced people to buy",
    ],
)


# ── Research / Literature Framework ────────────────────────────────

RESEARCH_FRAMEWORK = ExtractionFramework(
    artifact_type="research",
    purpose="Extract usable proof and evidence from scientific and market research",
    targets=[
        ExtractionTarget(
            "key_findings",
            "Primary conclusions with exact numbers and methodology.",
            "research_finding",
            "critical",
            ["'40% reduction in cortisol (n=200, double-blind, 8 weeks)'"],
        ),
        ExtractionTarget(
            "study_quality",
            "Sample size, methodology, peer-review status, potential bias.",
            "research_finding",
            "critical",
        ),
        ExtractionTarget(
            "usable_statistics",
            "Numbers that can be cited in marketing materials.",
            "proof_claim",
            "high",
        ),
        ExtractionTarget(
            "mechanism_evidence",
            "Evidence explaining HOW something works at a biological/chemical level.",
            "mechanism_insight",
            "high",
        ),
        ExtractionTarget(
            "safety_signals",
            "Side effects, contraindications, long-term safety data.",
            "research_finding",
            "critical",
        ),
        ExtractionTarget(
            "regulatory_implications",
            "What can and cannot be claimed based on this evidence.",
            "research_finding",
            "critical",
        ),
        ExtractionTarget(
            "competitive_evidence",
            "How this evidence compares to what competitors can cite.",
            "competitive_signal",
            "medium",
        ),
    ],
    reasoning_questions=[
        "Is this evidence strong enough to base a headline on?",
        "What claims does this evidence support vs. what does it NOT support?",
        "Could this evidence be used by a competitor? Is it ingredient-specific or brand-specific?",
        "What is the strongest single statistic from this research?",
        "Are there regulatory constraints on how this evidence can be used in marketing?",
    ],
    anti_patterns=[
        "Citing findings without noting methodology quality",
        "Extrapolating beyond what the study actually measured",
        "Confusing correlation findings with causation claims",
        "Missing regulatory constraints on health/medical evidence",
    ],
)


# ── Competitor Framework ───────────────────────────────────────────

COMPETITOR_FRAMEWORK = ExtractionFramework(
    artifact_type="competitor",
    purpose="Extract competitive positioning, claims, proof, pricing, and audience signals from competitor assets",
    targets=[
        ExtractionTarget(
            "positioning_statement",
            "How the competitor positions themselves — their core promise and identity.",
            "competitive_signal",
            "critical",
            ["'The only clinically-proven…'", "'Built by doctors, for doctors'"],
        ),
        ExtractionTarget(
            "primary_claims",
            "Every factual assertion the competitor makes. Exact text.",
            "competitive_signal",
            "critical",
            ["'3x faster results'", "'Used by 500,000+ customers'"],
        ),
        ExtractionTarget(
            "proof_inventory",
            "All evidence they cite: studies, certifications, testimonials, before/afters, endorsements.",
            "proof_claim",
            "critical",
        ),
        ExtractionTarget(
            "pricing_structure",
            "Price points, tiers, anchoring strategy, subscription vs one-time, hidden costs.",
            "competitive_signal",
            "high",
            ["'$49/mo or $399/yr (save 32%)'", "'Free trial → $79/mo'"],
        ),
        ExtractionTarget(
            "audience_signals",
            "Who are they targeting? Language, imagery, personas, pain points addressed.",
            "audience_desire",
            "high",
        ),
        ExtractionTarget(
            "mechanism_claims",
            "How do they explain their product works? Is the mechanism clear or hidden?",
            "mechanism_insight",
            "high",
        ),
        ExtractionTarget(
            "differentiation_claims",
            "How they distinguish from alternatives. What makes them 'different'?",
            "competitive_signal",
            "high",
            ["'Unlike other supplements, we use…'", "'The first and only…'"],
        ),
        ExtractionTarget(
            "risk_reversal",
            "Guarantees, return policies, free trials, money-back terms.",
            "competitive_signal",
            "medium",
        ),
        ExtractionTarget(
            "content_themes",
            "Recurring themes in their ads, posts, emails. What angles do they lean on?",
            "creative_structure",
            "high",
        ),
        ExtractionTarget(
            "vulnerability_gaps",
            "What they DON'T address — missing proof, unsupported claims, ignored objections.",
            "competitive_signal",
            "critical",
            ["No clinical evidence cited", "No mechanism explanation", "Generic testimonials only"],
        ),
    ],
    reasoning_questions=[
        "What is their strongest competitive advantage? Can we neutralize it?",
        "Where are they vulnerable — what claims are unsupported or weak?",
        "What audience segments are they NOT serving well?",
        "Are they competing on price, proof, mechanism, or brand? Where is the opening?",
        "What would it take for a customer to switch from them to us?",
        "Is there category sameness? Are they saying the same thing as everyone else?",
    ],
    anti_patterns=[
        "Listing competitor features without analyzing strategic implications",
        "Assuming competitor claims are true — note which are supported vs unsupported",
        "Missing what the competitor ISN'T saying — gaps are often more valuable than claims",
        "Treating all competitors as direct — differentiate direct, indirect, and category competitors",
        "Ignoring pricing psychology (anchoring, decoy tiers, urgency)",
    ],
)


# ── Offer Framework ───────────────────────────────────────────────

OFFER_FRAMEWORK = ExtractionFramework(
    artifact_type="offer",
    purpose="Decompose an offer into mechanism, CTA, price anchoring, risk reversal, and constraints",
    targets=[
        ExtractionTarget(
            "mechanism",
            "What the product does, how it works, why it's believable, and what makes it unique.",
            "mechanism_insight",
            "critical",
            ["'Patented cold-press extraction preserves 97% of active compounds'"],
        ),
        ExtractionTarget(
            "primary_cta",
            "The main call to action — exact text, type (buy/try/learn/subscribe), friction level.",
            "offer_truth",
            "critical",
            ["'Start Your Free Trial' (low friction)", "'Buy Now — $149' (high friction)"],
        ),
        ExtractionTarget(
            "price_anchoring",
            "How price is framed: comparisons, per-day cost, value stacking, competitor anchoring.",
            "offer_truth",
            "high",
            ["'Less than your daily coffee'", "'$200 value, yours for $49'"],
        ),
        ExtractionTarget(
            "risk_reversal",
            "Guarantees, refund policies, trials — everything that reduces purchase risk.",
            "offer_truth",
            "critical",
            ["'60-day money-back guarantee'", "'Cancel anytime, no questions asked'"],
        ),
        ExtractionTarget(
            "constraints",
            "Regulatory limits, claim restrictions, things that CANNOT be said.",
            "offer_truth",
            "critical",
            ["FDA disclaimer required", "Cannot claim to cure/treat/prevent disease"],
        ),
        ExtractionTarget(
            "value_stack",
            "All bonuses, bundled items, added value beyond the core product.",
            "offer_truth",
            "high",
        ),
        ExtractionTarget(
            "urgency_scarcity",
            "Time limits, quantity limits, price increases — real or manufactured.",
            "offer_truth",
            "medium",
        ),
        ExtractionTarget(
            "target_awareness",
            "What awareness level the offer is optimized for (unaware → most aware).",
            "audience_desire",
            "high",
        ),
        ExtractionTarget(
            "proof_basis",
            "All proof elements supporting the offer: studies, testimonials, certifications, results.",
            "proof_claim",
            "critical",
        ),
        ExtractionTarget(
            "objection_anticipation",
            "Which buyer objections does the offer structure address? Which does it miss?",
            "audience_objection",
            "high",
        ),
    ],
    reasoning_questions=[
        "Is the mechanism clear enough to explain in one sentence? If not, that's a copy problem.",
        "Does the proof match the size of the claim? Big claims need big proof.",
        "What's the primary objection this offer fails to address?",
        "Is the CTA appropriate for the awareness level of the likely buyer?",
        "What would make a warm lead hesitate at the point of purchase?",
        "Is the price anchoring based on real value or arbitrary numbers?",
    ],
    anti_patterns=[
        "Listing offer components without analyzing their strategic interaction",
        "Ignoring constraint severity — some constraints kill entire angles",
        "Not distinguishing real scarcity from manufactured urgency",
        "Missing the mechanism gap — many offers never explain HOW the product works",
        "Treating the offer as static — offers evolve and should be re-analyzed after changes",
    ],
)


# ── Creative Concept Framework ────────────────────────────────────

CREATIVE_CONCEPT_FRAMEWORK = ExtractionFramework(
    artifact_type="creative_concept",
    purpose="Evaluate image concepts for scroll-stop potential, native-feed fit, and brand alignment",
    targets=[
        ExtractionTarget(
            "scroll_stop_element",
            "What in this image/concept would make someone stop scrolling? Be specific.",
            "creative_structure",
            "critical",
            ["Unexpected juxtaposition", "Extreme close-up of texture", "Pattern interrupt color"],
        ),
        ExtractionTarget(
            "concept_source",
            "Where did this concept originate? Copy-derived, reptile trigger, VOC, wild association, loopback.",
            "creative_structure",
            "critical",
            ["Copy-derived: literal visualization of headline", "Reptile: disgust trigger", "Wild: unrelated metaphor"],
        ),
        ExtractionTarget(
            "native_feed_fit",
            "Does this look native to the target platform feed, or does it scream 'ad'?",
            "creative_structure",
            "critical",
            ["Native: looks like organic Instagram post", "Ad-like: stock photo with text overlay"],
        ),
        ExtractionTarget(
            "emotional_trigger",
            "What emotion does this concept evoke? Map to the 13 reptile triggers if applicable.",
            "creative_structure",
            "high",
            ["Curiosity (what is that?)", "Disgust (visceral reaction)", "Aspiration (I want that life)"],
        ),
        ExtractionTarget(
            "copy_alignment",
            "How well does this concept reinforce the ad copy it's paired with?",
            "creative_structure",
            "high",
            ["Direct illustration of headline claim", "Emotional complement to body copy", "Contradicts copy tone"],
        ),
        ExtractionTarget(
            "format_suitability",
            "Which ad formats and placements would this concept work for?",
            "creative_structure",
            "medium",
            ["1:1 feed post", "9:16 story/reel", "Carousel card", "Thumbnail"],
        ),
        ExtractionTarget(
            "production_feasibility",
            "Can this be produced with AI image generation, or does it need photography/design?",
            "creative_structure",
            "medium",
            ["AI-generatable with Midjourney", "Needs real product photography", "Composite: AI + product shot"],
        ),
        ExtractionTarget(
            "differentiation_from_category",
            "Does this concept look different from typical ads in the category?",
            "competitive_signal",
            "high",
        ),
        ExtractionTarget(
            "winning_vectors",
            "If from a proven winner: what specific visual elements drove performance?",
            "creative_structure",
            "high",
            ["Subject matter (close-up ingredient)", "Camera angle (overhead flat-lay)", "Lighting (natural golden hour)"],
        ),
    ],
    reasoning_questions=[
        "Would YOU stop scrolling for this? Be honest — default is to keep scrolling.",
        "Does this concept pass the 'thumb test' — is it compelling at thumbnail size?",
        "Is this concept specific to OUR product, or could any competitor use it?",
        "What's the concept's relationship to the copy — does it add or just decorate?",
        "If we generated 50 of these, how many would a human creative director keep?",
        "Does this feel native to the platform, or does it feel like an interruption?",
    ],
    anti_patterns=[
        "Evaluating concepts based on aesthetic quality instead of scroll-stop potential",
        "Ignoring platform context — what works on Instagram fails on LinkedIn",
        "Treating all AI-generated concepts as equal quality",
        "Missing the 'polished = invisible' trap — native beats beautiful in feed",
        "Not considering the concept-copy interaction — image and text work together",
        "Evaluating in isolation instead of against the competitive visual landscape",
    ],
)


# ── Email Framework ───────────────────────────────────────────────

EMAIL_FRAMEWORK = ExtractionFramework(
    artifact_type="email",
    purpose="Extract persuasion architecture from email campaigns: subject lines, preview text, body structure, CTA placement",
    targets=[
        ExtractionTarget(
            "subject_line",
            "Exact subject line text. Categorize: curiosity, benefit, urgency, personal, story.",
            "hook_pattern",
            "critical",
            ["'The mistake 90% of people make with…' (curiosity)", "'Your results are ready' (personal)"],
        ),
        ExtractionTarget(
            "preview_text",
            "Preview/preheader text — does it complement or repeat the subject line?",
            "hook_pattern",
            "high",
        ),
        ExtractionTarget(
            "opening_line",
            "First sentence of the email body. Does it earn the next line?",
            "hook_pattern",
            "critical",
        ),
        ExtractionTarget(
            "email_structure",
            "Overall format: story, listicle, problem-solution, testimonial, educational, promotional.",
            "creative_structure",
            "high",
        ),
        ExtractionTarget(
            "cta_placement",
            "Where CTAs appear, how many, exact text, and what belief setup precedes each.",
            "landing_page_claim",
            "critical",
            ["Single CTA at end after full story", "Multiple CTAs: after hook, after proof, after urgency"],
        ),
        ExtractionTarget(
            "proof_elements",
            "Testimonials, statistics, case studies, screenshots embedded in the email.",
            "proof_claim",
            "high",
        ),
        ExtractionTarget(
            "personalization",
            "Dynamic fields, segment-specific content, behavioral triggers.",
            "creative_structure",
            "medium",
            ["{{first_name}} in subject", "Product-specific recommendations", "Cart abandonment trigger"],
        ),
        ExtractionTarget(
            "urgency_mechanisms",
            "Deadlines, countdown language, scarcity signals, consequence framing.",
            "landing_page_claim",
            "medium",
        ),
        ExtractionTarget(
            "tone_and_voice",
            "Brand voice: casual, authoritative, urgent, friendly, clinical. Consistency with other channels.",
            "creative_structure",
            "medium",
        ),
        ExtractionTarget(
            "sequence_position",
            "Where in the sequence this email sits: welcome, nurture, cart abandon, win-back, promo.",
            "creative_structure",
            "high",
        ),
    ],
    reasoning_questions=[
        "Would you open this email based on the subject line alone? Why or why not?",
        "Does the email deliver on the subject line's promise, or is it bait-and-switch?",
        "Is the CTA earned by the preceding content, or does it appear prematurely?",
        "What awareness level does this email assume the reader is at?",
        "Could a competitor send this exact email with their product swapped in?",
        "What's the email's ONE job? Is every element serving that job?",
    ],
    anti_patterns=[
        "Analyzing the email body without considering subject + preview as a unit",
        "Ignoring CTA placement context — what comes BEFORE the button matters more than the button text",
        "Treating all emails as standalone instead of considering sequence position",
        "Missing mobile rendering considerations — most emails are read on phones",
        "Evaluating persuasion without considering the sender-recipient relationship stage",
    ],
)


# ── Framework Registry ──────────────────────────────────────────────

ALL_FRAMEWORKS: dict[str, ExtractionFramework] = {
    "landing_page": LANDING_PAGE_FRAMEWORK,
    "video": VIDEO_FRAMEWORK,
    "ad_creative": AD_CREATIVE_FRAMEWORK,
    "voc": VOC_FRAMEWORK,
    "research": RESEARCH_FRAMEWORK,
    "competitor": COMPETITOR_FRAMEWORK,
    "offer": OFFER_FRAMEWORK,
    "creative_concept": CREATIVE_CONCEPT_FRAMEWORK,
    "email": EMAIL_FRAMEWORK,
}


def get_framework_prompt(artifact_type: str) -> str:
    """Convert a framework into an injectable prompt section.

    This gets appended to the worker's system prompt so the LLM knows
    exactly what to extract and how to reason about it.
    """
    framework = ALL_FRAMEWORKS.get(artifact_type)
    if not framework:
        return ""

    lines = [
        f"## Extraction Framework: {framework.artifact_type}",
        f"Purpose: {framework.purpose}",
        "",
        "### Extraction Targets (extract ALL of these):",
    ]

    for t in framework.targets:
        examples = f" Examples: {'; '.join(t.examples)}" if t.examples else ""
        lines.append(f"- **{t.name}** [{t.priority}]: {t.description}{examples}")

    lines.append("")
    lines.append("### Reasoning Questions (answer after extraction):")
    for q in framework.reasoning_questions:
        lines.append(f"- {q}")

    lines.append("")
    lines.append("### Anti-Patterns (avoid these mistakes):")
    for ap in framework.anti_patterns:
        lines.append(f"- ❌ {ap}")

    return "\n".join(lines)
