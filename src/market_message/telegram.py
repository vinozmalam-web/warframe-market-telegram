from __future__ import annotations

from typing import Any

import httpx

from .config import Config
from .models import TelegramIncomingMessage, TelegramUpdate


class TelegramError(RuntimeError):
    """Raised when Telegram rejects a notification."""


class TelegramClient:
    def __init__(self, config: Config):
        self.config = config
        self._client = httpx.Client(timeout=config.request_timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def send_message(self, text: str) -> int | None:
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
        data = self._parse_response(response)
        result = data.get("result")
        if isinstance(result, dict):
            message_id = result.get("message_id")
            if isinstance(message_id, int):
                return message_id
        return None

    def get_updates(self, offset: int | None = None) -> list[TelegramUpdate]:
        url = (
            f"{self.config.telegram_api_base_url}/bot"
            f"{self.config.telegram_bot_token}/getUpdates"
        )
        payload: dict[str, Any] = {"timeout": 0}
        if offset is not None:
            payload["offset"] = offset
        response = self._client.post(url, json=payload)
        data = self._parse_response(response)
        result = data.get("result")
        if not isinstance(result, list):
            raise TelegramError(f"Telegram returned unexpected updates payload: {data}")

        updates: list[TelegramUpdate] = []
        for raw_update in result:
            update = self._parse_update(raw_update)
            if update is not None:
                updates.append(update)
        return updates

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise TelegramError(f"Telegram returned {response.status_code}: {response.text[:500]}")
        try:
            data = response.json()
        except ValueError as exc:
            raise TelegramError("Telegram returned non-JSON response") from exc
        if not data.get("ok"):
            raise TelegramError(f"Telegram rejected request: {data}")
        return data

    def _parse_update(self, raw_update: Any) -> TelegramUpdate | None:
        if not isinstance(raw_update, dict):
            return None
        update_id = raw_update.get("update_id")
        if not isinstance(update_id, int):
            return None

        raw_message = raw_update.get("message")
        if not isinstance(raw_message, dict):
            return TelegramUpdate(update_id=update_id, message=None)

        raw_chat = raw_message.get("chat")
        chat_id = raw_chat.get("id") if isinstance(raw_chat, dict) else None
        if chat_id is None or str(chat_id) != str(self.config.telegram_chat_id):
            return TelegramUpdate(update_id=update_id, message=None)

        message_id = raw_message.get("message_id")
        if not isinstance(message_id, int):
            return TelegramUpdate(update_id=update_id, message=None)

        text = raw_message.get("text")
        if not isinstance(text, str):
            text = None

        reply_to_message_id = None
        raw_reply = raw_message.get("reply_to_message")
        if isinstance(raw_reply, dict) and isinstance(raw_reply.get("message_id"), int):
            reply_to_message_id = raw_reply["message_id"]

        return TelegramUpdate(
            update_id=update_id,
            message=TelegramIncomingMessage(
                message_id=message_id,
                chat_id=str(chat_id),
                text=text,
                reply_to_message_id=reply_to_message_id,
            ),
        )
