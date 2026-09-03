from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    database_url: str = "sqlite:///./local.db"
    ai_provider: str = "auto"  # auto | openai | ollama | simulated
    openai_api_key: str | None = None
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"
    api_key: str | None = None  # optional Bearer auth
    rate_limit_per_minute: int = 30


settings = Settings()
