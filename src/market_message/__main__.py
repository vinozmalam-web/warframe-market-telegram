from __future__ import annotations

import logging
import re
import sys
import time

from .config import Config, ConfigError
from .forwarder import MessageForwarder
from .state import StateStore
from .telegram import TelegramClient
from .warframe import AuthenticationError, WarframeMarketClient


_TELEGRAM_BOT_TOKEN_IN_URL = re.compile(r"(/bot)[0-9]+:[^/\s\"']+")


class _TelegramBotTokenRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = _redact_telegram_bot_tokens(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def _redact_telegram_bot_tokens(message: str) -> str:
    return _TELEGRAM_BOT_TOKEN_IN_URL.sub(r"\1<redacted>", message)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if not any(
            isinstance(existing_filter, _TelegramBotTokenRedactionFilter)
            for existing_filter in handler.filters
        ):
            handler.addFilter(_TelegramBotTokenRedactionFilter())


def main() -> int:
    _configure_logging()
    logger = logging.getLogger("market_message")

    try:
        config = Config.from_env()
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    state = StateStore(config.state_path)
    warframe = WarframeMarketClient(config, device_id=state.get_or_create_device_id())
    telegram = TelegramClient(config)
    forwarder = MessageForwarder(
        warframe=warframe,
        telegram=telegram,
        state=state,
        market_base_url=config.market_base_url,
    )

    try:
        _login_until_success(warframe, config.poll_interval_seconds, logger)
        _send_startup_notification(telegram, config.poll_interval_seconds, logger)
        logger.info("Polling every %s seconds", config.poll_interval_seconds)
        while True:
            try:
                reply_count = forwarder.forward_replies()
                if reply_count:
                    logger.info("Sent %s Telegram reply/replies to Warframe Market", reply_count)
                sent_count = forwarder.poll_once()
                if sent_count:
                    logger.info("Forwarded %s message(s) to Telegram", sent_count)
            except AuthenticationError:
                logger.warning("Warframe Market session expired; logging in again")
                _login_until_success(warframe, config.poll_interval_seconds, logger)
            except Exception:
                logger.exception("Polling cycle failed; will retry")
            time.sleep(config.poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Stopping")
        return 0
    finally:
        warframe.close()
        telegram.close()


def _send_startup_notification(
    telegram: TelegramClient,
    poll_interval_seconds: int,
    logger: logging.Logger,
) -> None:
    try:
        telegram.send_message(
            "Warframe Market Telegram forwarder started\n"
            f"Polling every {poll_interval_seconds} seconds"
        )
    except Exception:
        logger.exception("Telegram startup notification failed; continuing")


def _login_until_success(
    warframe: WarframeMarketClient,
    retry_delay_seconds: int,
    logger: logging.Logger,
) -> None:
    while True:
        try:
            warframe.login()
            return
        except Exception:
            logger.exception(
                "Warframe Market login failed; retrying in %s seconds",
                retry_delay_seconds,
            )
            time.sleep(retry_delay_seconds)


if __name__ == "__main__":
    sys.exit(main())
