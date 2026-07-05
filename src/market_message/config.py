from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    warframe_email: str
    warframe_password: str
    telegram_bot_token: str
    telegram_chat_id: str
    poll_interval_seconds: int = 30
    state_path: Path = Path("data/state.sqlite")
    platform: str = "pc"
    language: str = "en"
    crossplay: bool = True
    market_base_url: str = "https://warframe.market"
    api_base_url: str = "https://api.warframe.market/v1"
    telegram_api_base_url: str = "https://api.telegram.org"
    request_timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        values = env or os.environ
        missing: list[str] = []

        warframe_email = _get(values, "WARFRAME_MARKET_EMAIL") or _get(
            values, "WARFRAME_MARKET_LOGIN"
        )
        if not warframe_email:
            missing.append("WARFRAME_MARKET_EMAIL or WARFRAME_MARKET_LOGIN")

        warframe_password = _get(values, "WARFRAME_MARKET_PASSWORD")
        if not warframe_password:
            missing.append("WARFRAME_MARKET_PASSWORD")

        telegram_bot_token = _get(values, "TELEGRAM_BOT_TOKEN")
        if not telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")

        telegram_chat_id = _get(values, "TELEGRAM_CHAT_ID")
        if not telegram_chat_id:
            missing.append("TELEGRAM_CHAT_ID")

        if missing:
            raise ConfigError("Missing required environment variables: " + ", ".join(missing))

        poll_interval_seconds = _int_env(values, "POLL_INTERVAL_SECONDS", 30)
        if poll_interval_seconds < 5:
            raise ConfigError("POLL_INTERVAL_SECONDS must be at least 5")

        request_timeout_seconds = _float_env(values, "REQUEST_TIMEOUT_SECONDS", 20.0)
        if request_timeout_seconds <= 0:
            raise ConfigError("REQUEST_TIMEOUT_SECONDS must be greater than 0")

        return cls(
            warframe_email=warframe_email or "",
            warframe_password=warframe_password or "",
            telegram_bot_token=telegram_bot_token or "",
            telegram_chat_id=telegram_chat_id or "",
            poll_interval_seconds=poll_interval_seconds,
            state_path=Path(_get(values, "STATE_PATH") or "data/state.sqlite"),
            platform=_get(values, "WARFRAME_MARKET_PLATFORM") or "pc",
            language=_get(values, "WARFRAME_MARKET_LANGUAGE") or "en",
            crossplay=_bool_env(values, "WARFRAME_MARKET_CROSSPLAY", True),
            market_base_url=(_get(values, "WARFRAME_MARKET_BASE_URL") or "https://warframe.market").rstrip("/"),
            api_base_url=(_get(values, "WARFRAME_MARKET_API_BASE_URL") or "https://api.warframe.market/v1").rstrip("/"),
            telegram_api_base_url=(_get(values, "TELEGRAM_API_BASE_URL") or "https://api.telegram.org").rstrip("/"),
            request_timeout_seconds=request_timeout_seconds,
        )


def _get(values: Mapping[str, str], key: str) -> str | None:
    value = values.get(key)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _int_env(values: Mapping[str, str], key: str, default: int) -> int:
    raw = _get(values, key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be an integer") from exc


def _float_env(values: Mapping[str, str], key: str, default: float) -> float:
    raw = _get(values, key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be a number") from exc


def _bool_env(values: Mapping[str, str], key: str, default: bool) -> bool:
    raw = _get(values, key)
    if raw is None:
        return default
    normalized = raw.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{key} must be a boolean")
