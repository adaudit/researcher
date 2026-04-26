"""Tests for worker contracts and execution."""

import pytest

from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput
from app.workers.copy_shape_police import CopyShapePoliceWorker
from app.workers.compression_tax import CompressionTaxWorker


def test_skill_contract_shape():
    """Every worker must define a complete skill contract."""
    worker = CopyShapePoliceWorker()
    contract = worker.contract

    assert isinstance(contract, SkillContract)
    assert contract.skill_name
    assert contract.purpose
    assert len(contract.accepted_input_types) > 0
    assert isinstance(contract.recall_scope, list)
    assert isinstance(contract.write_scope, list)
    assert len(contract.steps) > 0
    assert len(contract.quality_checks) > 0


def test_worker_input_defaults():
    """WorkerInput should have sane defaults."""
    inp = WorkerInput(account_id="acct_1")
    assert inp.account_id == "acct_1"
    assert inp.offer_id is None
    assert inp.artifact_ids == []
    assert inp.params == {}


def test_worker_output_defaults():
    """WorkerOutput should have sane defaults."""
    out = WorkerOutput(worker_name="test", success=True)
    assert out.worker_name == "test"
    assert out.success is True
    assert out.data == {}
    assert out.observations == []
    assert out.errors == []
    assert out.quality_warnings == []
    assert out.requires_review is False


def test_compression_tax_contract():
    """Compression tax worker has a valid contract."""
    worker = CompressionTaxWorker()
    assert worker.contract.skill_name == "compression_tax"
    assert "compression" in worker.contract.purpose.lower() or "cut" in worker.contract.purpose.lower()


# ── Trace capture ──────────────────────────────────────────────────


def test_router_trace_capture_off_by_default():
    """Without start_trace_capture, _record_trace is a no-op."""
    from app.services.llm.router import _record_trace, pop_traces, Capability, Provider

    # No active capture — pop returns empty even after a record attempt
    _record_trace(
        Capability.STRATEGIC_REASONING, Provider.ANTHROPIC,
        "claude", "sys", "user", {"ok": True},
    )
    assert pop_traces() == []


def test_router_trace_capture_records_calls():
    """Once started, _record_trace appends to the buffer."""
    from app.services.llm.router import (
        Capability, Provider, _record_trace, pop_traces, start_trace_capture,
    )

    start_trace_capture()
    _record_trace(
        Capability.CREATIVE_GENERATION, Provider.ZAI,
        "glm-5.1", "system A", "user A", {"hooks": []},
    )
    _record_trace(
        Capability.STRATEGIC_REASONING, Provider.GOOGLE,
        "gemini-2.5-flash", "system B", "user B", {"_parse_error": True},
    )

    traces = pop_traces()
    assert len(traces) == 2
    assert traces[0]["capability"] == "creative_generation"
    assert traces[0]["provider"] == "zai"
    assert traces[0]["model"] == "glm-5.1"
    assert traces[0]["quality_score"] == 1
    assert traces[1]["quality_score"] == 0  # _parse_error -> 0


def test_pop_traces_clears_buffer():
    """pop_traces should reset the buffer so the next worker run starts fresh."""
    from app.services.llm.router import (
        Capability, Provider, _record_trace, pop_traces, start_trace_capture,
    )

    start_trace_capture()
    _record_trace(
        Capability.SYNTHESIS, Provider.ANTHROPIC,
        "claude-opus-4-6", "sys", "user", {"ok": True},
    )
    first = pop_traces()
    assert len(first) == 1

    # Buffer is now disabled until next start_trace_capture()
    _record_trace(
        Capability.SYNTHESIS, Provider.ANTHROPIC,
        "claude-opus-4-6", "sys", "user", {"ok": True},
    )
    assert pop_traces() == []


@pytest.mark.asyncio
async def test_base_worker_captures_router_traces(monkeypatch):
    """BaseWorker.run() should pull captured traces and ship them to the collector."""
    from app.services.llm.router import _record_trace, Capability, Provider
    from app.workers import base as base_module

    captured: list[dict] = []

    class FakeCollector:
        def capture(self, **kwargs):
            captured.append(kwargs)

    monkeypatch.setattr(base_module, "_get_training_collector", lambda: FakeCollector())

    class _Contract:
        skill_name = "test_worker"

    class TestWorker(BaseWorker):
        contract = SkillContract(
            skill_name="test_worker",
            purpose="Test",
            accepted_input_types=["test"],
            recall_scope=[],
            write_scope=[],
        )

        async def execute(self, worker_input):
            # Simulate a router call inside execute()
            _record_trace(
                Capability.CREATIVE_GENERATION, Provider.ANTHROPIC,
                "claude-opus-4-6", "system text", "user text",
                {"result": "ok"},
            )
            return WorkerOutput(
                worker_name="test_worker", success=True, data={"k": "v"},
            )

    out = await TestWorker().run(WorkerInput(account_id="acct_test", offer_id="offer_test"))

    assert out.success
    assert len(captured) == 1
    trace = captured[0]
    assert trace["worker_name"] == "test_worker"
    assert trace["capability"] == "creative_generation"
    assert trace["provider"] == "anthropic"
    assert trace["model"] == "claude-opus-4-6"
    assert trace["account_id"] == "acct_test"
    assert trace["offer_id"] == "offer_test"
    assert trace["quality_score"] == 1
    # Legacy stash should not leak into output.data
    assert "_llm_trace" not in out.data


@pytest.mark.asyncio
async def test_base_worker_legacy_trace_still_captured(monkeypatch):
    """Workers that still stash _llm_trace in data should be captured (back-compat)."""
    from app.workers import base as base_module

    captured: list[dict] = []

    class FakeCollector:
        def capture(self, **kwargs):
            captured.append(kwargs)

    monkeypatch.setattr(base_module, "_get_training_collector", lambda: FakeCollector())

    class LegacyWorker(BaseWorker):
        contract = SkillContract(
            skill_name="legacy_worker",
            purpose="Test",
            accepted_input_types=["test"],
            recall_scope=[],
            write_scope=[],
        )

        async def execute(self, worker_input):
            return WorkerOutput(
                worker_name="legacy_worker",
                success=True,
                data={
                    "result": "ok",
                    "_llm_trace": {
                        "capability": "text_extraction",
                        "provider": "anthropic",
                        "model": "claude-haiku-4-5",
                        "system_prompt": "sys",
                        "user_prompt": "user",
                        "response": "{}",
                        "quality_score": 1,
                    },
                },
            )

    out = await LegacyWorker().run(WorkerInput(account_id="acct"))

    assert out.success
    assert len(captured) == 1
    assert captured[0]["capability"] == "text_extraction"
    # Stash should be removed from output.data so it doesn't leak
    assert "_llm_trace" not in out.data
