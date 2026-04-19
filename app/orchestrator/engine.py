"""Celery-based workflow orchestrator.

Acts as the control plane for all research and strategy workflows.
Each workflow is a deterministic sequence of typed actions with
explicit state transitions:

  queued -> acquiring -> normalizing -> retaining -> reasoning ->
  reflecting -> approved -> published

The orchestrator coordinates acquisition, normalization, and specialized
workers that all read from and write to Hindsight as the central
memory substrate.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from celery import Celery

from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "researcher",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,   # 10 minute soft limit
    task_time_limit=900,        # 15 minute hard limit
    task_routes={
        "app.orchestrator.workflows.*": {"queue": "workflows"},
        "app.orchestrator.engine.*": {"queue": "default"},
        "autonomous.*": {"queue": "autonomous"},
    },
)

# ── Celery Beat Schedule ──────────────────────────────────────────
# Autonomous crons that run the system without human intervention.

celery_app.conf.beat_schedule = {
    # Every hour: process new performance data → update skills
    "hourly-learning": {
        "task": "autonomous.hourly_learning",
        "schedule": 3600.0,
    },
    # Every 24 hours: news monitor, competitor scan, new styles scan
    "daily-research": {
        "task": "autonomous.daily_research",
        "schedule": 86400.0,
    },
    # Every 7 days: full reflection + coverage matrix + primer audit
    "weekly-full-cycle": {
        "task": "autonomous.weekly_full_cycle",
        "schedule": 604800.0,
    },
    # Every 30 days: cross-business intelligence aggregation
    "monthly-cross-business": {
        "task": "autonomous.monthly_cross_business",
        "schedule": 2592000.0,
    },
    # Existing weekly refresh tasks
    "weekly-top-ad-refresh": {
        "task": "app.orchestrator.workflows.weekly_refresh.run_top_ad_refresh",
        "schedule": 604800.0,
    },
    "weekly-memory-reflection": {
        "task": "app.orchestrator.workflows.weekly_refresh.run_memory_reflection",
        "schedule": 604800.0,
    },
    "weekly-iteration-synthesis": {
        "task": "app.orchestrator.workflows.weekly_refresh.run_iteration_synthesis",
        "schedule": 604800.0,
    },
}

# Register autonomous tasks lazily to avoid circular imports.
# Celery discovers them when the worker process starts.
celery_app.conf.update(
    include=["app.orchestrator.autonomous"],
)


# ── Workflow state machine ──────────────────────────────────────────

WORKFLOW_STATES = [
    "queued",
    "acquiring",
    "normalizing",
    "retaining",
    "reasoning",
    "reflecting",
    "approved",
    "published",
    "failed",
]

VALID_TRANSITIONS: dict[str, list[str]] = {
    "queued": ["acquiring", "failed"],
    "acquiring": ["normalizing", "failed"],
    "normalizing": ["retaining", "failed"],
    "retaining": ["reasoning", "failed"],
    "reasoning": ["reflecting", "approved", "failed"],
    "reflecting": ["approved", "failed"],
    "approved": ["published", "failed"],
    "published": [],
    "failed": ["queued"],  # allow retry
}


def validate_transition(current: str, target: str) -> bool:
    return target in VALID_TRANSITIONS.get(current, [])


def build_step_log_entry(step: str, status: str, detail: str = "") -> dict:
    return {
        "step": step,
        "status": status,
        "ts": datetime.now(timezone.utc).isoformat(),
        "detail": detail,
    }
