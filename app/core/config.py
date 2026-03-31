from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import (
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_PAYMENT_WEBHOOK_PATH,
    DEFAULT_SQLITE_PATH,
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
    sqlite_path: Path = Field(default=Path(DEFAULT_SQLITE_PATH), alias="SQLITE_PATH")
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
    api_host: str = Field(default=DEFAULT_API_HOST, alias="API_HOST")
    api_port: int = Field(default=DEFAULT_API_PORT, alias="API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @model_validator(mode="after")
    def validate_runtime_mode(self) -> "Settings":
        if self.database_url is None:
            sqlite_path = self.sqlite_path
            if not sqlite_path.is_absolute():
                sqlite_path = Path.cwd() / sqlite_path
            self.database_url = f"sqlite+aiosqlite:///{sqlite_path}"

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
