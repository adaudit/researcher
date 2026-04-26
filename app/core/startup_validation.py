"""Startup validation — fail fast on missing required config in production.

Prevents silent degradation when API keys are missing. Logs warnings for
optional keys and raises on truly required keys when APP_ENV=production.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


REQUIRED_IN_PRODUCTION = [
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "HINDSIGHT_API_KEY",
]

REQUIRED_AT_LEAST_ONE_LLM = [
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ZAI_API_KEY",
    "XAI_API_KEY",
]

OPTIONAL_BUT_LOGGED = [
    "SCRAPECREATORS_API_KEY",
    "SERPAPI_KEY",
    "BFL_API_KEY",
    "IDEOGRAM_API_KEY",
    "META_AD_LIBRARY_ACCESS_TOKEN",
    "NCBI_API_KEY",
    "TWELVELABS_API_KEY",
]


def validate_startup_config() -> None:
    """Validate config at startup. Raises in production if required keys missing.

    Always logs the configuration state so deploys are traceable.
    """
    is_prod = settings.APP_ENV.lower() in ("production", "prod")

    # SECRET_KEY check — production must change the default
    if is_prod and settings.SECRET_KEY == "change-me-in-production":
        raise RuntimeError(
            "SECRET_KEY must be changed from the default in production"
        )

    # Required-in-prod keys
    missing_required: list[str] = []
    for key in REQUIRED_IN_PRODUCTION:
        value = getattr(settings, key, "")
        if not value:
            missing_required.append(key)

    if missing_required and is_prod:
        raise RuntimeError(
            f"Required config missing in production: {', '.join(missing_required)}"
        )
    elif missing_required:
        logger.warning(
            "config.missing_keys env=%s keys=%s — workers may fail",
            settings.APP_ENV, missing_required,
        )

    # At-least-one LLM provider must be configured
    available_llm = [
        k for k in REQUIRED_AT_LEAST_ONE_LLM
        if getattr(settings, k, "")
    ]

    if not available_llm and is_prod:
        raise RuntimeError(
            "No LLM provider configured. At least one of "
            f"{REQUIRED_AT_LEAST_ONE_LLM} must be set."
        )
    elif not available_llm:
        logger.warning(
            "config.no_llm_provider — at least one LLM key recommended"
        )
    else:
        logger.info(
            "config.llm_providers_configured providers=%s",
            [k.replace("_API_KEY", "").lower() for k in available_llm],
        )

    # Optional keys — log so missing ones are visible
    missing_optional = [
        k for k in OPTIONAL_BUT_LOGGED
        if not getattr(settings, k, "")
    ]
    if missing_optional:
        logger.info(
            "config.optional_keys_missing keys=%s — degraded acquisition/generation",
            missing_optional,
        )

    logger.info(
        "config.validated env=%s debug=%s api_prefix=%s",
        settings.APP_ENV, settings.DEBUG, settings.API_V1_PREFIX,
    )
