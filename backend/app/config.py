from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:123456@localhost:5432/paper_reader"

    PDF_EXTRACTOR: str = "pymupdf4llm"
    CHUNK_MAX_CHARS: int = 2200
    
    LLM_API_KEY: str = "api-key"
    LLM_MODEL: str = "gpt-5.4-mini"
    LLM_BASE_URL: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

settings = Settings()

#gpt-5.4-mini
#Input：$0.75 / 1M tokens
#Output：$4.50 / 1M tokens