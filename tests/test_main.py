import logging
from types import SimpleNamespace

import market_message.__main__ as app


class FakeTelegramClient:
    instances = []

    def __init__(self, config):
        self.config = config
        self.sent_messages = []
        self.closed = False
        self.__class__.instances.append(self)

    def send_message(self, text):
        self.sent_messages.append(text)

    def close(self):
        self.closed = True


class FailingTelegramClient:
    instances = []

    def __init__(self, config):
        self.config = config
        self.closed = False
        self.__class__.instances.append(self)

    def send_message(self, text):
        raise RuntimeError("telegram is down")

    def close(self):
        self.closed = True


class FakeStateStore:
    def __init__(self, path):
        self.path = path

    def get_or_create_device_id(self):
        return "device-id"


class FakeWarframeMarketClient:
    def __init__(self, config, device_id):
        self.config = config
        self.device_id = device_id
        self.closed = False

    def login(self):
        pass

    def close(self):
        self.closed = True


class StoppingForwarder:
    instances = []

    def __init__(self, warframe, telegram, state, market_base_url):
        self.warframe = warframe
        self.telegram = telegram
        self.state = state
        self.market_base_url = market_base_url
        self.forward_replies_calls = 0
        self.__class__.instances.append(self)

    def forward_replies(self):
        self.forward_replies_calls += 1
        return 1

    def poll_once(self):
        raise KeyboardInterrupt


def configure_main(monkeypatch, tmp_path, telegram_cls):
    config = SimpleNamespace(
        state_path=tmp_path / "state.sqlite",
        poll_interval_seconds=30,
        market_base_url="https://warframe.market",
    )
    telegram_cls.instances = []
    monkeypatch.setattr(app.Config, "from_env", staticmethod(lambda: config))
    monkeypatch.setattr(app, "StateStore", FakeStateStore)
    monkeypatch.setattr(app, "WarframeMarketClient", FakeWarframeMarketClient)
    monkeypatch.setattr(app, "TelegramClient", telegram_cls)
    StoppingForwarder.instances = []
    monkeypatch.setattr(app, "MessageForwarder", StoppingForwarder)


def test_main_reports_bot_start_to_telegram(monkeypatch, tmp_path):
    configure_main(monkeypatch, tmp_path, FakeTelegramClient)

    result = app.main()

    assert result == 0
    assert FakeTelegramClient.instances[0].sent_messages == [
        "Warframe Market Telegram forwarder started\nPolling every 30 seconds"
    ]


def test_main_logs_and_continues_when_startup_notification_fails(
    monkeypatch,
    tmp_path,
    caplog,
):
    configure_main(monkeypatch, tmp_path, FailingTelegramClient)

    with caplog.at_level(logging.ERROR):
        result = app.main()

    assert result == 0
    assert "Telegram startup notification failed; continuing" in caplog.text


def test_main_processes_telegram_replies_before_polling_warframe(monkeypatch, tmp_path):
    configure_main(monkeypatch, tmp_path, FakeTelegramClient)

    result = app.main()

    assert result == 0
    assert StoppingForwarder.instances[0].forward_replies_calls == 1


def test_main_redacts_telegram_bot_token_from_http_logs(monkeypatch, tmp_path, caplog):
    configure_main(monkeypatch, tmp_path, FakeTelegramClient)

    with caplog.at_level(logging.INFO):
        result = app.main()
        logging.getLogger("httpx").info(
            'HTTP Request: POST https://api.telegram.org/bot123:secret/sendMessage '
            '"HTTP/1.1 401 Unauthorized"'
        )

    assert result == 0
    assert "bot123:secret" not in caplog.text
    assert "bot<redacted>/sendMessage" in caplog.text
