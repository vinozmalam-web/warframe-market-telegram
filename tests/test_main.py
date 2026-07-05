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
    def __init__(self, warframe, telegram, state, market_base_url):
        self.warframe = warframe
        self.telegram = telegram
        self.state = state
        self.market_base_url = market_base_url

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
