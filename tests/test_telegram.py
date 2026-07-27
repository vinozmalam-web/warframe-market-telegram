import httpx

from market_message.config import Config
from market_message.telegram import TelegramClient


def make_config():
    return Config(
        warframe_email="seller@example.com",
        warframe_password="secret",
        telegram_bot_token="123:token",
        telegram_chat_id="987654",
        telegram_api_base_url="https://telegram.example",
    )


def test_send_message_returns_telegram_message_id():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 9001}},
        )

    client = TelegramClient(make_config())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    message_id = client.send_message("hello")

    assert message_id == 9001
    assert requests[0].url == "https://telegram.example/bot123:token/sendMessage"


def test_get_updates_returns_message_replies_and_plain_messages():
    def handler(request):
        assert request.url == "https://telegram.example/bot123:token/getUpdates"
        assert request.read() == b'{"timeout":0,"offset":40}'
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": [
                    {
                        "update_id": 40,
                        "message": {
                            "message_id": 100,
                            "chat": {"id": 987654},
                            "text": "plain message",
                        },
                    },
                    {
                        "update_id": 41,
                        "message": {
                            "message_id": 101,
                            "chat": {"id": 987654},
                            "text": "reply text",
                            "reply_to_message": {"message_id": 9001},
                        },
                    },
                    {
                        "update_id": 42,
                        "message": {
                            "message_id": 102,
                            "chat": {"id": 111111},
                            "text": "wrong chat",
                            "reply_to_message": {"message_id": 9001},
                        },
                    },
                ],
            },
        )

    client = TelegramClient(make_config())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    updates = client.get_updates(offset=40)

    assert [update.update_id for update in updates] == [40, 41, 42]
    assert updates[0].message is not None
    assert updates[0].message.text == "plain message"
    assert updates[0].message.reply_to_message_id is None
    assert updates[1].message is not None
    assert updates[1].message.text == "reply text"
    assert updates[1].message.reply_to_message_id == 9001
    assert updates[2].message is None
