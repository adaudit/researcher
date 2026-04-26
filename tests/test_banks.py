"""Tests for Hindsight bank model."""

from app.services.hindsight.banks import (
    BankType,
    bank_id_for,
    recall_scope_for_worker,
)


def test_bank_id_generation():
    assert bank_id_for("acct_1", BankType.CORE) == "acct_1_core"
    assert bank_id_for("acct_1", BankType.CREATIVE) == "acct_1_creatives"
    assert bank_id_for("acct_1", BankType.VOC) == "acct_1_voc"
    assert bank_id_for("acct_1", BankType.REFLECTION) == "acct_1_reflections"


def test_offer_bank_id_generation():
    assert bank_id_for("acct_1", BankType.OFFER, "offer_7") == "acct_1_offer_offer_7"
    # Non-offer banks ignore offer_id
    assert bank_id_for("acct_1", BankType.CORE, "offer_7") == "acct_1_core"


def test_recall_scope_for_known_worker():
    scope = recall_scope_for_worker("hook_engineer", "acct_1", "offer_7")
    assert "acct_1_offer_offer_7" in scope
    assert "acct_1_voc" in scope
    assert "acct_1_creatives" in scope
    assert "acct_1_reflections" in scope


def test_recall_scope_for_landing_page_analyzer():
    scope = recall_scope_for_worker("landing_page_analyzer", "acct_1", "offer_7")
    assert "acct_1_pages" in scope
    assert "acct_1_offer_offer_7" in scope
    # Should NOT include VOC or creative
    assert "acct_1_voc" not in scope
    assert "acct_1_creatives" not in scope


def test_recall_scope_for_unknown_worker():
    scope = recall_scope_for_worker("nonexistent_worker", "acct_1")
    assert scope == []
