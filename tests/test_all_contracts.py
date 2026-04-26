"""Tests for all worker contracts — every worker must have a valid contract."""

import importlib
import pkgutil

import pytest

from app.workers.base import BaseWorker, SkillContract


def _discover_workers() -> list[type[BaseWorker]]:
    """Find all BaseWorker subclasses across the workers package."""
    import app.workers as workers_pkg

    worker_classes: list[type[BaseWorker]] = []

    for _, module_name, _ in pkgutil.iter_modules(workers_pkg.__path__):
        if module_name in ("base",):
            continue
        try:
            mod = importlib.import_module(f"app.workers.{module_name}")
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseWorker)
                    and attr is not BaseWorker
                    and hasattr(attr, "contract")
                ):
                    worker_classes.append(attr)
        except ImportError:
            pass

    return worker_classes


ALL_WORKERS = _discover_workers()


@pytest.mark.parametrize("worker_cls", ALL_WORKERS, ids=lambda w: w.__name__)
def test_worker_contract_complete(worker_cls):
    """Every worker must have a fully defined skill contract."""
    contract = worker_cls.contract

    assert isinstance(contract, SkillContract), f"{worker_cls.__name__} missing SkillContract"
    assert contract.skill_name, f"{worker_cls.__name__} missing skill_name"
    assert contract.purpose, f"{worker_cls.__name__} missing purpose"
    assert len(contract.accepted_input_types) > 0, f"{worker_cls.__name__} has no accepted_input_types"
    assert isinstance(contract.recall_scope, list), f"{worker_cls.__name__} recall_scope not a list"
    assert isinstance(contract.write_scope, list), f"{worker_cls.__name__} write_scope not a list"
    assert len(contract.steps) > 0, f"{worker_cls.__name__} has no steps"
    assert len(contract.quality_checks) > 0, f"{worker_cls.__name__} has no quality_checks"


@pytest.mark.parametrize("worker_cls", ALL_WORKERS, ids=lambda w: w.__name__)
def test_worker_skill_names_unique(worker_cls):
    """No two workers should share the same skill_name."""
    names = [w.contract.skill_name for w in ALL_WORKERS]
    assert names.count(worker_cls.contract.skill_name) == 1, (
        f"Duplicate skill_name: {worker_cls.contract.skill_name}"
    )


def test_worker_count():
    """We should have at least 25 workers."""
    assert len(ALL_WORKERS) >= 25, f"Only found {len(ALL_WORKERS)} workers"
