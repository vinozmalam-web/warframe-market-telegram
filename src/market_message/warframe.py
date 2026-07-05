from __future__ import annotations

import logging
from html.parser import HTMLParser
from typing import Any

from .config import Config
from .models import ChatSummary, IncomingMessage

logger = logging.getLogger(__name__)


class WarframeMarketError(RuntimeError):
    """Base error for Warframe Market API failures."""


class AuthenticationError(WarframeMarketError):
    """Raised when the stored Warframe Market session is invalid."""


class WarframeMarketClient:
    def __init__(self, config: Config, device_id: str):
        self.config = config
        self.device_id = device_id
        self.current_user_id: str | None = None
        self._csrf_token: str | None = None
        import httpx

        self._client = httpx.Client(
            follow_redirects=True,
            timeout=config.request_timeout_seconds,
            headers={"User-Agent": "market-message/0.1"},
        )

    def close(self) -> None:
        self._client.close()

    def login(self) -> None:
        self._csrf_token = self._fetch_csrf_token()
        payload = {
            "email": self.config.warframe_email,
            "password": self.config.warframe_password,
            "device_id": self.device_id,
        }
        data = self._request("POST", "/auth/signin", json=payload, csrf=True)
        user = _unwrap_payload(data).get("user", {})
        user_id = user.get("id")
        if not user_id:
            raise WarframeMarketError("Warframe Market sign-in response did not include user id")
        self.current_user_id = str(user_id)
        logger.info("Logged in to Warframe Market as user id %s", self.current_user_id)

    def list_chats(self) -> dict[str, Any]:
        return self._request("GET", "/im/chats")

    def get_chat(self, chat_id: str) -> dict[str, Any]:
        return self._request("GET", f"/im/chats/{chat_id}")

    def _fetch_csrf_token(self) -> str:
        response = self._client.get(self.config.market_base_url)
        response.raise_for_status()
        parser = _CsrfParser()
        parser.feed(response.text)
        if not parser.csrf_token:
            raise WarframeMarketError("Unable to find CSRF token on Warframe Market page")
        return parser.csrf_token

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        csrf = bool(kwargs.pop("csrf", False))
        headers = {
            "Accept": "application/json",
            "Platform": self.config.platform,
            "Language": self.config.language,
            "platform": self.config.platform,
            "language": self.config.language,
            "crossplay": str(self.config.crossplay).lower(),
        }
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            headers["Content-Type"] = "application/json"
        if csrf and self._csrf_token:
            headers["X-CSRFToken"] = self._csrf_token

        url = f"{self.config.api_base_url}{path}"
        response = self._client.request(method, url, headers=headers, **kwargs)
        if response.status_code in {401, 403}:
            raise AuthenticationError(f"Warframe Market returned {response.status_code}")
        if response.status_code >= 400:
            raise WarframeMarketError(
                f"Warframe Market returned {response.status_code}: {response.text[:500]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise WarframeMarketError("Warframe Market returned non-JSON response") from exc
        if not isinstance(data, dict):
            raise WarframeMarketError("Warframe Market returned unexpected JSON shape")
        return data


def extract_chats(data: dict[str, Any]) -> list[ChatSummary]:
    payload = _unwrap_payload(data)
    raw_chats = _extract_collection(payload, "chats")
    chats: list[ChatSummary] = []
    for raw_chat in raw_chats:
        if not isinstance(raw_chat, dict):
            continue
        chat_id = raw_chat.get("id") or raw_chat.get("chat_id") or raw_chat.get("_id")
        if not chat_id:
            continue
        unread = raw_chat.get("unread_count", raw_chat.get("unread_messages", 0))
        chats.append(ChatSummary(id=str(chat_id), unread_count=_safe_int(unread)))
    return chats


def extract_messages(data: dict[str, Any], chat_id: str) -> list[IncomingMessage]:
    payload = _unwrap_payload(data)
    raw_messages = _extract_collection(payload, "messages")
    users = _extract_users(payload)
    messages: list[IncomingMessage] = []

    for raw_message in raw_messages:
        if not isinstance(raw_message, dict):
            continue
        message_id = raw_message.get("id") or raw_message.get("_id") or raw_message.get("temp_id")
        sender_id = (
            raw_message.get("message_from")
            or raw_message.get("from")
            or raw_message.get("sender_id")
            or raw_message.get("user_id")
        )
        if not message_id or not sender_id:
            continue
        message_chat_id = raw_message.get("chat_id") or chat_id
        text = raw_message.get("raw_message")
        if text is None:
            text = raw_message.get("message", raw_message.get("text", ""))
        sender_name = _sender_name(raw_message, users, str(sender_id))
        messages.append(
            IncomingMessage(
                id=str(message_id),
                chat_id=str(message_chat_id),
                sender_id=str(sender_id),
                sender_name=sender_name,
                text=str(text),
                sent_at=_optional_str(
                    raw_message.get("send_date")
                    or raw_message.get("created_at")
                    or raw_message.get("created")
                ),
            )
        )

    return messages


def _unwrap_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = data.get("payload", data)
    return payload if isinstance(payload, dict) else {}


def _extract_collection(payload: dict[str, Any], name: str) -> list[Any]:
    direct = payload.get(name)
    if isinstance(direct, list):
        return direct
    if isinstance(direct, dict):
        return list(direct.values())

    entities = payload.get("entities")
    if isinstance(entities, dict):
        entity_collection = entities.get(name)
        if isinstance(entity_collection, dict):
            result = payload.get("result")
            if isinstance(result, list):
                return [
                    entity_collection[item_id]
                    for item_id in result
                    if item_id in entity_collection
                ]
            return list(entity_collection.values())

    return []


def _extract_users(payload: dict[str, Any]) -> dict[str, Any]:
    users = payload.get("users")
    if isinstance(users, dict):
        return users
    entities = payload.get("entities")
    if isinstance(entities, dict) and isinstance(entities.get("users"), dict):
        return entities["users"]
    return {}


def _sender_name(raw_message: dict[str, Any], users: dict[str, Any], sender_id: str) -> str:
    sender = raw_message.get("sender")
    if isinstance(sender, dict):
        name = sender.get("ingame_name") or sender.get("ingameName") or sender.get("slug")
        if name:
            return str(name)
    user = users.get(sender_id)
    if isinstance(user, dict):
        name = user.get("ingame_name") or user.get("ingameName") or user.get("slug")
        if name:
            return str(name)
    return sender_id


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


class _CsrfParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.csrf_token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attr_map = {key: value for key, value in attrs}
        if attr_map.get("name") == "csrf-token" and attr_map.get("content"):
            self.csrf_token = attr_map["content"]
