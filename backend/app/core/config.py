from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RETUNORI API"
    database_url: str = "sqlite:///./retunori.db"
    jwt_secret: str = "development-only-change-me-please-use-a-long-random-secret"
    jwt_expire_minutes: int = 1440
    frontend_origin: str = "http://localhost:5173"
    daraja_base_url: str = "https://sandbox.safaricom.co.ke"
    daraja_consumer_key: str = ""
    daraja_consumer_secret: str = ""
    daraja_passkey: str = ""
    daraja_shortcode: str = ""
    daraja_callback_url: str = ""
    daraja_callback_secret: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
