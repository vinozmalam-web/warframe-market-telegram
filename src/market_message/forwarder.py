from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from typing import Protocol

from .models import IncomingMessage
from .state import StateStore
from .warframe import extract_chats, extract_messages

TELEGRAM_MAX_MESSAGE_LENGTH = 4096


class WarframeLike(Protocol):
    current_user_id: str | None

    def list_chats(self) -> dict:
        ...

    def get_chat(self, chat_id: str) -> dict:
        ...


class TelegramLike(Protocol):
    def send_message(self, text: str) -> None:
        ...


class MessageForwarder:
    def __init__(
        self,
        warframe: WarframeLike,
        telegram: TelegramLike,
        state: StateStore,
        market_base_url: str,
    ):
        self.warframe = warframe
        self.telegram = telegram
        self.state = state
        self.market_base_url = market_base_url.rstrip("/")

    def poll_once(self) -> int:
        current_user_id = self.warframe.current_user_id
        if not current_user_id:
            raise RuntimeError("Warframe Market client is not logged in")

        sent_count = 0
        chats = extract_chats(self.warframe.list_chats())
        for chat in chats:
            if chat.unread_count <= 0:
                continue

            messages = extract_messages(self.warframe.get_chat(chat.id), chat_id=chat.id)
            incoming = [
                message
                for message in messages
                if message.sender_id != current_user_id
            ]
            incoming.sort(key=lambda message: (message.sent_at or "", message.id))
            candidates = incoming[-chat.unread_count :]

            for message in candidates:
                if self.state.was_message_sent(message.id):
                    continue
                self.telegram.send_message(format_telegram_message(message, self.market_base_url))
                self.state.mark_message_sent(message.id, message.chat_id)
                sent_count += 1

        return sent_count


def format_telegram_message(message: IncomingMessage, market_base_url: str) -> str:
    link = f"{market_base_url.rstrip('/')}/im/chats/{message.chat_id}"
    header = f"Warframe Market: new incoming message\nFrom: {message.sender_name}\n\n"
    suffix = f"\n\nOpen chat: {link}"
    body = clean_message_text(message.text) or "(empty message)"
    max_body_len = TELEGRAM_MAX_MESSAGE_LENGTH - len(header) - len(suffix)

    if max_body_len < 0:
        return (header + suffix)[-TELEGRAM_MAX_MESSAGE_LENGTH:]

    if len(body) > max_body_len:
        body = body[: max(0, max_body_len - 3)].rstrip() + "..."

    return header + body + suffix


def clean_message_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    text = unescape(parser.text)
    text = text.replace("\xa0", " ")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div"} and self.parts:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
