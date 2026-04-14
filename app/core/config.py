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

    # Auth
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    JWT_ALGORITHM: str = "HS256"


settings = Settings()
