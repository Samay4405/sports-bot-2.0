"""Centralized application configuration via environment variables.

All secrets and tunables are loaded from a `.env` file using Pydantic Settings.
Never hardcode credentials — always use this module to access them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://sportsbot:sportsbot@localhost:5432/sportsbot"

    # ── Encryption ────────────────────────────────────────────────────────
    # 32-byte hex string (64 hex chars) for AES-256-GCM
    encryption_key: str = ""

    # ── Google Gemini ─────────────────────────────────────────────────────
    google_api_key: str = ""
    llm_model: str = "gemini-2.0-flash"

    # ── Telegram ──────────────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── Booking ───────────────────────────────────────────────────────────
    # Seconds around the target time to fire retry attempts
    booking_retry_offsets: list[int] = [0, 5, 15]

    # ── Paths ─────────────────────────────────────────────────────────────
    screenshot_dir: Path = Path("./screenshots")

    # ── Validators ────────────────────────────────────────────────────────

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """Ensure the encryption key is a valid 32-byte hex string."""
        if v and len(v) != 64:
            raise ValueError(
                f"ENCRYPTION_KEY must be exactly 64 hex characters (32 bytes), got {len(v)}"
            )
        if v:
            try:
                bytes.fromhex(v)
            except ValueError:
                raise ValueError("ENCRYPTION_KEY must be a valid hex string")
        return v

    @field_validator("booking_retry_offsets", mode="before")
    @classmethod
    def parse_retry_offsets(cls, v: Any) -> list[int]:
        """Parse retry offsets from JSON string or list."""
        if isinstance(v, str):
            return json.loads(v)
        return v

    @property
    def encryption_key_bytes(self) -> bytes:
        """Return the encryption key as raw bytes."""
        if not self.encryption_key:
            raise ValueError("ENCRYPTION_KEY is not configured")
        return bytes.fromhex(self.encryption_key)


# Singleton — import this from anywhere
settings = Settings()
