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
actually do (sameness mapping) before claiming difference.\
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
5. What stays the same? (explicit preservation list)\
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
}\
"""


def get_training_context(include_examples: bool = True) -> str:
    """Assemble the full training context for injection into worker prompts.

    This gets cached via prompt caching so it's essentially free
    after the first call per worker.
    """
    parts = [CREATIVE_STRATEGY_PRINCIPLES, REASONING_FRAMEWORKS]
    if include_examples:
        parts.append(FEW_SHOT_EXAMPLES)
    return "\n\n---\n\n".join(parts)
