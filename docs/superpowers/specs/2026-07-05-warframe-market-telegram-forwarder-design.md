# Warframe Market Telegram Forwarder Design

## Goal

Build a Docker Compose packaged service that logs in to Warframe Market with credentials from `.env`, regularly checks incoming chat messages, and forwards new incoming messages to Telegram with a direct chat link.

## Architecture

The service is a small Python worker. It uses a persistent HTTP session to log in to Warframe Market, polls the private chat endpoints on a configurable interval, and sends notifications through the Telegram Bot API. SQLite stores delivered message IDs and the generated Warframe Market device ID, so restarts do not duplicate notifications.

## Components

- `Config`: reads required environment variables and applies safe defaults.
- `WarframeMarketClient`: fetches the CSRF token from the site, signs in through the v1 API, lists chats, and fetches chat messages.
- `TelegramClient`: sends plain-text Telegram messages.
- `StateStore`: stores sent Warframe Market message IDs and service metadata in SQLite.
- `MessageForwarder`: extracts incoming unread messages, formats Telegram text, forwards them, and marks them sent only after Telegram accepts the message.
- `main`: owns the login and polling loop, including retry after transient failures.

## Data Flow

1. The worker loads `.env` through Docker Compose environment injection.
2. The worker fetches Warframe Market HTML to obtain a CSRF token and cookies.
3. The worker posts `email`, `password`, and a stable `device_id` to `/auth/signin`.
4. Every `POLL_INTERVAL_SECONDS`, the worker calls `/im/chats`.
5. Chats with `unread_count > 0` are fetched through `/im/chats/{chat_id}`.
6. Incoming messages not present in SQLite are sent to Telegram.
7. A message is inserted into SQLite only after Telegram returns success.

## Error Handling

401 or 403 from Warframe Market forces a fresh login. Other Warframe Market and Telegram failures are logged and retried on the next polling cycle. Failed Telegram deliveries are not marked sent, so they can be retried.

## Testing

Unit tests cover environment parsing, message extraction from API payloads, HTML stripping and Telegram formatting, SQLite deduplication, and the forwarder behavior that sends only incoming unread messages and records them after success.
