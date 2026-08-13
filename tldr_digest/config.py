"""Zentrale Konfiguration. Secrets kommen aus der Umgebung (.env lokal, GH-Secrets in CI)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Immer nötig (auch im Dry-Run, weil das LLM läuft).
    anthropic_api_key: str

    # Nur für den echten Mailversand nötig -> Default leer, damit der Dry-Run ohne
    # SMTP-Creds läuft. main.py prüft vor dem Versand, dass sie gesetzt sind.
    smtp_user: str = ""
    smtp_app_password: str = ""
    mail_to: str = "lucasbeck1095@gmail.com"

    # Verhalten (Defaults, per env überschreibbar)
    model: str = "claude-sonnet-5"
    fetch_budget: int = 12           # max. tiefe Artikel-Fetches pro Lauf
    article_char_cap: int = 10_000   # Truncation je geholtem Artikel

    # SMTP-Server (Gmail)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587             # STARTTLS

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
