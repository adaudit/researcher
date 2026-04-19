"""Tests for worker contracts and execution."""

from app.workers.base import SkillContract, WorkerInput, WorkerOutput
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
