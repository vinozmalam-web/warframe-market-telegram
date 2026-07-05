from __future__ import annotations

from typing import Any

import httpx

from .config import Config


class TelegramError(RuntimeError):
    """Raised when Telegram rejects a notification."""


class TelegramClient:
    def __init__(self, config: Config):
        self.config = config
        self._client = httpx.Client(timeout=config.request_timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def send_message(self, text: str) -> None:
        url = (
            f"{self.config.telegram_api_base_url}/bot"
            f"{self.config.telegram_bot_token}/sendMessage"
        )
        payload: dict[str, Any] = {
            "chat_id": self.config.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        response = self._client.post(url, json=payload)
        if response.status_code >= 400:
            raise TelegramError(f"Telegram returned {response.status_code}: {response.text[:500]}")
        try:
            data = response.json()
        except ValueError as exc:
            raise TelegramError("Telegram returned non-JSON response") from exc
        if not data.get("ok"):
            raise TelegramError(f"Telegram rejected message: {data}")
