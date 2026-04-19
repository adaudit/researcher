"""Tests for workflow engine state machine."""

from app.orchestrator.engine import VALID_TRANSITIONS, validate_transition


def test_valid_transitions():
    assert validate_transition("queued", "acquiring") is True
    assert validate_transition("acquiring", "normalizing") is True
    assert validate_transition("normalizing", "retaining") is True
    assert validate_transition("retaining", "reasoning") is True
    assert validate_transition("reasoning", "reflecting") is True
    assert validate_transition("reflecting", "approved") is True
    assert validate_transition("approved", "published") is True


def test_invalid_transitions():
    assert validate_transition("queued", "published") is False
    assert validate_transition("published", "queued") is False
    assert validate_transition("acquiring", "approved") is False


def test_failure_transitions():
    for state in ["queued", "acquiring", "normalizing", "retaining",
                  "reasoning", "reflecting", "approved"]:
        assert validate_transition(state, "failed") is True


def test_retry_from_failed():
    assert validate_transition("failed", "queued") is True
