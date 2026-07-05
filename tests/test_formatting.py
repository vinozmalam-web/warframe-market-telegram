from market_message.forwarder import format_telegram_message
from market_message.models import IncomingMessage


def test_format_telegram_message_strips_html_and_includes_chat_link():
    message = IncomingMessage(
        id="message-1",
        chat_id="chat-1",
        sender_id="user-2",
        sender_name="Buyer",
        text="<b>Hello</b>&nbsp;Tenno<br>Need item?",
        sent_at="2026-07-05T12:00:00Z",
    )

    text = format_telegram_message(message, "https://warframe.market")

    assert "Buyer" in text
    assert "Hello Tenno\nNeed item?" in text
    assert "https://warframe.market/im/chats/chat-1" in text
    assert "<b>" not in text
    assert "&nbsp;" not in text


def test_format_telegram_message_truncates_long_text():
    message = IncomingMessage(
        id="message-1",
        chat_id="chat-1",
        sender_id="user-2",
        sender_name="Buyer",
        text="x" * 5000,
        sent_at=None,
    )

    text = format_telegram_message(message, "https://warframe.market")

    assert len(text) <= 4096
    assert "..." in text
    assert text.endswith("https://warframe.market/im/chats/chat-1")
