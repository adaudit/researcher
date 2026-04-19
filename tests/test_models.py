"""Tests for database models — ensure all models are importable and well-formed."""

import pytest


def test_all_models_import():
    from app.db.models import (
        Account,
        Artifact,
        AudienceTargeting,
        CreativeAnalysis,
        CreativeAsset,
        DemographicBreakdown,
        IngestQuestion,
        IterationHeader,
        ObservationRecord,
        Offer,
        PerformanceSnapshot,
        SkillComponent,
        SkillComposition,
        StrategyOutput,
        SwipeEntry,
        User,
        WinningDefinition,
        WorkflowJob,
        WorkspaceMembership,
    )

    assert Account.__tablename__ == "accounts"
    assert User.__tablename__ == "users"
    assert CreativeAsset.__tablename__ == "creative_assets"
    assert PerformanceSnapshot.__tablename__ == "performance_snapshots"
    assert SkillComponent.__tablename__ == "skill_components"
    assert WinningDefinition.__tablename__ == "winning_definitions"


def test_model_count():
    from app.db.models import __all__

    assert len(__all__) >= 17, f"Only {len(__all__)} models — expected 17+"


def test_bank_types():
    from app.services.hindsight.banks import BankType

    assert len(BankType) >= 11
    assert BankType.SEEDS.value == "seeds"
    assert BankType.PRIMERS.value == "primers"
    assert BankType.SKILLS.value == "skills"
    assert BankType.GLOBAL.value == "global"


def test_bank_specs_complete():
    from app.services.hindsight.banks import BANK_SPECS, BankType

    for bank_type in BankType:
        assert bank_type in BANK_SPECS, f"Missing BankSpec for {bank_type.value}"
        spec = BANK_SPECS[bank_type]
        assert spec.description
        assert spec.default_memory_type in ("world_fact", "experience", "mental_model")


def test_recall_scope_covers_all_workers():
    from app.services.hindsight.banks import recall_scope_for_worker

    workers_that_need_scope = [
        "offer_intelligence", "creative_ingest", "voc_miner",
        "audience_psychology", "hook_engineer", "brief_composer",
        "copy_generator", "hook_generator", "headline_generator",
        "coverage_matrix", "ad_analyzer", "creative_producer",
    ]

    for worker in workers_that_need_scope:
        scope = recall_scope_for_worker(worker, "acct_test")
        assert len(scope) > 0, f"Worker '{worker}' has empty recall scope"


def test_workflow_states():
    from app.orchestrator.engine import WORKFLOW_STATES, VALID_TRANSITIONS

    assert "queued" in WORKFLOW_STATES
    assert "published" in WORKFLOW_STATES
    assert "failed" in WORKFLOW_STATES

    # Every state has defined transitions (even if empty)
    for state in WORKFLOW_STATES:
        assert state in VALID_TRANSITIONS


def test_primer_types():
    from app.knowledge.primers import PrimerType

    assert PrimerType.AD.value == "ad_primer"
    assert PrimerType.HOOK.value == "hook_primer"
    assert PrimerType.HEADLINE.value == "headline_primer"
