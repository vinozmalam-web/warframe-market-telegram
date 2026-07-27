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


def test_extract_riven_items_and_attributes_v2():
    from market_message.warframe import extract_riven_items, extract_riven_attributes

    v2_weapons_payload = {
        "apiVersion": "0.25.0",
        "data": [
            {
                "id": "123",
                "slug": "kulstar",
                "group": "secondary",
                "rivenType": "pistol",
                "i18n": {"ru": {"name": "Кулстар"}, "en": {"name": "Kulstar"}},
            }
        ],
    }

    weapons = extract_riven_items(v2_weapons_payload)
    assert len(weapons) == 1
    assert weapons[0].url_name == "kulstar"
    assert weapons[0].item_name == "Кулстар"
    assert weapons[0].ru_name == "Кулстар"
    assert weapons[0].group == "secondary"
    assert weapons[0].riven_type == "pistol"

    v2_attrs_payload = {
        "apiVersion": "0.25.0",
        "data": [
            {
                "id": "456",
                "slug": "punch_through",
                "group": "default",
                "i18n": {"ru": {"name": "Пронзание Навылет"}, "en": {"name": "Punch Through"}},
            }
        ],
    }

    attrs = extract_riven_attributes(v2_attrs_payload)
    assert len(attrs) == 1
    assert attrs[0].url_name == "punch_through"
    assert attrs[0].effect == "Пронзание Навылет"


def test_get_riven_meta_fallback(monkeypatch):
    config = Config(
        warframe_email="seller@example.com",
        warframe_password="secret",
        telegram_bot_token="123:token",
        telegram_chat_id="987654",
    )
    client = WarframeMarketClient(config, device_id="device-id")

    # Force HTTP request to fail so it uses static fallback
    monkeypatch.setattr(client, "_request", lambda method, path, **kwargs: Exception("Network error"))

    weapons = client.get_riven_items()
    assert len(weapons) > 0
    rubico = next(w for w in weapons if w.url_name == "rubico")
    assert rubico.ru_name == "Рубико"

    attrs = client.get_riven_attributes()
    assert len(attrs) == 32
    assert any(a.url_name == "critical_chance" for a in attrs)


def test_warframe_client_rate_limiting(monkeypatch):
    import time
    config = Config(
        warframe_email="seller@example.com",
        warframe_password="secret",
        telegram_bot_token="123:token",
        telegram_chat_id="987654",
        warframe_max_requests_per_second=10.0,
    )
    client = WarframeMarketClient(config, device_id="device-id")

    class DummyResponse:
        status_code = 200
        def json(self):
            return {"payload": {}}

    monkeypatch.setattr(client._client, "request", lambda method, url, **kwargs: DummyResponse())

    start_time = time.monotonic()
    for _ in range(4):
        client.list_chats()
    elapsed = time.monotonic() - start_time

    assert elapsed >= 0.25
    client.close()


def test_warframe_client_429_retry(monkeypatch):
    config = Config(
        warframe_email="seller@example.com",
        warframe_password="secret",
        telegram_bot_token="123:token",
        telegram_chat_id="987654",
        warframe_max_requests_per_second=1000.0,
    )
    client = WarframeMarketClient(config, device_id="device-id")

    attempts = 0

    class RateLimitedResponse:
        status_code = 429
        headers = {"Retry-After": "0.01"}

    class SuccessResponse:
        status_code = 200
        headers = {}
        def json(self):
            return {"payload": {"chats": []}}

    def fake_request(method, url, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return RateLimitedResponse()
        return SuccessResponse()

    monkeypatch.setattr(client._client, "request", fake_request)

    res = client.list_chats()
    assert res == {"payload": {"chats": []}}
    assert attempts == 3
    client.close()


def test_warframe_client_rpm_rate_limiting(monkeypatch):
    import time
    fake_time = 1000.0
    slept = []

    def fake_monotonic():
        nonlocal fake_time
        return fake_time

    def fake_sleep(secs):
        nonlocal fake_time
        slept.append(secs)
        fake_time += secs

    monkeypatch.setattr(time, "monotonic", fake_monotonic)
    monkeypatch.setattr(time, "sleep", fake_sleep)

    config = Config(
        warframe_email="seller@example.com",
        warframe_password="secret",
        telegram_bot_token="123:token",
        telegram_chat_id="987654",
        warframe_max_requests_per_second=1000.0,
        warframe_max_requests_per_minute=2.0,
    )
    client = WarframeMarketClient(config, device_id="device-id")

    class DummyResponse:
        status_code = 200
        def json(self):
            return {"payload": {}}

    monkeypatch.setattr(client._client, "request", lambda method, url, **kwargs: DummyResponse())

    # Send 3 requests when RPM limit is 2 per minute
    for _ in range(3):
        client.list_chats()

    client.close()
    assert any(s > 50.0 for s in slept)  # Should sleep ~60 seconds to satisfy 2 RPM limit


