from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Automation Platform API"
    app_version: str = "0.3.0"
    environment: str = "development"
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'automation_platform.db').as_posix()}"
    allowed_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    cookie_secure: bool = False
    session_hours: int = Field(default=8, ge=1, le=24)
    max_attempts: int = Field(default=3, ge=1, le=10)
    execution_timeout_seconds: int = Field(default=300, ge=10)
    worker_poll_seconds: float = Field(default=1, ge=0.1)
    power_automate_url: SecretStr = SecretStr("")
    power_automate_token: SecretStr = SecretStr("")
    power_automate_callback_secret: SecretStr = SecretStr("")
    power_automate_idempotent: bool = False
    public_api_base_url: str = "http://127.0.0.1:8000"
    local_runner_enabled: bool = False
    browser_headless: bool = True
    local_allowed_hosts: list[str] = []
    assets_dir: Path = PROJECT_ROOT / "data" / "reference-images"
    artifacts_dir: Path = PROJECT_ROOT / "data" / "artifacts"
    artifact_retention_hours: int = Field(default=24, ge=1, le=168)

    @field_validator("power_automate_callback_secret")
    @classmethod
    def callback_key_length(cls, value: SecretStr):
        if value.get_secret_value() and len(value.get_secret_value()) < 32:
            raise ValueError("O segredo de callback deve ter pelo menos 32 caracteres.")
        return value

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / "backend" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )


settings = Settings()
