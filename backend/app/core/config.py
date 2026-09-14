from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Private Finance Agent"
    database_path: str = "./data/finance.db"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    ollama_categorizer_model: str = "qwen3:8b"
    ollama_timeout_seconds: float = 120.0

    cors_origins: str = "http://localhost:5173"

    gmail_credentials_path: str = "./.secrets/gmail_credentials.json"
    gmail_token_path: str = "./.secrets/gmail_token.json"
    gmail_query: str = '(debited OR credited OR "has been used") newer_than:90d'
    gmail_max_results: int = 100

    watcher_enabled: bool = True
    watcher_hour: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FINANCE_",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else BACKEND_ROOT / path

    @property
    def gmail_credentials_file(self) -> Path:
        return self._resolve(self.gmail_credentials_path)

    @property
    def gmail_token_file(self) -> Path:
        return self._resolve(self.gmail_token_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
