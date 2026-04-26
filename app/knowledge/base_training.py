"""Base training corpus — the system's foundational creative strategy knowledge.

This is NOT static documentation. It is injected as context into worker
prompts via prompt caching, so the LLM has domain expertise before it
sees any specific account data. It covers:

  1. What good creative strategy looks like (principles)
  2. What to extract from each artifact type (extraction guides)
  3. How to reason about extracted data (reasoning frameworks)
  4. Examples of good vs bad output (few-shot calibration)

The training corpus is versioned — when the team learns something new
about what works, it gets added here and every worker benefits.
"""

import logging

logger = logging.getLogger(__name__)


# ── Core Principles ─────────────────────────────────────────────────

CREATIVE_STRATEGY_PRINCIPLES = """\
## Core Creative Strategy Principles

### 1. Research Before Ideation
Creative quality is determined by research quality. A brief built on deep
customer language and real proof will always outperform one built on
assumptions. The sequence is: evidence → insight → strategy → execution.

### 2. The Mechanism Is the Strategy
Every offer has a mechanism — how it actually delivers the result.
The mechanism is what separates a real offer from a generic promise.
Creative strategy that doesn't connect to the mechanism produces
interchangeable copy that any competitor could use.

### 3. Proof Is Not Optional
Claims without proof are liabilities. The hierarchy:
- Scientific proof > Authority proof > Social proof > Product proof > Logical proof
A claim without corresponding proof must be flagged, not published.

### 4. Awareness Determines Everything
A hook that works for product-aware audiences fails for problem-aware.
Every piece of creative output must declare its awareness level target.
The Schwartz spectrum: Unaware → Problem Aware → Solution Aware →
Product Aware → Most Aware.

### 5. The Anti-Generic Test
For every headline, claim, or hook: "Could a direct competitor put their
logo on this and use it unchanged?" If yes, it fails. Specificity comes
from mechanism, proof, and exact customer language — not adjectives.

### 6. Compression Over Expansion
More words ≠ more persuasion. Every sentence must earn its place through
proof, mechanism connection, emotional shift, or narrative function.
Generic filler destroys credibility and attention.

### 7. Customer Language > Copywriter Language
The words customers actually use to describe their problem are more
persuasive than polished marketing language. Preserve exact phrases.
"I'm tired of waking up at 3am" > "Struggling with sleep issues?"

### 8. Iteration Is the System
The first version is a hypothesis. Weekly research cycles reveal what
the market actually responds to. Every iteration must be evidence-backed,
not opinion-backed. What changed in the data → what should change in the copy.

### 9. Desire Mapping Before Hook Writing
You cannot write a good hook without knowing what the audience actually
wants. Desire maps must come from evidence (VOC, comments, reviews),
not from assumptions about the audience.

### 10. The Consequence Frame
Differentiation isn't "we're better." It's "because we do X differently,
the consequence for you is Y." This requires knowing what competitors
actually do (sameness mapping) before claiming difference.

### 11. Creative Diversity Is the System
Creative diversity is not just "try different styles." It operates on
three levels, and all three must be covered to find new winning clusters:

**Level 1 — Segments (Who you're talking to):**
A segment = Demographics/Identity × Core Pain/Promise × Constraints.
Constraints are the "but" factor — "I want healthy plants BUT it has
to be organic." Some segments are broad (scale), some are specific (tails).
A healthy mix of both is essential.

**Level 2 — Awareness Levels (Where you meet them):**
Unaware → Problem Aware → Solution Aware → Product Aware → Most Aware.
Each segment has different awareness levels. 5 segments × 5 levels = 25
distinct creative buckets. Most accounts only test 3-4.

**Level 3 — CASH (The creative DNA):**
Concepts, Angles, Styles, and Hooks. Style is only ONE component — most
people think "creative diversity" means "try UGC and founder-led." That
misses 75% of the landscape. Messaging diversity (concepts, angles, hooks)
is what actually prevents clustering.

Think Battleship: spread your shots → find ships → saturate around wins.
Ecology: a healthy ad account has many species, not all primates.
Avoid local maximums: if you only test on one peak, you never find
the higher peaks elsewhere.

### 12. Hook First, Always
40-60% of writing effort should be on the hook. The hook determines
whether anyone reads the rest. A mediocre ad with a lethal hook will
outperform a perfect ad with a generic opener. Hooks must be:
- Specific (exact numbers, exact language, exact pain)
- Mechanism-connected (bridges to the product's actual solution)
- Proof-anchored (something provable, not just a claim)
- Awareness-matched (unaware hooks ≠ product-aware hooks)

### 13. Primers Are Living Documents
The three foundational documents for any account:
- **Ad Primer**: 10-12 winning ads separated by ###
- **Hook Primer**: 10-12 winning hooks
- **Headline Primer**: 10-12 winning headlines
These evolve as the account evolves. Winners from this cycle become
next cycle's primer material. This is the compounding flywheel.

### 14. The 60/10/10/20 Rule
Time allocation for creative production:
- Ideation: 50% (finding ideas is THE highest-leverage activity)
- Brief: 10% (polishing seeds into the strongest possible ideas)
- Writing: 10% (should be almost mechanical with good briefs and primers)
- Creative/Visual: 20% (images and video)
- Analysis: 10% (reviewing what worked and why)
Most people spend 50% on writing and wonder why they run out of ideas.

### 15. Net New Is the Leverage
Everything in the creative process is for NET NEW creatives — brand new
ad concepts that don't exist in the account. Iterations on winners are
a different, simpler process. If you can nail net new creative generation,
everything else becomes trivial. Net new is where the real leverage is.\
"""


# ── Reasoning Frameworks ────────────────────────────────────────────

REASONING_FRAMEWORKS = """\
## Reasoning Frameworks for Creative Strategy

### A. The Belief Transfer Chain
Every piece of persuasive content is a belief transfer chain:
1. Current belief (what the reader believes now)
2. Required shift (what must change for them to buy)
3. Evidence for shift (proof that makes the shift feel inevitable)
4. New belief (what they believe after consuming the content)

When analyzing a page or ad, map the belief chain. Where is it broken?
Where is the shift unsupported? Where is there a leap without evidence?

### B. The Proof-to-Claim Ratio
For every claim in a piece of copy, there should be at least one
supporting proof element. Calculate:
- Claims made: count distinct promises or assertions
- Proof provided: count distinct evidence elements
- Ratio < 1:1 = proof gap (dangerous)
- Ratio > 2:1 = proof-rich (strong)

### C. The Awareness-Level Filter
Before evaluating any creative, determine the audience awareness level.
Then evaluate through that lens:
- Unaware: Does the hook create curiosity without assuming the problem?
- Problem Aware: Does it validate the pain and introduce a new frame?
- Solution Aware: Does it differentiate the mechanism from alternatives?
- Product Aware: Does it handle objections and prove claims?
- Most Aware: Does it provide urgency and remove final friction?

### D. The Mechanism Bridge Test
A mechanism bridge connects the hook's promise to how the product
actually delivers. Test:
1. Hook makes promise P
2. Product has mechanism M
3. Is there a clear logical path from P → M?
If the hook promises "better sleep" but the mechanism is about cortisol,
the bridge is: "better sleep ← reduced nighttime cortisol ← this ingredient"

### E. The Sameness-Before-Difference Framework
Before claiming differentiation:
1. List what EVERY competitor in the category says
2. List what THIS offer says that matches the category
3. Only the non-overlapping elements are true differentiators
4. Build consequence framing only around true differentiators

### F. The VOC Mining Hierarchy
When extracting from customer language:
1. Exact phrases (most valuable — direct quotes)
2. Recurring patterns (multiple people saying similar things)
3. Intensity markers (words showing strong emotion or urgency)
4. Objection clusters (recurring doubts and concerns)
5. Desire contradictions (wanting two conflicting things)

### G. The Iteration Evidence Chain
Every iteration must follow:
1. What data changed? (new comments, performance drop, competitor shift)
2. What does it mean? (pattern, not isolated observation)
3. What should change in the creative? (specific section, specific direction)
4. What outcome proves it worked? (measurable, falsifiable)
5. What stays the same? (explicit preservation list)

### H. The Creative Coverage Matrix
Evaluate creative diversity using the three-level framework:
1. Map all active ads to: Segment × Awareness Level × CASH type
2. Identify clusters (where are you testing the same thing repeatedly?)
3. Identify gaps (which segments have zero ads? which awareness levels?)
4. Prioritize: test gaps first, then iterate on proven clusters
Like Battleship — if all your shots are in one quadrant, you're missing ships.

### I. The STORMING Source Diversity Framework
When generating ideas, pull from multiple sources to ensure natural diversity:
- **S**wipes: Competitor ads currently spending money
- **T**emplates: Proven ad format structures
- **O**rganic: Viral outliers from social platforms outside paid ads
- **R**esearch: Books, forums, comments, YouTube — real customer language
- **M**atrix: Explicit creative diversity audit using the coverage matrix
- **I**nternal Vectors: Patterns hidden in your own winners
- **N**ew Styles: Emerging visual and structural formats
- **G**ambits: Your own creative instincts and guesses
If you only use 1-2 sources, you cluster. Using a spread naturally creates
diversity across segments, awareness levels, and messaging types.

### J. The Hook-First Writing Framework
When generating ad copy from a brief:
1. Generate 10-20 hooks first (from hook primer + brief)
2. Push for strength: "make these 10 hooks even stronger"
3. Pick the best hook(s)
4. Generate 2-4 full ad copies using winning hook + ad primer + brief
5. Pick the best copy
6. Generate 10 headlines using headline primer + finished copy
7. Pick the best headline
The hook determines everything. Don't start with body copy.

### K. The Primer-Based Generation Framework
When writing anything, always ground it in proven winners:
1. Load the relevant primer (ad/hook/headline)
2. Use the primer as style and quality calibration
3. Combine primer patterns with brief-specific direction
4. Generate multiple options (stochastic — like MidJourney giving 4 images)
5. Pick the best, not the first
Primers compound: winners → primers → better output → new winners → better primers.

### L. The Seed Bank Accumulation Framework
Seeds are raw ideation sparks that accumulate across weeks:
1. Each ideation cycle generates 50-100 seeds from diverse sources
2. Seeds are tagged by source type (STORMING letter)
3. Seeds accumulate in the seed bank — never deleted
4. Each cycle, review accumulated seeds for emerging patterns
5. After 12 weeks: 1,200+ seeds to mine, cross-reference, and evolve
The seed bank is both an AI flywheel (more data → better patterns) and
an instinct flywheel (reviewing seeds sharpens human pattern recognition).

### M. The SCRAWLS Visual Concept Framework
For generating scroll-stopping ad images, pull from 7 sources:
- **S**wipes: Competitor visual formats currently spending money
- **C**opy-Derived: Literal image concepts from finished ad text
- **R**eptile Triggers: 13 primal psychological triggers (bizarre, voyeur,
  suffering, sexual, primal fear, inside joke, old/vintage, victory lap,
  selfie, uncanny object, ultra-real, gory/visceral, wildcard)
- **A**udience Language: Customer words turned into visual scenes
- **W**ild Sourcing: Real images from Reddit, forums, social — not ads
- **L**oopback: Expand winning image vectors from your own account
- **S**ource: Your own instinctive visual ideas
The image does NOT need to logically connect to the product. Disconnected,
native-looking, "what the fuck am I looking at" images often perform best.
Format: 1:1 or 4:5 only. Must look native to feed, NOT polished.\
"""


# ── Few-Shot Examples ────────────────────────────────────────────────

FEW_SHOT_EXAMPLES = """\
## Calibration: Good vs Bad Output Examples

### Example 1: Hook Analysis

BAD (generic, any competitor could use this):
{
  "hook": "Discover the secret to better sleep",
  "awareness_level": "problem_aware",
  "analysis": "This hook appeals to people who want better sleep"
}

GOOD (specific, mechanism-connected, evidence-backed):
{
  "hook": "Your cortisol spikes at 3am — here's what your doctor won't test for",
  "awareness_level": "problem_aware",
  "desire_anchor": "Pain cluster: '3am wake-ups' mentioned in 14/47 comments",
  "proof_anchor": "2024 endocrine study showing nocturnal cortisol correlation",
  "mechanism_connection": "Product's adaptogen blend targets HPA axis regulation",
  "anti_generic_check": "Competitors focus on melatonin — this hook is mechanism-specific",
  "why_it_works": "Combines exact customer language ('3am') with medical specificity that positions the product's mechanism as the answer competitors aren't offering"
}

### Example 2: Landing Page Claim Extraction

BAD (paraphrased, no page reference):
{
  "claim": "The product helps with weight loss",
  "type": "benefit"
}

GOOD (exact text, sourced, proof-linked):
{
  "claim_text": "Lost 23 lbs in 90 days without changing my diet",
  "claim_type": "testimonial_outcome_claim",
  "exact_location": "Section 3, testimonial carousel, slide 2",
  "supporting_proof": "Before/after photo adjacent, but no verification method shown",
  "risk_assessment": "Specific outcome claim in health category — requires FTC-compliant substantiation",
  "proof_gap": "No clinical study backing the '90 days' timeframe claim"
}

### Example 3: VOC Mining

BAD (summarized, lost the actual language):
{
  "theme": "Customers want to feel more energetic",
  "count": 8
}

GOOD (exact phrases preserved, clustered with intensity):
{
  "theme": "afternoon_energy_crash",
  "intensity": "high",
  "frequency": 8,
  "exact_phrases": [
    "I literally cannot function after 2pm",
    "the afternoon crash is RUINING my productivity",
    "I need something that doesn't make me crash at 3pm",
    "every single afternoon I hit a wall"
  ],
  "implied_desire": "Sustained energy without the crash cycle",
  "language_note": "They say 'crash' not 'fatigue' — use 'crash' in copy",
  "objection_nearby": "3 of these commenters also mentioned skepticism about stimulants"
}

### Example 4: Proof Inventory

BAD (no hierarchy, no gaps):
{
  "proof": ["clinical study", "testimonials", "doctor endorsement"]
}

GOOD (hierarchical, gap-identified, strength-rated):
{
  "proof_hierarchy": {
    "scientific": [{
      "claim": "40% reduction in cortisol after 8 weeks",
      "source": "Journal of Clinical Endocrinology, 2024",
      "strength": "strong — peer-reviewed, n=200, double-blind",
      "usability": "Can cite directly. Include journal name for authority."
    }],
    "authority": [{
      "claim": "Recommended by Dr. Sarah Chen, endocrinologist",
      "source": "Product website",
      "strength": "medium — real doctor but paid endorsement not disclosed",
      "usability": "Use name and credential. Add disclosure."
    }],
    "social": [{
      "claim": "12,000+ customers",
      "source": "Website footer",
      "strength": "weak — no verification, common inflation tactic",
      "usability": "Can reference but don't anchor proof chain to it"
    }]
  },
  "proof_gaps": [
    "No long-term safety data beyond 8 weeks",
    "No comparison study vs. competing products",
    "Testimonials lack verification methodology"
  ],
  "strongest_proof_chain": "Peer-reviewed study → Doctor endorsement → Specific customer outcomes"
}

### Example 5: Iteration Header

BAD (vague, no evidence, no hypothesis):
{
  "target": "Improve the headline",
  "reason": "It could be better"
}

GOOD (specific, evidence-backed, falsifiable):
{
  "asset_type": "landing_page",
  "asset_section": "hero_headline",
  "target": "Replace generic benefit headline with consequence-led opener anchored in the 3am cortisol spike proof",
  "reason": "Current headline 'Sleep Better Tonight' scores 2/10 on specificity — it's category-generic. CTR on page is 1.2% vs 3.4% category average. VOC data shows '3am wake-ups' is the highest-frequency pain phrase (14/47 comments).",
  "evidence_refs": ["voc_cluster_3am_wakeups", "proof_cortisol_study_2024", "perf_ctr_last_30d"],
  "constraint": "Must not change the mechanism section or CTA. Maintain health compliance.",
  "expected_effect": "CTR improvement to 2.5%+ by matching the dominant pain language",
  "test_hypothesis": "If we lead with the specific pain ('3am wake-ups') instead of the generic benefit ('better sleep'), CTR will increase because we match the exact language pattern from 30% of VOC data"
}

### Example 6: Brief Writing (Seed → Brief)

BAD (vague, no direction, no source grounding):
{
  "brief": "Write an ad about how the supplement helps with sleep. Use a testimonial angle."
}

GOOD (specific, source-grounded, creatively open):
{
  "brief": "A problem-aware ad that opens with the exact moment of 3am wakefulness — that specific, miserable clarity where you're staring at the ceiling knowing tomorrow is ruined. The emotional core is quiet desperation mixed with resignation ('this is just my life now'). The mechanism bridge: the reason you wake at 3am isn't insomnia — it's a cortisol spike your body can't regulate. This product's adaptogen blend targets the HPA axis, which is the actual system that controls that 3am spike. The tone should feel like a friend who finally figured it out, not a doctor lecturing. Source: VOC cluster '3am wake-ups' (14/47 comments), cortisol study from Journal of Clinical Endocrinology 2024.",
  "awareness_level": "problem_aware",
  "segment": "Women 35-55, chronic sleep issues, skeptical of melatonin",
  "source_material": "Reddit comment: 'I literally lie there from 3am to 5am every single night just waiting for the alarm. I've tried everything.'",
  "mechanism_bridge": "3am wakeup → cortisol spike → HPA axis dysregulation → adaptogen blend targets HPA",
  "what_makes_it_interesting": "Nobody in the category is talking about WHY you wake at 3am. Everyone says 'better sleep' — this says 'your cortisol is spiking.'"
}

### Example 7: Hook Generation

BAD (generic hooks with no specificity):
[
  "Discover the secret to better sleep",
  "This changed my life",
  "You won't believe what happened"
]

GOOD (specific, mechanism-connected, proof-anchored):
[
  {
    "hook": "Your cortisol spikes at 3am. Here's what your doctor won't test for.",
    "type": "problem_aware_medical_curiosity",
    "proof_anchor": "cortisol_study_2024",
    "why_it_works": "Exact time (3am) from VOC + medical specificity competitors don't use"
  },
  {
    "hook": "I was the woman who 'tried everything' for sleep. Then I stopped trying to fix my sleep and started fixing my cortisol.",
    "type": "problem_aware_identity_shift",
    "proof_anchor": "voc_cluster_tried_everything",
    "why_it_works": "Identity language ('the woman who') + reframe from symptom to mechanism"
  },
  {
    "hook": "23 lbs lighter. Zero diet changes. My doctor thought I was lying.",
    "type": "product_aware_outcome",
    "proof_anchor": "testimonial_23lbs_90days",
    "why_it_works": "Specific number + no-effort angle + authority surprise (doctor's reaction)"
  }
]

### Example 8: Creative Concept (Copy → Image)

BAD (literal product shot):
{
  "concept": "Product bottle on a white background",
  "style": "clean product photography"
}

GOOD (scroll-stopping, native, emotionally provocative):
{
  "concept": "Extreme close-up of bloodshot eyes reflected in a phone screen showing 3:04 AM. The phone brightness illuminates tear-dampened skin. Shot looks like it was taken by the person themselves.",
  "source": "copy_derived + reptile_trigger_ultra_real",
  "scroll_stop_score": 9,
  "native_feed_score": 10,
  "product_connection": "None directly — the image is the FEELING. The copy does the selling.",
  "format": "1:1 square",
  "generation_notes": "Must look like a real iPhone photo, NOT AI-generated. RAW mode, stylization 0."
}

### Example 9: Seed Evaluation

BAD SEED (too vague to become a brief):
"Something about how stress affects sleep"

GOOD SEED (specific enough to develop into a brief):
{
  "seed": "Silver as a health ingredient — keep seeing it referenced in competitor ads and trending on TikTok health. Nobody in our category is talking about colloidal silver even though 3 competitors are quietly adding it. Could be a new angle cluster.",
  "source": "internal_vector (pattern in competitor monitoring)",
  "potential": "high — completely untapped in our messaging",
  "segment_coverage": "opens solution-aware + unaware angles we don't have",
  "next_step": "Research silver claims, check regulatory constraints, develop 2-3 brief variations"
}

### Example 10: Creative Coverage Matrix Gap Report

BAD (no structure, just vibes):
"We should try more UGC and maybe some different audiences"

GOOD (structured gap analysis across all three levels):
{
  "coverage_analysis": {
    "segment_coverage": {
      "active": ["Women 35-55 chronic pain", "Men 40-60 joint health"],
      "untested": ["Athletes 25-40 recovery", "Parents 30-45 energy/fatigue"],
      "gap_severity": "high — 2 of 4 identified segments have zero ads"
    },
    "awareness_coverage": {
      "over_indexed": "product_aware (60% of ads)",
      "under_indexed": "unaware (5% of ads), problem_aware (10%)",
      "gap_severity": "critical — barely reaching top-of-funnel audiences"
    },
    "cash_coverage": {
      "concepts_tested": 8,
      "angles_tested": 4,
      "styles_tested": 3,
      "hooks_tested": 12,
      "clustering": "Heavy clustering on testimonial concept + UGC style. Zero paradoxical, zero fear-based, zero research-led."
    }
  },
  "recommended_priorities": [
    "Unaware ads for Athletes 25-40 — completely untapped segment and awareness level",
    "Problem-aware ads using research/scientific angles — zero in account",
    "Paradoxical or fear-based hooks — current hooks are 100% promise-based"
  ]
}\
"""


def get_training_context(
    include_examples: bool = True,
    include_corpus: bool = True,
    corpus_budget: int = 50_000,
) -> str:
    """Assemble the full training context for injection into worker prompts.

    Combines built-in corpus (principles, frameworks, examples) with
    user-ingested corpus files from app/knowledge/corpus/.

    This gets cached via prompt caching so it's essentially free
    after the first call per worker.
    """
    parts = [CREATIVE_STRATEGY_PRINCIPLES, REASONING_FRAMEWORKS]
    if include_examples:
        parts.append(FEW_SHOT_EXAMPLES)

    # Load user-ingested corpus if available
    if include_corpus:
        try:
            from app.knowledge.doc_ingest.store import corpus_store
            corpus_context = corpus_store.load_all_for_context(max_chars=corpus_budget)
            if corpus_context:
                parts.append(corpus_context)
        except Exception as exc:
            # Corpus loading is best-effort — workers run with built-in
            # principles only. Log so missing corpus is visible.
            logger.warning("training_context.corpus_load_failed error=%s", exc)

    return "\n\n---\n\n".join(parts)
