from fastapi import APIRouter

from app.api.v1.accounts import router as accounts_router
from app.api.v1.artifacts import router as artifacts_router
from app.api.v1.iterations import router as iterations_router
from app.api.v1.landing_pages import router as landing_pages_router
from app.api.v1.memory import router as memory_router
from app.api.v1.offers import router as offers_router
from app.api.v1.research_cycles import router as research_cycles_router
from app.api.v1.strategy import router as strategy_router
from app.api.v1.webhooks import router as webhooks_router

router = APIRouter()
router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
router.include_router(offers_router, prefix="/offers", tags=["offers"])
router.include_router(artifacts_router, prefix="/artifacts", tags=["artifacts"])
router.include_router(research_cycles_router, prefix="/research-cycles", tags=["research-cycles"])
router.include_router(landing_pages_router, prefix="/landing-page", tags=["landing-page"])
router.include_router(memory_router, prefix="/memory", tags=["memory"])
router.include_router(strategy_router, prefix="/strategy-map", tags=["strategy"])
router.include_router(iterations_router, prefix="/iteration-headers", tags=["iterations"])
router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
