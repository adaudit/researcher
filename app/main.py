from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import router as api_v1_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ARG001
    # Startup: initialize connections, warm caches, etc.
    yield
    # Shutdown: cleanup
    from app.db.session import engine

    await engine.dispose()


app = FastAPI(
    title="Researcher — Creative Strategy SaaS",
    description=(
        "Hindsight-first creative strategy operating system. "
        "Converts raw market evidence into structured strategic assets."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}
