from market_message.forwarder import MessageForwarder
from market_message.state import StateStore


class FakeWarframeMarketClient:
    current_user_id = "me"

    def __init__(self):
        self.chat_payload = {
            "payload": {
                "chats": [
                    {"id": "chat-1", "unread_count": 2},
                    {"id": "chat-2", "unread_count": 0},
                ]
            }
        }
        self.messages_payload = {
            "payload": {
                "messages": [
                    {
                        "id": "outgoing",
                        "chat_id": "chat-1",
                        "message_from": "me",
                        "raw_message": "my reply",
                        "send_date": "2026-07-05T11:59:00Z",
                    },
                    {
                        "id": "incoming-1",
                        "chat_id": "chat-1",
                        "message_from": "buyer",
                        "raw_message": "first",
                        "send_date": "2026-07-05T12:00:00Z",
                    },
                    {
                        "id": "incoming-2",
                        "chat_id": "chat-1",
                        "message_from": "buyer",
                        "raw_message": "second",
                        "send_date": "2026-07-05T12:01:00Z",
                    },
                ],
                "users": {"buyer": {"ingame_name": "Buyer"}},
            }
        }

    def list_chats(self):
        return self.chat_payload

    def get_chat(self, chat_id):
        assert chat_id == "chat-1"
        return self.messages_payload


class FakeTelegramClient:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, text):
        self.sent_messages.append(text)


class FailingTelegramClient:
    def send_message(self, text):
        raise RuntimeError("telegram is down")


def test_forwarder_sends_only_unread_incoming_messages_once(tmp_path):
    state = StateStore(tmp_path / "state.sqlite")
    telegram = FakeTelegramClient()
    forwarder = MessageForwarder(
        warframe=FakeWarframeMarketClient(),
        telegram=telegram,
        state=state,
        market_base_url="https://warframe.market",
    )

    sent_count = forwarder.poll_once()
    second_sent_count = forwarder.poll_once()

    assert sent_count == 2
    assert second_sent_count == 0
    assert len(telegram.sent_messages) == 2
    assert "first" in telegram.sent_messages[0]
    assert "second" in telegram.sent_messages[1]
    assert "my reply" not in "\n".join(telegram.sent_messages)


def test_forwarder_does_not_mark_message_sent_when_telegram_fails(tmp_path):
    state = StateStore(tmp_path / "state.sqlite")
    forwarder = MessageForwarder(
        warframe=FakeWarframeMarketClient(),
        telegram=FailingTelegramClient(),
        state=state,
        market_base_url="https://warframe.market",
    )

    try:
        forwarder.poll_once()
    except RuntimeError:
        pass

    assert not state.was_message_sent("incoming-1")
    assert not state.was_message_sent("incoming-2")
