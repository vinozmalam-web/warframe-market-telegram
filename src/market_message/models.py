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
