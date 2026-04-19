"""Tests for the intelligence layer — skills, refinement, templates, benchmarks."""

import pytest


# ── Permissions / RBAC ──────────────────────────────────────────────

def test_role_permissions():
    from app.core.permissions import Permission, Role, has_permission

    assert has_permission("owner", Permission.DELETE_WORKSPACE)
    assert has_permission("admin", Permission.MANAGE_MEMBERS)
    assert not has_permission("viewer", Permission.GENERATE_CREATIVE)
    assert has_permission("creative", Permission.GENERATE_CREATIVE)
    assert not has_permission("creative", Permission.MANAGE_MEMBERS)
    assert has_permission("analyst", Permission.INGEST_PERFORMANCE)
    assert not has_permission("analyst", Permission.GENERATE_CREATIVE)
    assert has_permission("strategist", Permission.APPROVE_CONTENT)
    assert not has_permission("invalid_role", Permission.READ_ALL)


# ── Refinement Engine ───────────────────────────────────────────────

def test_refinement_criteria():
    from app.services.intelligence.refinement_engine import (
        CRITERIA_MAP,
        HOOK_CRITERIA,
        COPY_CRITERIA,
        IMAGE_CONCEPT_CRITERIA,
    )

    assert "hook_generation" in CRITERIA_MAP
    assert "copy_generation" in CRITERIA_MAP
    assert "image_concept_generation" in CRITERIA_MAP

    # Check criteria have required fields
    for criteria_list in [HOOK_CRITERIA, COPY_CRITERIA, IMAGE_CONCEPT_CRITERIA]:
        for c in criteria_list:
            assert c.name
            assert c.description
            assert c.weight > 0
            assert 1 <= c.min_score <= 10
            assert 1 <= c.max_score <= 10


def test_grade_result_dataclass():
    from app.services.intelligence.refinement_engine import GradeResult

    grade = GradeResult(
        scores={"specificity": 8, "proof_anchor": 6},
        overall_score=7.2,
        weaknesses=["Proof anchor could be stronger"],
        strengths=["Specific number used"],
        passes_threshold=True,
        pass_number=1,
    )
    assert grade.passes_threshold
    assert len(grade.weaknesses) == 1


# ── Template Library ────────────────────────────────────────────────

def test_base_templates_exist():
    from app.services.intelligence.template_library import BASE_TEMPLATES

    assert len(BASE_TEMPLATES) >= 20

    # Verify all templates have required fields
    for tmpl in BASE_TEMPLATES:
        assert tmpl.name
        assert tmpl.description
        assert tmpl.format_type in ("static", "video", "carousel", "email")
        assert tmpl.style in ("template", "native", "hybrid")
        assert len(tmpl.awareness_fit) > 0
        assert len(tmpl.platforms) > 0
        assert tmpl.structure
        assert tmpl.visual_direction


def test_template_format_coverage():
    from app.services.intelligence.template_library import BASE_TEMPLATES

    formats = set(t.format_type for t in BASE_TEMPLATES)
    assert "static" in formats
    assert "video" in formats
    assert "carousel" in formats
    assert "email" in formats


# ── Industry Benchmarks ─────────────────────────────────────────────

def test_industry_benchmarks():
    from app.api.v1.performance import INDUSTRY_BENCHMARKS

    assert len(INDUSTRY_BENCHMARKS) >= 14

    for industry, benchmarks in INDUSTRY_BENCHMARKS.items():
        assert "avg_cpa" in benchmarks
        assert "avg_roas" in benchmarks
        assert "avg_ctr" in benchmarks
        assert "avg_hook_rate" in benchmarks
        assert benchmarks["avg_cpa"] > 0
        assert benchmarks["avg_roas"] > 0


def test_performance_tier_classification():
    from app.api.v1.performance import _classify_tier, _safe_div
    from app.db.models.performance import WinningDefinition

    win_def = WinningDefinition(
        id="test",
        account_id="test",
        primary_metric="roas",
        winner_threshold=3.0,
        strong_threshold=2.0,
        average_threshold=1.0,
        weak_threshold=0.5,
        min_spend_for_evaluation=50.0,
        min_impressions_for_evaluation=1000,
    )

    assert _classify_tier(4.0, win_def, 100, 5000) == "winner"
    assert _classify_tier(2.5, win_def, 100, 5000) == "strong"
    assert _classify_tier(1.5, win_def, 100, 5000) == "average"
    assert _classify_tier(0.3, win_def, 100, 5000) == "loser"
    assert _classify_tier(2.0, win_def, 10, 5000) == "untested"  # spend too low
    assert _classify_tier(None, win_def, 100, 5000) == "untested"

    assert _safe_div(100, 5000) == 0.02
    assert _safe_div(100, 0) is None
    assert _safe_div(None, 5000) is None
    assert _safe_div(100, 5000, 1000) == 20.0


# ── Categorization Dimensions ───────────────────────────────────────

def test_categorization_dimensions():
    from app.services.intelligence.creative_library import CATEGORIZATION_DIMENSIONS

    assert "format_type" in CATEGORIZATION_DIMENSIONS
    assert "visual_style" in CATEGORIZATION_DIMENSIONS
    assert "hook_type" in CATEGORIZATION_DIMENSIONS
    assert "awareness_level" in CATEGORIZATION_DIMENSIONS
    assert "dr_tags" in CATEGORIZATION_DIMENSIONS
    assert "performance_tier" in CATEGORIZATION_DIMENSIONS

    # Each dimension should have at least 5 values
    for dim, values in CATEGORIZATION_DIMENSIONS.items():
        assert len(values) >= 5, f"{dim} has only {len(values)} values"


# ── Skill Domains ───────────────────────────────────────────────────

def test_skill_domains():
    from app.services.intelligence.skill_manager import SkillDomain

    assert len(SkillDomain) >= 10
    assert SkillDomain.HOOKS.value == "hooks"
    assert SkillDomain.COPY.value == "copy"
    assert SkillDomain.VISUALS.value == "visuals"


# ── Embedding Dimensions ───────────────────────────────────────────

def test_embedding_dimensions():
    from app.services.intelligence.embeddings import TEXT_EMBEDDING_DIM, VISUAL_EMBEDDING_DIM

    assert TEXT_EMBEDDING_DIM == 1536
    assert VISUAL_EMBEDDING_DIM == 1024


# ── Task Context ────────────────────────────────────────────────────

def test_task_context():
    from app.services.intelligence.skill_composer import TaskContext

    ctx = TaskContext(
        task_type="hook_generation",
        worker_name="hook_generator",
        format_type="static",
        awareness_level="problem_aware",
        platform="meta",
        task_description="Generate hooks for a cortisol supplement",
        include_domains=["hook", "copy"],
        max_per_domain=3,
        max_total=10,
    )

    assert ctx.task_type == "hook_generation"
    assert ctx.max_total == 10
    assert len(ctx.include_domains) == 2
