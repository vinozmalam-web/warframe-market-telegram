import os

import pytest

from market_message.config import Config, ConfigError


def clear_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith(("WARFRAME_MARKET_", "TELEGRAM_", "POLL_", "STATE_")):
            monkeypatch.delenv(key, raising=False)


def test_config_reads_required_values_and_defaults(monkeypatch):
    clear_env(monkeypatch)
    monkeypatch.setenv("WARFRAME_MARKET_EMAIL", "seller@example.com")
    monkeypatch.setenv("WARFRAME_MARKET_PASSWORD", "secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "987654")

    config = Config.from_env()

    assert config.warframe_email == "seller@example.com"
    assert config.warframe_password == "secret"
    assert config.telegram_bot_token == "123:token"
    assert config.telegram_chat_id == "987654"
    assert config.poll_interval_seconds == 30
    assert config.platform == "pc"
    assert config.language == "en"
    assert str(config.state_path).endswith("data/state.sqlite")


def test_config_accepts_login_alias(monkeypatch):
    clear_env(monkeypatch)
    monkeypatch.setenv("WARFRAME_MARKET_LOGIN", "seller@example.com")
    monkeypatch.setenv("WARFRAME_MARKET_PASSWORD", "secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "987654")

    config = Config.from_env()

    assert config.warframe_email == "seller@example.com"


def test_config_rejects_missing_required_values(monkeypatch):
    clear_env(monkeypatch)
    monkeypatch.setenv("WARFRAME_MARKET_PASSWORD", "secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:token")

    with pytest.raises(ConfigError) as exc:
        Config.from_env()

    message = str(exc.value)
    assert "WARFRAME_MARKET_EMAIL" in message
    assert "TELEGRAM_CHAT_ID" in message


def test_config_rejects_too_small_poll_interval(monkeypatch):
    clear_env(monkeypatch)
    monkeypatch.setenv("WARFRAME_MARKET_EMAIL", "seller@example.com")
    monkeypatch.setenv("WARFRAME_MARKET_PASSWORD", "secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "987654")
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "2")

    with pytest.raises(ConfigError) as exc:
        Config.from_env()

    assert "POLL_INTERVAL_SECONDS" in str(exc.value)
