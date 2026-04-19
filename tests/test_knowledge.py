"""Tests for the knowledge system — training corpus, frameworks, synthesizer."""

import pytest


def test_training_context_loads():
    from app.knowledge.base_training import get_training_context

    ctx = get_training_context()
    assert len(ctx) > 5000
    assert "Mechanism" in ctx
    assert "Proof" in ctx
    assert "Awareness" in ctx


def test_training_context_without_examples():
    from app.knowledge.base_training import get_training_context

    with_examples = get_training_context(include_examples=True)
    without_examples = get_training_context(include_examples=False)
    assert len(with_examples) > len(without_examples)


def test_principles_count():
    from app.knowledge.base_training import CREATIVE_STRATEGY_PRINCIPLES

    principle_count = CREATIVE_STRATEGY_PRINCIPLES.count("### ")
    assert principle_count >= 15, f"Only {principle_count} principles — expected 15+"


def test_reasoning_frameworks_count():
    from app.knowledge.base_training import REASONING_FRAMEWORKS

    framework_count = REASONING_FRAMEWORKS.count("### ")
    assert framework_count >= 13, f"Only {framework_count} frameworks — expected 13+"


def test_few_shot_examples_count():
    from app.knowledge.base_training import FEW_SHOT_EXAMPLES

    example_count = FEW_SHOT_EXAMPLES.count("### Example")
    assert example_count >= 10, f"Only {example_count} examples — expected 10+"


def test_extraction_frameworks():
    from app.knowledge.extraction_frameworks import ALL_FRAMEWORKS, get_framework_prompt

    assert len(ALL_FRAMEWORKS) >= 9
    assert "landing_page" in ALL_FRAMEWORKS
    assert "video" in ALL_FRAMEWORKS
    assert "competitor" in ALL_FRAMEWORKS
    assert "offer" in ALL_FRAMEWORKS
    assert "creative_concept" in ALL_FRAMEWORKS
    assert "email" in ALL_FRAMEWORKS

    # Each framework should produce a non-empty prompt
    for name in ALL_FRAMEWORKS:
        prompt = get_framework_prompt(name)
        assert len(prompt) > 100, f"Framework '{name}' prompt too short"

    # Non-existent framework returns empty string
    assert get_framework_prompt("nonexistent") == ""


def test_extraction_framework_structure():
    from app.knowledge.extraction_frameworks import ALL_FRAMEWORKS

    for name, framework in ALL_FRAMEWORKS.items():
        assert framework.artifact_type == name
        assert framework.purpose
        assert len(framework.targets) >= 5, f"{name} has only {len(framework.targets)} targets"
        assert len(framework.reasoning_questions) >= 3, f"{name} has too few reasoning questions"
        assert len(framework.anti_patterns) >= 3, f"{name} has too few anti-patterns"

        # Every target has required fields
        for target in framework.targets:
            assert target.name
            assert target.description
            assert target.evidence_type
            assert target.priority in ("critical", "high", "medium", "low")


def test_synthesizer_produces_sections():
    from app.knowledge.synthesizer import synthesize_full_corpus

    sections = synthesize_full_corpus()
    assert len(sections) >= 30

    domains = set(s.domain for s in sections)
    assert "creative_strategy" in domains
    assert "reasoning" in domains
    assert "extraction" in domains
    assert "worker_behavior" in domains

    types = set(s.section_type for s in sections)
    assert "principle" in types
    assert "framework" in types


def test_synthesizer_markdown_export():
    from app.knowledge.synthesizer import export_markdown

    md = export_markdown()
    assert len(md) > 10000
    assert "# Creative Strategy Training Corpus" in md
    assert "## Creative Strategy" in md


def test_synthesizer_training_pairs():
    from app.knowledge.synthesizer import export_training_pairs

    pairs = export_training_pairs()
    assert len(pairs) >= 30

    # Every pair has required fields
    for pair in pairs:
        assert "instruction" in pair
        assert "output" in pair
        assert "domain" in pair
