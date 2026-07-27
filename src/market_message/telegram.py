from __future__ import annotations

from typing import Any

import httpx

from .config import Config
from .models import TelegramIncomingMessage, TelegramUpdate


import hashlib
import hmac
from urllib.parse import parse_qsl


class TelegramError(RuntimeError):
    """Raised when Telegram rejects a notification."""


def validate_init_data(init_data: str, bot_token: str) -> bool:
    if not init_data or not bot_token:
        return False
    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed_data.pop("hash", None)
        if not received_hash:
            return False

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed_data.items(), key=lambda item: item[0])
        )

        secret_key = hmac.new(
            b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
        ).digest()
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(calculated_hash.lower(), received_hash.lower())
    except Exception:
        return False


class TelegramClient:
    def __init__(self, config: Config):
        self.config = config
        self._client = httpx.Client(timeout=config.request_timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def send_message(
        self,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> int | None:
        url = (
            f"{self.config.telegram_api_base_url}/bot"
            f"{self.config.telegram_bot_token}/sendMessage"
        )
        payload: dict[str, Any] = {
            "chat_id": self.config.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup

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
