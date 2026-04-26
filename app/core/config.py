from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Application
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    API_V1_PREFIX: str = "/v1"
    DEBUG: bool = False

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://researcher:researcher_dev@localhost:5432/researcher"
    DATABASE_URL_SYNC: str = "postgresql://researcher:researcher_dev@localhost:5432/researcher"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Object Storage (S3-compatible)
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_ARTIFACTS: str = "researcher-artifacts"
    S3_BUCKET_MEDIA: str = "researcher-media"
    S3_REGION: str = "us-east-1"

    # Hindsight
    HINDSIGHT_API_KEY: str = ""
    HINDSIGHT_BASE_URL: str = "https://api.hindsight.dev"

    # LLM Providers
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # External APIs
    META_AD_LIBRARY_ACCESS_TOKEN: str = ""
    NCBI_API_KEY: str = ""

    # Z.ai (GLM-5.1 — cheap high-quality reasoning, OpenAI-compatible API)
    ZAI_API_KEY: str = ""
    ZAI_BASE_URL: str = "https://open.z.ai/api/paas/v4"  # OpenAI-compatible
    ZAI_MODEL: str = "glm-5.1"

    # Local LLM (Ollama, vLLM — any OpenAI-compatible server)
    LOCAL_LLM_BASE_URL: str = ""  # e.g. "http://localhost:11434/v1" for Ollama
    LOCAL_LLM_MODEL: str = ""     # e.g. "gemma4:26b", "gemma4:31b", "llama3.3:70b"

    # xAI / Grok (hooks, headlines, punchy short-form — X-corpus-trained)
    XAI_API_KEY: str = ""
    XAI_BASE_URL: str = "https://api.x.ai/v1"
    XAI_MODEL: str = "grok-4"
    XAI_FAST_MODEL: str = "grok-4.1-fast"

    # TwelveLabs (video embeddings via Marengo — $0.0015/min)
    TWELVELABS_API_KEY: str = ""
    TWELVELABS_BASE_URL: str = "https://api.twelvelabs.io/v1.3"
    TWELVELABS_EMBED_MODEL: str = "Marengo-retrieval-2.7"

    # SerpAPI (Google Scholar search — free tier 250/month)
    SERPAPI_KEY: str = ""

    # Acquisition — ScrapCreators (social platform data)
    SCRAPECREATORS_API_KEY: str = ""
    SCRAPECREATORS_BASE_URL: str = "https://api.scrapecreators.com/v1"

    # Auth
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    JWT_ALGORITHM: str = "HS256"


settings = Settings()
