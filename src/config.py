"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# =============================================================================
# Find .env file
# =============================================================================

def find_env_file() -> str:
    """Find the .env file relative to project root."""
    # Try different locations
    candidates = [
        "config/.env",
        ".env",
        Path(__file__).parent.parent / "config" / ".env",
    ]
    
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return str(path)
    
    return "config/.env"  # Default


ENV_FILE = find_env_file()


# =============================================================================
# Settings Classes
# =============================================================================


class SednaSettings(BaseSettings):
    """Sedna Agency API settings."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="SEDNA_",
        extra="ignore",
    )

    api_base_url: str = "http://test.kodsedna.com/SednaAgencyb2bApi/api"
    username: str = "7STAR"
    password: SecretStr = SecretStr("7STAR")
    timeout_seconds: int = 30
    max_retries: int = 3


class BookingEmailSettings(BaseSettings):
    """Booking email specific settings."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="BOOKING_EMAIL_",
        extra="ignore",
    )

    host: str = "imap.gmail.com"
    port: int = 993
    address: str = "booking@pointholiday.com"
    password: SecretStr = SecretStr("")
    use_ssl: bool = True


class StopSaleEmailSettings(BaseSettings):
    """Stop sale email specific settings."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="STOPSALE_EMAIL_",
        extra="ignore",
    )

    host: str = "imap.gmail.com"
    port: int = 993
    address: str = "stopsale@pointholiday.com"
    password: SecretStr = SecretStr("")
    use_ssl: bool = True


class AppSettings(BaseSettings):
    """Application-level settings."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    # Email polling
    email_check_interval_seconds: int = 60

    # Processing
    max_retry_attempts: int = 3
    retry_backoff_seconds: int = 5
    mark_processed_emails: bool = True
    delete_processed_pdfs: bool = False

    # Paths
    temp_dir: str = "/tmp/mindops-entegrasyon"

    @field_validator("email_check_interval_seconds")
    @classmethod
    def validate_interval(cls, v: int) -> int:
        if v < 10:
            raise ValueError("Email check interval must be at least 10 seconds")
        return v


class Settings(BaseSettings):
    """Main settings container with lazy loading."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Cache for sub-settings
    _sedna: SednaSettings | None = None
    _booking: BookingEmailSettings | None = None
    _stopsale: StopSaleEmailSettings | None = None
    _app: AppSettings | None = None

    @property
    def sedna(self) -> SednaSettings:
        if self._sedna is None:
            self._sedna = SednaSettings()
        return self._sedna

    @property
    def booking_email(self) -> BookingEmailSettings:
        if self._booking is None:
            self._booking = BookingEmailSettings()
        return self._booking

    @property
    def stopsale_email(self) -> StopSaleEmailSettings:
        if self._stopsale is None:
            self._stopsale = StopSaleEmailSettings()
        return self._stopsale

    @property
    def app(self) -> AppSettings:
        if self._app is None:
            self._app = AppSettings()
        return self._app

    # Convenience accessors
    @property
    def sedna_api_base_url(self) -> str:
        return self.sedna.api_base_url

    @property
    def sedna_username(self) -> str:
        return self.sedna.username

    @property
    def sedna_password(self) -> str:
        return self.sedna.password.get_secret_value()

    @property
    def booking_email_host(self) -> str:
        return self.booking_email.host

    @property
    def booking_email_port(self) -> int:
        return self.booking_email.port

    @property
    def booking_email_address(self) -> str:
        return self.booking_email.address

    @property
    def booking_email_password(self) -> str:
        return self.booking_email.password.get_secret_value()

    @property
    def stopsale_email_host(self) -> str:
        return self.stopsale_email.host

    @property
    def stopsale_email_port(self) -> int:
        return self.stopsale_email.port

    @property
    def stopsale_email_address(self) -> str:
        return self.stopsale_email.address

    @property
    def stopsale_email_password(self) -> str:
        return self.stopsale_email.password.get_secret_value()

    @property
    def email_check_interval_seconds(self) -> int:
        return self.app.email_check_interval_seconds


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
