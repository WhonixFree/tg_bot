from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import (
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_PAYMENT_WEBHOOK_PATH,
)
from app.core.enums import PaymentProviderMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bot_token: SecretStr = Field(alias="BOT_TOKEN")
    admin_tg_id: int = Field(alias="ADMIN_TG_ID")
    private_channel_id: int = Field(alias="PRIVATE_CHANNEL_ID")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    db_host: str | None = Field(default=None, alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str | None = Field(default=None, alias="DB_NAME")
    db_user: str | None = Field(default=None, alias="DB_USER")
    db_password: SecretStr | None = Field(default=None, alias="DB_PASSWORD")
    app_base_url: str = Field(alias="APP_BASE_URL")
    free_channel_url: str = Field(alias="FREE_CHANNEL_URL")
    manager_contact_text: str = Field(alias="MANAGER_CONTACT_TEXT")
    project_description_text: str = Field(alias="PROJECT_DESCRIPTION_TEXT")
    main_menu_image_path: str = Field(alias="MAIN_MENU_IMAGE_PATH")
    payment_provider_mode: PaymentProviderMode = Field(
        default=PaymentProviderMode.MOCK,
        alias="PAYMENT_PROVIDER_MODE",
    )
    merchant_project_uuid: str | None = Field(default=None, alias="MERCHANT_PROJECT_UUID")
    merchant_api_key: SecretStr | None = Field(default=None, alias="MERCHANT_API_KEY")
    payment_webhook_path: str = Field(
        default=DEFAULT_PAYMENT_WEBHOOK_PATH,
        alias="PAYMENT_WEBHOOK_PATH",
    )
    rate_api_timeout_seconds: float = Field(default=5.0, alias="RATE_API_TIMEOUT_SECONDS")
    rate_cache_ttl_seconds: int = Field(default=30, alias="RATE_CACHE_TTL_SECONDS")
    coingecko_base_url: str = Field(
        default="https://api.coingecko.com/api/v3",
        alias="COINGECKO_BASE_URL",
    )
    binance_base_url: str = Field(
        default="https://api.binance.com",
        alias="BINANCE_BASE_URL",
    )
    api_host: str = Field(default=DEFAULT_API_HOST, alias="API_HOST")
    api_port: int = Field(default=DEFAULT_API_PORT, alias="API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @model_validator(mode="after")
    def validate_runtime_mode(self) -> "Settings":
        if self.database_url is None:
            missing_db_fields: list[str] = []
            if not self.db_host:
                missing_db_fields.append("DB_HOST")
            if not self.db_name:
                missing_db_fields.append("DB_NAME")
            if not self.db_user:
                missing_db_fields.append("DB_USER")
            if self.db_password is None or not self.db_password.get_secret_value():
                missing_db_fields.append("DB_PASSWORD")
            if missing_db_fields:
                fields = ", ".join(missing_db_fields)
                raise ValueError(
                    "Database configuration requires DATABASE_URL or configured values for "
                    f"{fields}."
                )
            self.database_url = (
                "postgresql+psycopg://"
                f"{self.db_user}:{self.db_password.get_secret_value()}@"
                f"{self.db_host}:{self.db_port}/{self.db_name}"
            )

        if self.payment_provider_mode is PaymentProviderMode.LIVE:
            missing_fields: list[str] = []
            if not self.merchant_project_uuid:
                missing_fields.append("MERCHANT_PROJECT_UUID")
            if self.merchant_api_key is None or not self.merchant_api_key.get_secret_value():
                missing_fields.append("MERCHANT_API_KEY")
            if missing_fields:
                fields = ", ".join(missing_fields)
                raise ValueError(
                    "PAYMENT_PROVIDER_MODE=live requires configured values for "
                    f"{fields}."
                )

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
