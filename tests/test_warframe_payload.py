import json
import sys

from market_message.config import Config
from market_message.warframe import WarframeMarketClient
from market_message.warframe import extract_chats, extract_messages


def test_extract_chats_accepts_payload_wrapper():
    payload = {
        "payload": {
            "chats": [
                {"id": "chat-1", "unread_count": 2},
                {"chat_id": "chat-2", "unread_messages": 0},
            ]
        }
    }

    chats = extract_chats(payload)

    assert [chat.id for chat in chats] == ["chat-1", "chat-2"]
    assert [chat.unread_count for chat in chats] == [2, 0]


def test_extract_messages_uses_raw_message_when_available_and_sender_names():
    payload = {
        "payload": {
            "messages": [
                {
                    "id": "message-1",
                    "chat_id": "chat-1",
                    "message_from": "user-2",
                    "message": "<p>rendered</p>",
                    "raw_message": "plain",
                    "send_date": "2026-07-05T12:00:00Z",
                }
            ],
            "users": {
                "user-2": {
                    "ingame_name": "Buyer",
                    "slug": "buyer",
                }
            },
        }
    }

    messages = extract_messages(payload, chat_id="chat-1")

    assert len(messages) == 1
    assert messages[0].id == "message-1"
    assert messages[0].chat_id == "chat-1"
    assert messages[0].sender_id == "user-2"
    assert messages[0].sender_name == "Buyer"
    assert messages[0].text == "plain"


def test_send_chat_message_uses_warframe_websocket(monkeypatch):
    calls = {}

    class FakeSocket:
        def send(self, payload):
            calls["payload"] = json.loads(payload)

        def close(self):
            calls["closed"] = True

    class FakeWebsocketModule:
        def create_connection(self, url, timeout, header, subprotocols):
            calls["url"] = url
            calls["timeout"] = timeout
            calls["header"] = header
            calls["subprotocols"] = subprotocols
            return FakeSocket()

    monkeypatch.setitem(sys.modules, "websocket", FakeWebsocketModule())
    config = Config(
        warframe_email="seller@example.com",
        warframe_password="secret",
        telegram_bot_token="123:token",
        telegram_chat_id="987654",
        market_base_url="https://warframe.market",
        platform="pc",
        request_timeout_seconds=7.0,
    )
    client = WarframeMarketClient(config, device_id="device-id")
    client._client.cookies.set("sessionid", "abc123", domain=".warframe.market")

    client.send_chat_message("chat-1", "reply text")
    client.close()

    assert calls["url"] == "wss://ws.warframe.market/socket?platform=pc"
    assert calls["timeout"] == 7.0
    assert calls["subprotocols"] == ["wfm"]
    assert "Origin: https://warframe.market" in calls["header"]
    assert "Cookie: sessionid=abc123" in calls["header"]
    assert calls["payload"]["type"] == "@WS/chats/SEND_MESSAGE"
    assert calls["payload"]["payload"]["chat_id"] == "chat-1"
    assert calls["payload"]["payload"]["message"] == "reply text"
    assert len(calls["payload"]["payload"]["temp_id"]) == 24
    assert calls["closed"] is True
