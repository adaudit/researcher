"""Celery Beat schedule for recurring research and reflection jobs.

Weekly and daily jobs that operationalize compounding research:
  - Top ad refresh (weekly)
  - Comments/reviews refresh (weekly)
  - Landing page diff (weekly)
  - News monitor (daily)
  - Literature refresh (weekly)
  - Performance feedback ingest (daily)
  - Memory reflection (weekly)
  - Iteration synthesis (weekly)
"""

from celery.schedules import crontab

from app.orchestrator.engine import celery_app

celery_app.conf.beat_schedule = {
    # ── Daily jobs ──
    "daily-news-monitor": {
        "task": "app.orchestrator.workflows.weekly_refresh.run_news_monitor",
        "schedule": crontab(hour=6, minute=0),  # 6:00 AM UTC daily
        "options": {"queue": "workflows"},
    },
    "daily-performance-ingest": {
        "task": "app.orchestrator.workflows.weekly_refresh.run_performance_ingest",
        "schedule": crontab(hour=7, minute=0),  # 7:00 AM UTC daily
        "options": {"queue": "workflows"},
    },

    # ── Weekly jobs (Monday mornings) ──
    "weekly-top-ad-refresh": {
        "task": "app.orchestrator.workflows.weekly_refresh.run_top_ad_refresh",
        "schedule": crontab(hour=5, minute=0, day_of_week=1),
        "options": {"queue": "workflows"},
    },
    "weekly-voc-refresh": {
        "task": "app.orchestrator.workflows.weekly_refresh.run_voc_refresh",
        "schedule": crontab(hour=5, minute=30, day_of_week=1),
        "options": {"queue": "workflows"},
    },
    "weekly-landing-page-diff": {
        "task": "app.orchestrator.workflows.weekly_refresh.run_landing_page_diff",
        "schedule": crontab(hour=6, minute=0, day_of_week=1),
        "options": {"queue": "workflows"},
    },
    "weekly-literature-refresh": {
        "task": "app.orchestrator.workflows.weekly_refresh.run_literature_refresh",
        "schedule": crontab(hour=6, minute=30, day_of_week=1),
        "options": {"queue": "workflows"},
    },
    "weekly-memory-reflection": {
        "task": "app.orchestrator.workflows.weekly_refresh.run_memory_reflection",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),
        "options": {"queue": "workflows"},
    },
    "weekly-iteration-synthesis": {
        "task": "app.orchestrator.workflows.weekly_refresh.run_iteration_synthesis",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),
        "options": {"queue": "workflows"},
    },
}
