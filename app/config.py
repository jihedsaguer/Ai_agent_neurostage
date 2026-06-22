from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str = ""
    UPLOAD_DIR: str = "./uploads"
    UPLOAD_BASE_URL: str = "http://localhost:3000"
    NESTJS_INTERNAL_URL: str = "http://app:3000"
    INTERNAL_SECRET: str
    ENVIRONMENT: str = "development"
    LLM_PROVIDER: str = "ollama"
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    GENERATION_MODEL: str = "llama3.2"
    EMBEDDING_DIMENSIONS: int = 768

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
