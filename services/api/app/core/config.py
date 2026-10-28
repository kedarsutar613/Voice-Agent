from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./voice.db"
    jwt_secret: str
    admin_email: str = "admin@example.com"
    admin_password: str
    cors_origins: str = "http://localhost:5173"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    public_base_url: str = ""
    outbound_enabled: bool = False
    outbound_allowlist: str = ""
    daily_call_limit: int = 10
    max_call_seconds: int = 300
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
if (
    len(settings.jwt_secret) < 32
    or len(settings.admin_password) < 12
    or settings.jwt_secret.startswith("replace-with-")
    or settings.admin_password.startswith("replace-with-")
):
    raise RuntimeError(
        "JWT_SECRET must have 32 characters and ADMIN_PASSWORD at least 12"
    )
