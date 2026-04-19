"""Shared test fixtures."""

import pytest


@pytest.fixture
def account_id() -> str:
    return "acct_test123"


@pytest.fixture
def offer_id() -> str:
    return "offer_test456"


@pytest.fixture
def sample_offer_payload() -> dict:
    return {
        "name": "Test Supplement",
        "mechanism": "Proprietary blend of adaptogens that reduce cortisol",
        "cta": "Try Risk-Free for 30 Days",
        "price_point": 49.99,
        "price_model": "subscription",
        "product_url": "https://example.com/product",
        "target_audience": "Adults 35-55 experiencing chronic stress",
        "awareness_level": "problem_aware",
        "regulated_category": "health",
        "domain_risk_level": "elevated",
        "proof_basis": {
            "clinical_study": True,
            "testimonials": True,
            "expert_endorsement": False,
        },
    }
