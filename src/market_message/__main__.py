import asyncio
import logging
import re
import sys

from .config import Config, ConfigError
from .forwarder import MessageForwarder
from .sniper import RivenSniperEngine
from .state import StateStore
from .telegram import TelegramClient
from .warframe import AuthenticationError, WarframeMarketClient
from .web import WebServer, run_web_server

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


async def async_main() -> int:
    _configure_logging()
    logger = logging.getLogger("market_message")

    try:
        config = Config.from_env()
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    state_path = getattr(config, "state_path", "data/state.sqlite")
    state = StateStore(state_path)
    warframe = WarframeMarketClient(config, device_id=state.get_or_create_device_id())
    telegram = TelegramClient(config)
    forwarder = MessageForwarder(
        warframe=warframe,
        telegram=telegram,
        state=state,
        market_base_url=getattr(config, "market_base_url", "https://warframe.market"),
    )
    sniper = RivenSniperEngine(
        warframe=warframe,
        telegram=telegram,
        state=state,
        market_base_url=getattr(config, "market_base_url", "https://warframe.market"),
        max_alerts_per_rule_run=getattr(config, "max_alerts_per_rule_run", 3),
        seen_auction_ttl_days=getattr(config, "seen_auction_ttl_days", 7),
    )
    web_server = WebServer(
        config=config,
        state=state,
        warframe=warframe,
    )

    loop = asyncio.get_running_loop()
    runner = None

    try:
        await loop.run_in_executor(None, _login_until_success, warframe, getattr(config, "poll_interval_seconds", 30), logger)
        _send_startup_notification(telegram, config, logger)

        web_port = getattr(config, "web_port", 8080)
        runner = await run_web_server(web_server, port=web_port)

        logger.info(
            "Service started. Message poll: %ss | Riven sniper poll: %ss",
            getattr(config, "poll_interval_seconds", 30),
            getattr(config, "riven_poll_interval_seconds", 5),
        )

        async def poll_messages_loop():
            poll_interval = getattr(config, "poll_interval_seconds", 30)
            while True:
                try:
                    sent_count = await loop.run_in_executor(None, forwarder.poll_once)
                    if sent_count:
                        logger.info("Forwarded %s message(s) to Telegram", sent_count)
                    reply_count = await loop.run_in_executor(None, forwarder.forward_replies)
                    if reply_count:
                        logger.info("Sent %s Telegram reply/replies to Warframe Market", reply_count)
                except AuthenticationError:
                    logger.warning("Warframe Market session expired; logging in again")
                    await loop.run_in_executor(None, _login_until_success, warframe, poll_interval, logger)
                except Exception as exc:
                    if isinstance(exc, KeyboardInterrupt):
                        raise
                    logger.exception("Message polling cycle failed; will retry")
                await asyncio.sleep(poll_interval)

        async def poll_riven_loop():
            riven_interval = getattr(config, "riven_poll_interval_seconds", 5)
            while True:
                try:
                    notified_count = await loop.run_in_executor(None, sniper.check_auctions_once)
                    if notified_count:
                        logger.info("Sniper found and notified %s riven auction(s)", notified_count)
                except Exception as exc:
                    if isinstance(exc, KeyboardInterrupt):
                        raise
                    logger.exception("Riven sniper cycle failed; will retry")
                await asyncio.sleep(riven_interval)

        await asyncio.gather(
            poll_messages_loop(),
            poll_riven_loop(),
        )
    except asyncio.CancelledError:
        logger.info("Stopping tasks")
    except KeyboardInterrupt:
        logger.info("Stopping")
    finally:
        if runner is not None:
            await runner.cleanup()
        warframe.close()
        telegram.close()

    return 0


def main() -> int:
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        return 0


def _send_startup_notification(
    telegram: TelegramClient,
    config: Config,
    logger: logging.Logger,
) -> None:
    try:
        web_app_url = getattr(config, "web_app_url", "")
        poll_interval = getattr(config, "poll_interval_seconds", 30)

        if web_app_url:
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🎯 Открыть Снайпер (Mini App)",
                            "web_app": {"url": web_app_url},
                        }
                    ]
                ]
            }
            telegram.send_message(
                "🚀 <b>Warframe Market Forwarder & Riven Sniper запущен</b>\n"
                f"⏱ Сообщения: каждые {poll_interval}с | 🎯 Снайпер: каждые {getattr(config, 'riven_poll_interval_seconds', 5)}с",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        else:
            telegram.send_message(
                f"Warframe Market Telegram forwarder started\nPolling every {poll_interval} seconds"
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
            import time
            time.sleep(retry_delay_seconds)


if __name__ == "__main__":
    sys.exit(main())

