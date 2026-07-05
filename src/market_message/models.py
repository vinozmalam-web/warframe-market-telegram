from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatSummary:
    id: str
    unread_count: int


@dataclass(frozen=True)
class IncomingMessage:
    id: str
    chat_id: str
    sender_id: str
    sender_name: str
    text: str
    sent_at: str | None


@dataclass(frozen=True)
class TelegramIncomingMessage:
    message_id: int
    chat_id: str
    text: str | None
    reply_to_message_id: int | None


@dataclass(frozen=True)
class TelegramUpdate:
    update_id: int
    message: TelegramIncomingMessage | None
