# Centralized runtime settings loaded from .env and exposed as a typed settings object.

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Application settings loaded from environment variables.
class Settings(BaseSettings):
    # Required in .env for deployment.
    # Example: postgresql://postgres:123456@localhost:5432/paper_reader
    DATABASE_URL: str

    PDF_EXTRACTOR: str = "pymupdf4llm"
    CHUNK_MAX_CHARS: int = 2200
    ENABLE_DEBUG_EXPORTS: bool = False

    # Upload and resource protection limits.
    # Set to 0 or a negative number to disable a count-based limit.
    MAX_UPLOAD_MB: int = 30
    MAX_PAPERS_PER_USER: int = 10
    MAX_PROCESSING_PAPERS_PER_USER: int = 1
    MAX_FILENAME_LENGTH: int = 255
    PDF_UPLOAD_CHUNK_BYTES: int = 1024 * 1024
    UPLOAD_DIR: str = "uploads"

    # Logging settings.
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    # Background worker / queue settings.
    WORKER_POLL_INTERVAL_SECONDS: int = 2
    WORKER_MAX_ATTEMPTS: int = 2
    WORKER_TASK_TIMEOUT_MINUTES: int = 30
    WORKER_HEARTBEAT_INTERVAL_SECONDS: int = 30

    # Pipeline settings.
    # When enabled, a successful parse_overview task automatically queues
    # Chinese translation after parse_status=processed and overview_status=completed.
    AUTO_TRANSLATE_AFTER_PARSE: bool = True

    # Storage cleanup settings.
    # Incoming files are temporary files saved before a paper row is fully created.
    # Orphan scans only log by default; enable auto delete only after reviewing logs.
    INCOMING_FILE_TTL_HOURS: int = 24
    ENABLE_ORPHAN_FILE_SCAN: bool = True
    AUTO_DELETE_ORPHAN_FILES: bool = False

    # LLM settings. Keep the real API key in .env, never in source code.
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-5.4-mini"
    LLM_BASE_URL: str | None = None

    # CORS origins for the frontend. Comma-separated list.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Temporary development user before school SSO is connected.
    DEV_USER_OID: str = "dev-user"
    DEV_USER_EMAIL: str = "dev@example.com"
    DEV_USER_NAME: str = "Dev User"
    DEV_TENANT_ID: str = "dev-tenant"

    # Reserved for the later school-login/session/JWT bridge.
    SESSION_SECRET_KEY: str = "change-this-before-deploy"
    JWT_SECRET_KEY: str = "change-this-before-deploy"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def upload_dir_path(self) -> Path:
        upload_dir = Path(self.UPLOAD_DIR)
        if upload_dir.is_absolute():
            return upload_dir
        return PROJECT_ROOT / upload_dir

    @property
    def log_dir_path(self) -> Path:
        log_dir = Path(self.LOG_DIR)
        if log_dir.is_absolute():
            return log_dir
        return PROJECT_ROOT / log_dir


settings = Settings()
