# Repository Map

## Назначение
Сервис для автоматического отслеживания входящих сообщений Warframe Market, а также снайпинга лотов (Riven-модов, Кува Личей, Сестер Парвоса) с уведомлениями в Telegram и управлением через Telegram Mini App.

## Архитектура и компоненты

### `src/market_message/`
- **`config.py`**
  - `Назначение`: Загрузка и валидация конфигурации приложения из переменных окружения.
  - `Точки входа`: `Config.from_env()`
  - `Контракты`: Задает таймауты, интервалы опроса, токены Telegram, учетные данные Warframe Market (`WARFRAME_MARKET_EMAIL`, `WARFRAME_MARKET_PASSWORD` или `WARFRAME_MARKET_JWT_TOKEN`, `WARFRAME_MARKET_CSRF_TOKEN`), `web_app_secret_token`, `WARFRAME_MARKET_MAX_RPS` и `WARFRAME_MARKET_MAX_RPM`.
- **`models.py`**
  - `Назначение`: Структуры данных (dataclass) для сообщений, чатов, аукционов (Riven / Lich / Sister) и правил снайпера.
  - `Точки входа`: `ChatMessage`, `AuctionItem`, `SniperRule`, `RivenItem`
  - `Контракты`: Поддержка специфичных полей для Личей и Сестер (`item_type`, `element`, `damage`, `having_ephemera`, `ephemera`, `quirk`, `min_damage`, `ephemera_filter`) и режима выкупа (`buyout_policy`: `any`, `direct`, `auction`).
- **`state.py`**
  - `Назначение`: SQLite-хранилище обработанных сообщений, просмотренных аукционов и правил снайпинга.
  - `Точки входа`: `StateStore`
  - `Контракты`: Инициализация таблиц, фиксация последней цены лота (`last_price`), повторная проверка при изменении цены, очистка неактивных лотов старше N дней (`cleanup_old_seen_auctions`).
- **`warframe.py`**
  - `Назначение`: Клиент для работы с REST API и WebSocket Warframe Market (аутентификация, чаты, аукционы Riven/Lich/Sister, русские названия и фолбэк-списки).
  - `Точки входа`: `WarframeMarketClient`, `extract_user_id_from_chats`, `get_lich_weapons`, `get_sister_weapons`, `get_items_by_type`, `extract_riven_items`, `extract_riven_attributes`, `FALLBACK_RIVEN_ITEMS`, `FALLBACK_LICH_ITEMS`, `FALLBACK_SISTER_ITEMS`, `WEAPON_RU_NAMES`
  - `Контракты`: Официальная API-авторизация (`POST /auth/signin` с `auth_type: header` на `api.warframe.market`), использование токенов сессий (`JWT` cookie / `WARFRAME_MARKET_JWT_TOKEN`), автополучение первичной сессии из API без парсинга HTML, поддержка v2 API (`/v2/riven/weapons`, `/v2/lich/weapons`, `/v2/sister/weapons`), скользящее ограничение частоты запросов (rate limit <= 3 RPS и <= 10 RPM), автоматический retry при HTTP 429, статическая страховка при сбоях API, поддержка русских названий оружия (`ru_name` / `WEAPON_RU_NAMES`), поиск аукционов по оружию, типу (`riven`, `lich`, `sister`) и специфичным фильтрам.
- **`telegram.py`**
  - `Назначение`: Клиент Telegram Bot API для отправки уведомлений, обработки reply, вызова Telegram Mini App и валидации `initData`.
  - `Точки входа`: `TelegramClient`, `validate_init_data`, `extract_user_from_init_data`
- **`sniper.py`**
  - `Назначение`: Движок фильтрации и снайпинга лотов (Riven, Кува Личей, Сестер Парвоса) по правилам пользователя.
  - `Точки входа`: `RivenSniperEngine`, `matches_rule`, `format_riven_notification`
  - `Контракты`: Ограничение отправки уведомлений за один проход по широким правилам (`MAX_ALERTS_PER_RULE_RUN`), отслеживание снижения цен на ранее найденных лотах, автоматическая очистка устаревших лотов (`SEEN_AUCTION_TTL_DAYS`), специализированное форматирование Telegram-уведомлений для Riven (с выводом полного названия оружия и мода, например "Sobek Manti-Gelimag") и Lich/Sister с использованием inline-тегов `<code>` без `<pre>` для поддержки копирования шёпота по тапу на Android/iOS, поддержка фильтрации лотов по типу выкупа (`buyout_policy`), полное отключение поиска по "любому оружию" (`*`) для предотвращения исчерпания API rate limit (429 Too Many Requests).
- **`web.py`**
  - `Назначение`: HTTP-сервер для обработки запросов Telegram Mini App и отдачи статики.
  - `Точки входа`: `run_web_server()`, `WebServer.handle_index`, `WebServer.handle_riven_meta`, `WebServer._validate_request_auth`
  - `Контракты`: Строгая авторизация всех API эндпоинтов по подписи `initData` Telegram с проверкой `user.id == TELEGRAM_CHAT_ID` или по `WEB_APP_SECRET_TOKEN`, отдаче метаданных по типу `?type=riven|kuva_lich|sister_of_parvos`, валидация правил с отклонением создания/изменения правил с невыбранным или 'любым' оружием (`*`), отдача `index.html` по умолчанию для `/`.
- **`forwarder.py`**
  - `Назначение`: Связующая логика между Warframe Market и Telegram для пересылки входящих сообщений.
  - `Точки входа`: `MessageForwarder`
- **`__main__.py`**
  - `Назначение`: Точка входа приложения, инициализация клиентов, веб-сервера и фоновых циклов опроса.
  - `Точки входа`: `main()`, `_notify_jwt_expiration_if_needed`
  - `Контракты`: Однократная отправка уведомления в Telegram при протухании JWT токена (`WARFRAME_MARKET_JWT_TOKEN`), взятого из конфигурации, а не полученного автоматически по логину/паролю.

### `app/web/`
- **`static/`**
  - `Назначение`: Фронтенд Telegram Mini App (HTML, CSS, JS, Service Worker).
  - `Точки входа`: `app/web/static/index.html`, `app/web/static/app.js`, `app/web/static/style.css`, `app/web/static/service-worker.js`
  - `Контракты`: Поддержка тёмного интерфейса TMA, выбор типа правила (`riven`, `kuva_lich`, `sister_of_parvos`), динамическое переключение формы (скрытие Riven-полей и показ фильтров стихии, урона, эфемеры, причуд), выбор режима выкупа (все лоты / исключить аукционы / только аукционы), кастомные дропдауны с текстовым поиском по английскому и русскому названию оружия/характеристик (`SearchableSelect`), управление версией SW (`const SW_VERSION = "edcsod-pwa-v10"`).

### `ВАЖНОЕ ЗАМЕЧАНИЕ`
при изменении фронтенда (app/web) необходимо инкрементировать версию в index.html и service-worker.js

### `docs/`
- **`deployment.md`**
  - `Назначение`: Подробное руководство по локальному и продакшн запуску сервиса (Docker + Cloudflare Tunnel + Telegram @BotFather).
  - `Точки входа`: `docs/deployment.md`

### `tests/`
- `Назначение`: Юнит- и интеграционные тесты логики снайпинга Riven/Lich/Sister, граничных условий, TDD-сценариев, веб-сервера, хранилища и форматирования.
- `Точки входа`: `pytest`


