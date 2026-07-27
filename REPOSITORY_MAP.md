# Repository Map

## Назначение
Сервис для автоматического отслеживания входящих сообщений Warframe Market, а также снайпинга лотов (Riven-модов, обычных модов, лицензиатов Кува/Сестер) с уведомлениями в Telegram и управлением через Telegram Mini App.

## Архитектура и компоненты

### `src/market_message/`
- **`config.py`**
  - `Назначение`: Загрузка и валидация конфигурации приложения из переменных окружения.
  - `Точки входа`: `Config.from_env()`
  - `Контракты`: Задает таймауты, интервалы опроса, токены Telegram, учетные данные Warframe Market, `web_app_secret_token` и `WARFRAME_MARKET_MAX_RPS`.
- **`models.py`**
  - `Назначение`: Структуры данных (dataclass) для сообщений, чатов, аукционов и правил снайпера.
  - `Точки входа`: `ChatMessage`, `AuctionItem`, `SniperRule`
- **`state.py`**
  - `Назначение`: SQLite-хранилище обработанных сообщений, просмотренных аукционов и правил снайпинга.
  - `Точки входа`: `StateStore`
  - `Контракты`: Инициализация таблиц, фиксация последней цены лота (`last_price`), повторная проверка при изменении цены, очистка неактивных лотов старше N дней (`cleanup_old_seen_auctions`).
- **`warframe.py`**
  - `Назначение`: Клиент для работы с REST API и WebSocket Warframe Market (аутентификация, чаты, аукционы, справочники Riven v1/v2 и фолбэк-списки).
  - `Точки входа`: `WarframeMarketClient`, `extract_riven_items`, `extract_riven_attributes`, `FALLBACK_RIVEN_ITEMS`, `FALLBACK_RIVEN_ATTRIBUTES`
  - `Контракты`: Использование токенов сессий, поддержка v2 API (`/v2/riven/weapons`, `/v2/riven/attributes`), ограничение частоты запросов (rate limit <= 3 RPS), автоматический retry при HTTP 429, статическая страховка при сбоях API, обработка ошибок авторизации, поиск аукционов по оружию, фильтрам характеристик (`positive_stats`) и сортировке.
- **`telegram.py`**
  - `Назначение`: Клиент Telegram Bot API для отправки уведомлений, обработки reply, вызова Telegram Mini App и валидации `initData`.
  - `Точки входа`: `TelegramClient`, `validate_init_data`, `extract_user_from_init_data`
- **`sniper.py`**
  - `Назначение`: Движок фильтрации и снайпинга лотов по правилам пользователя.
  - `Точки входа`: `RivenSniperEngine`
  - `Контракты`: Ограничение отправки уведомлений за один проход по широким правилам (`MAX_ALERTS_PER_RULE_RUN`), отслеживание снижения цен на ранее найденных лотах, автоматическая очистка устаревших лотов (`SEEN_AUCTION_TTL_DAYS`), сводная сводка в Telegram для защиты от спама, поддержка правил на любое оружие (`*`) через фильтрацию по `positive_stats` или обход доступных оружий.
- **`web.py`**
  - `Назначение`: HTTP-сервер для обработки запросов Telegram Mini App и отдачи статики.
  - `Точки входа`: `run_web_server()`, `WebServer.handle_index`, `WebServer._validate_request_auth`
  - `Контракты`: Строгая авторизация всех API эндпоинтов по подписи `initData` Telegram с проверкой `user.id == TELEGRAM_CHAT_ID` или по `WEB_APP_SECRET_TOKEN`, отдача `index.html` по умолчанию для `/` (без листинга файлов директории).
- **`forwarder.py`**
  - `Назначение`: Связующая логика между Warframe Market и Telegram для пересылки входящих сообщений.
  - `Точки входа`: `MessageForwarder`
- **`__main__.py`**
  - `Назначение`: Точка входа приложения, инициализация клиентов, веб-сервера и фоновых циклов опроса.
  - `Точки входа`: `main()`

### `app/web/`
- **`static/`**
  - `Назначение`: Фронтенд Telegram Mini App (HTML, CSS, JS, Service Worker).
  - `Точки входа`: `app/web/static/index.html`, `app/web/static/app.js`, `app/web/static/style.css`, `app/web/static/service-worker.js`
  - `Контракты`: Поддержка тёмного интерфейса TMA, валидация формы, кастомные дропдауны с текстовым поиском по названию оружия/характеристик (`SearchableSelect`), управление версией SW (`const SW_VERSION = "..."`).

### `ВАЖНОЕ ЗАМЕЧАНИЕ`
при изменении фронтенда (app/web) необходимо инкрементировать версию в index.html 


### `docs/`
- **`deployment.md`**
  - `Назначение`: Подробное руководство по локальному и продакшн запуску сервиса (Docker + Cloudflare Tunnel + Telegram @BotFather).
  - `Точки входа`: `docs/deployment.md`

### `tests/`
- `Назначение`: Юнит- и интеграционные тесты логики снайпинга, граничных условий, TDD-сценариев, веб-сервера, хранилища и форматирования.
- `Точки входа`: `pytest`

