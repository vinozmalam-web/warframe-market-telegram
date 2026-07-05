from __future__ import annotations

import logging
import sys
import time

from .config import Config, ConfigError
from .forwarder import MessageForwarder
from .state import StateStore
from .telegram import TelegramClient
from .warframe import AuthenticationError, WarframeMarketClient


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
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
        logger.info("Polling every %s seconds", config.poll_interval_seconds)
        while True:
            try:
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
