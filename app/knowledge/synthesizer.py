"""Training corpus synthesizer — exports all knowledge as structured markdown.

Produces a single, human-readable markdown document that doubles as
ML training material. The output is structured so that:

1. A human can read it front-to-back and understand the entire creative
   strategy system
2. An ML pipeline can parse it into (instruction, response) training pairs
3. A fine-tuning job can use it as a system prompt corpus

The export format uses consistent heading levels and tagged sections
so automated parsers can split it into chunks:

  # <domain>
  ## <topic>
  ### Principle / Framework / Example
  #### Instruction (what the model should do)
  #### Response (what good output looks like)
  #### Anti-pattern (what bad output looks like)

Export targets:
  - Full markdown document (docs/training_corpus.md)
  - JSONL training pairs (for fine-tuning)
  - System prompt fragments (for prompt injection)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TrainingSection:
    """One section of the training corpus."""

    domain: str          # e.g. "creative_strategy", "extraction", "reasoning"
    topic: str           # e.g. "mechanism_bridge", "voc_mining"
    section_type: str    # principle | framework | example | anti_pattern | vocabulary
    title: str
    content: str
    instruction: str = ""  # what the model should DO with this knowledge
    good_example: str = ""
    bad_example: str = ""
    tags: list[str] | None = None


def synthesize_full_corpus() -> list[TrainingSection]:
    """Pull all knowledge sources and synthesize into TrainingSection list.

    Sources:
      1. base_training.py — built-in principles, frameworks, examples
      2. extraction_frameworks.py — per-artifact extraction guides
      3. systems.py — worker system prompts (define behaviors)
      4. corpus/ — user-ingested documents
    """
    sections: list[TrainingSection] = []

    sections.extend(_extract_from_base_training())
    sections.extend(_extract_from_extraction_frameworks())
    sections.extend(_extract_from_system_prompts())
    sections.extend(_extract_from_corpus_store())

    return sections


def _extract_from_base_training() -> list[TrainingSection]:
    """Parse base_training.py constants into sections."""
    from app.knowledge.base_training import (
        CREATIVE_STRATEGY_PRINCIPLES,
        FEW_SHOT_EXAMPLES,
        REASONING_FRAMEWORKS,
    )

    sections: list[TrainingSection] = []

    # Parse principles
    for block in _split_markdown_sections(CREATIVE_STRATEGY_PRINCIPLES, "###"):
        title, body = _split_title_body(block)
        if not title:
            continue
        sections.append(TrainingSection(
            domain="creative_strategy",
            topic=_slugify(title),
            section_type="principle",
            title=title,
            content=body,
            instruction=f"Apply the principle '{title}' when evaluating or creating creative strategy outputs.",
            tags=["core_principle"],
        ))

    # Parse reasoning frameworks
    for block in _split_markdown_sections(REASONING_FRAMEWORKS, "###"):
        title, body = _split_title_body(block)
        if not title:
            continue
        sections.append(TrainingSection(
            domain="reasoning",
            topic=_slugify(title),
            section_type="framework",
            title=title,
            content=body,
            instruction=f"Use the '{title}' framework when reasoning about creative strategy decisions.",
            tags=["reasoning_framework"],
        ))

    # Parse few-shot examples
    for block in _split_markdown_sections(FEW_SHOT_EXAMPLES, "###"):
        title, body = _split_title_body(block)
        if not title:
            continue

        good = ""
        bad = ""
        # Split into GOOD and BAD sections
        if "GOOD" in body and "BAD" in body:
            parts = body.split("GOOD")
            if len(parts) >= 2:
                bad_part = parts[0]
                good_part = parts[1]
                if "BAD" in bad_part:
                    bad = bad_part.split("BAD")[-1].strip().strip(":()")
                good = good_part.strip().strip(":()")

        sections.append(TrainingSection(
            domain="calibration",
            topic=_slugify(title),
            section_type="example",
            title=title,
            content=body,
            instruction=f"When performing '{title.replace('Example ', '').split(':')[0]}', produce output matching the GOOD example, never the BAD example.",
            good_example=good[:2000] if good else "",
            bad_example=bad[:1000] if bad else "",
            tags=["few_shot", "calibration"],
        ))

    return sections


def _extract_from_extraction_frameworks() -> list[TrainingSection]:
    """Parse extraction_frameworks.py into sections."""
    from app.knowledge.extraction_frameworks import ALL_FRAMEWORKS

    sections: list[TrainingSection] = []

    for name, framework in ALL_FRAMEWORKS.items():
        # Main framework section
        targets_text = "\n".join(
            f"- **{t.name}** [{t.priority}]: {t.description}"
            + (f" Examples: {'; '.join(t.examples)}" if t.examples else "")
            for t in framework.targets
        )

        questions_text = "\n".join(f"- {q}" for q in framework.reasoning_questions)
        antipatterns_text = "\n".join(f"- {ap}" for ap in framework.anti_patterns)

        full_content = (
            f"**Purpose:** {framework.purpose}\n\n"
            f"**Extraction Targets:**\n{targets_text}\n\n"
            f"**Reasoning Questions:**\n{questions_text}\n\n"
            f"**Anti-Patterns:**\n{antipatterns_text}"
        )

        sections.append(TrainingSection(
            domain="extraction",
            topic=name,
            section_type="framework",
            title=f"{name.replace('_', ' ').title()} Extraction Framework",
            content=full_content,
            instruction=f"When analyzing a {name.replace('_', ' ')}, extract ALL of the listed targets. Answer the reasoning questions after extraction. Avoid the listed anti-patterns.",
            tags=["extraction", name],
        ))

    return sections


def _extract_from_system_prompts() -> list[TrainingSection]:
    """Parse worker system prompts into behavioral sections."""
    import app.prompts.systems as prompts_mod

    # Collect all *_SYSTEM constants from the prompts module
    prompts: dict[str, str] = {}
    for attr_name in dir(prompts_mod):
        if attr_name.endswith("_SYSTEM") and attr_name.isupper():
            val = getattr(prompts_mod, attr_name)
            if isinstance(val, str):
                # Convert OFFER_INTELLIGENCE_SYSTEM → offer_intelligence
                worker_name = attr_name.replace("_SYSTEM", "").lower()
                prompts[worker_name] = val

    sections: list[TrainingSection] = []

    for worker_name, prompt_text in prompts.items():
        title = worker_name.replace("_", " ").title()

        # Extract rules and quality tests from the prompt
        rules = ""
        quality_test = ""
        for block in prompt_text.split("##"):
            block_stripped = block.strip()
            if block_stripped.lower().startswith("rules"):
                rules = block_stripped
            elif "test" in block_stripped.lower() or "standard" in block_stripped.lower():
                quality_test = block_stripped

        sections.append(TrainingSection(
            domain="worker_behavior",
            topic=worker_name,
            section_type="principle",
            title=f"{title} — Role & Rules",
            content=prompt_text,
            instruction=f"When acting as the {title}, follow these rules exactly. Violating any rule produces output that will be rejected.",
            tags=["system_prompt", worker_name],
        ))

    return sections


def _extract_from_corpus_store() -> list[TrainingSection]:
    """Load user-ingested corpus and convert to sections."""
    try:
        from app.knowledge.doc_ingest.store import corpus_store
    except ImportError:
        return []

    sections: list[TrainingSection] = []
    entries = corpus_store.list_all()

    for meta in entries:
        slug = meta.get("slug", "")
        entry = corpus_store.get(slug)
        if not entry:
            continue

        source = entry.get("title", slug)

        for p in entry.get("principles", []):
            sections.append(TrainingSection(
                domain="ingested",
                topic=_slugify(p.get("name", "")),
                section_type="principle",
                title=p.get("name", ""),
                content=p.get("description", ""),
                instruction=f"Apply this principle from '{source}' in creative strategy work.",
                tags=["ingested", slug],
            ))

        for f in entry.get("frameworks", []):
            steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(f.get("steps", [])))
            sections.append(TrainingSection(
                domain="ingested",
                topic=_slugify(f.get("name", "")),
                section_type="framework",
                title=f.get("name", ""),
                content=f"{f.get('description', '')}\n\nSteps:\n{steps}\n\nWhen to use: {f.get('when_to_use', '')}",
                instruction=f"Use this framework from '{source}' when applicable.",
                tags=["ingested", slug],
            ))

        for e in entry.get("examples", []):
            sections.append(TrainingSection(
                domain="ingested",
                topic=_slugify(e.get("context", "")[:40]),
                section_type="example",
                title=f"Example: {e.get('context', '')}",
                content=e.get("why_good_is_better", ""),
                good_example=e.get("good_version", ""),
                bad_example=e.get("bad_version", ""),
                tags=["ingested", slug],
            ))

        for ap in entry.get("anti_patterns", []):
            sections.append(TrainingSection(
                domain="ingested",
                topic=_slugify(ap.get("name", "")),
                section_type="anti_pattern",
                title=ap.get("name", ""),
                content=f"{ap.get('description', '')}\n\n**Instead:** {ap.get('what_to_do_instead', '')}",
                instruction=f"Avoid this anti-pattern. {ap.get('what_to_do_instead', '')}",
                tags=["ingested", slug, "anti_pattern"],
            ))

    return sections


# ── Export Functions ────────────────────────────────────────────────


def export_markdown(output_path: str | None = None) -> str:
    """Export the full training corpus as a structured markdown document.

    The output is designed to be:
    1. Readable by humans as a complete creative strategy guide
    2. Parseable by ML pipelines into training chunks
    3. Usable as a system prompt corpus for new models

    Returns the markdown string and optionally writes to disk.
    """
    sections = synthesize_full_corpus()

    lines: list[str] = [
        "# Creative Strategy Training Corpus",
        "",
        f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"> Sections: {len(sections)}",
        f"> Domains: {', '.join(sorted(set(s.domain for s in sections)))}",
        "",
        "This document contains the complete creative strategy knowledge base.",
        "It serves as both a human learning guide and machine learning training corpus.",
        "",
        "---",
        "",
    ]

    # Group by domain
    domains: dict[str, list[TrainingSection]] = {}
    for s in sections:
        domains.setdefault(s.domain, []).append(s)

    # Emit in a logical order
    domain_order = [
        "creative_strategy", "reasoning", "extraction",
        "calibration", "worker_behavior", "ingested",
    ]
    for domain in domain_order:
        if domain not in domains:
            continue

        domain_sections = domains[domain]
        domain_title = domain.replace("_", " ").title()
        lines.append(f"## {domain_title}")
        lines.append("")

        # Group by section_type within domain
        by_type: dict[str, list[TrainingSection]] = {}
        for s in domain_sections:
            by_type.setdefault(s.section_type, []).append(s)

        type_order = ["principle", "framework", "example", "anti_pattern", "vocabulary"]
        for stype in type_order:
            if stype not in by_type:
                continue

            type_title = stype.replace("_", " ").title() + "s"
            lines.append(f"### {type_title}")
            lines.append("")

            for section in by_type[stype]:
                lines.append(f"#### {section.title}")
                lines.append("")

                if section.instruction:
                    lines.append(f"**Instruction:** {section.instruction}")
                    lines.append("")

                lines.append(section.content)
                lines.append("")

                if section.good_example:
                    lines.append("**Good Example:**")
                    lines.append(f"```\n{section.good_example}\n```")
                    lines.append("")

                if section.bad_example:
                    lines.append("**Bad Example (avoid this):**")
                    lines.append(f"```\n{section.bad_example}\n```")
                    lines.append("")

                if section.tags:
                    lines.append(f"*Tags: {', '.join(section.tags)}*")
                    lines.append("")

                lines.append("---")
                lines.append("")

    # Add remaining domains not in the explicit order
    for domain, domain_sections in domains.items():
        if domain in domain_order:
            continue
        lines.append(f"## {domain.replace('_', ' ').title()}")
        lines.append("")
        for section in domain_sections:
            lines.append(f"#### {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")
            lines.append("---")
            lines.append("")

    md_text = "\n".join(lines)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(md_text)
        logger.info("corpus.exported_markdown path=%s sections=%d chars=%d", path, len(sections), len(md_text))

    return md_text


def export_training_pairs(output_path: str | None = None) -> list[dict[str, str]]:
    """Export corpus as (instruction, response) JSONL training pairs.

    Each section becomes a training pair where:
    - instruction = what the model should do
    - input = context or scenario (if applicable)
    - response = the knowledge/behavior to learn

    This format works for:
    - Alpaca-style fine-tuning (instruction, input, output)
    - ChatML fine-tuning (system, user, assistant)
    - DPO training (chosen vs rejected from good/bad examples)
    """
    sections = synthesize_full_corpus()
    pairs: list[dict[str, str]] = []

    for section in sections:
        # Standard instruction pair
        pair: dict[str, str] = {
            "instruction": section.instruction or f"Explain the concept: {section.title}",
            "input": "",
            "output": section.content,
            "domain": section.domain,
            "topic": section.topic,
            "type": section.section_type,
        }

        if section.tags:
            pair["tags"] = ",".join(section.tags)

        pairs.append(pair)

        # If we have good/bad examples, create DPO pairs
        if section.good_example and section.bad_example:
            pairs.append({
                "instruction": section.instruction or f"Perform: {section.title}",
                "input": f"Task: {section.title}",
                "chosen": section.good_example,
                "rejected": section.bad_example,
                "domain": section.domain,
                "topic": section.topic,
                "type": "dpo_pair",
            })

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for pair in pairs:
                f.write(json.dumps(pair) + "\n")
        logger.info("corpus.exported_pairs path=%s count=%d", path, len(pairs))

    return pairs


def export_system_prompt_fragments(output_path: str | None = None) -> dict[str, str]:
    """Export domain-specific system prompt fragments.

    Each domain gets a consolidated text block that can be injected
    as a system prompt for models working in that domain. Useful for:
    - Custom GPTs / Assistants
    - Claude Projects
    - Any system that needs domain expertise as a system prompt
    """
    sections = synthesize_full_corpus()

    fragments: dict[str, str] = {}
    by_domain: dict[str, list[TrainingSection]] = {}
    for s in sections:
        by_domain.setdefault(s.domain, []).append(s)

    for domain, domain_sections in by_domain.items():
        lines = [f"# {domain.replace('_', ' ').title()} Knowledge Base\n"]
        for s in domain_sections:
            lines.append(f"## {s.title}\n")
            lines.append(s.content)
            lines.append("")
        fragments[domain] = "\n".join(lines)

    if output_path:
        path = Path(output_path)
        path.mkdir(parents=True, exist_ok=True)
        for domain, text in fragments.items():
            fpath = path / f"{domain}.md"
            fpath.write_text(text)
        logger.info("corpus.exported_fragments path=%s domains=%d", path, len(fragments))

    return fragments


# ── Helpers ─────────────────────────────────────────────────────────


def _split_markdown_sections(text: str, heading_prefix: str) -> list[str]:
    """Split markdown text by heading level."""
    sections = []
    current: list[str] = []

    for line in text.split("\n"):
        if line.strip().startswith(heading_prefix) and not line.strip().startswith(heading_prefix + "#"):
            if current:
                sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        sections.append("\n".join(current))

    return sections


def _split_title_body(section: str) -> tuple[str, str]:
    """Split a markdown section into title and body."""
    lines = section.strip().split("\n")
    if not lines:
        return "", ""

    title = lines[0].lstrip("#").strip()
    # Remove numbering like "1. " or "A. "
    import re
    title = re.sub(r"^\d+\.\s*", "", title)
    title = re.sub(r"^[A-Z]\.\s*", "", title)

    body = "\n".join(lines[1:]).strip()
    return title, body


def _slugify(text: str) -> str:
    """Convert text to a slug."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:60].strip("-")
