# Warframe Market Telegram Forwarder

Сервис логинится в `warframe.market`, регулярно проверяет входящие сообщения и пересылает новые входящие сообщения в Telegram. Уведомление содержит отправителя, текст сообщения и ссылку для быстрого перехода в чат.

## Как это работает

- Логин: `POST https://api.warframe.market/v1/auth/signin` с email/password и стабильным `device_id`.
- Проверка: `GET https://api.warframe.market/v1/im/chats`.
- Загрузка сообщений: `GET https://api.warframe.market/v1/im/chats/{chat_id}` для чатов с `unread_count > 0`.
- Дедупликация: SQLite хранит уже отправленные `message_id` в `data/state.sqlite`.
- Отправка: Telegram Bot API `sendMessage`.

## Быстрый старт

1. Создайте Telegram-бота через `@BotFather` и получите token.
2. Узнайте `TELEGRAM_CHAT_ID`.
   - Напишите что-нибудь вашему боту.
   - Откройте `https://api.telegram.org/bot<token>/getUpdates`.
   - Возьмите `message.chat.id`.
3. Создайте `.env`:

```bash
cp .env.example .env
```

4. Заполните в `.env`:

```dotenv
WARFRAME_MARKET_EMAIL=your-email@example.com
WARFRAME_MARKET_PASSWORD=your-password
TELEGRAM_BOT_TOKEN=123456789:token
TELEGRAM_CHAT_ID=123456789
```

5. Запустите:

```bash
docker compose up -d --build
```

6. Посмотрите логи:

```bash
docker compose logs -f market-message
```

## Настройки `.env`

| Переменная | Обязательная | По умолчанию | Описание |
| --- | --- | --- | --- |
| `WARFRAME_MARKET_EMAIL` | да | нет | Email аккаунта Warframe Market. Можно использовать `WARFRAME_MARKET_LOGIN`. |
| `WARFRAME_MARKET_PASSWORD` | да | нет | Пароль аккаунта Warframe Market. |
| `TELEGRAM_BOT_TOKEN` | да | нет | Token бота от `@BotFather`. |
| `TELEGRAM_CHAT_ID` | да | нет | ID пользователя, группы или канала для уведомлений. |
| `POLL_INTERVAL_SECONDS` | нет | `30` | Интервал проверки. Минимум 5 секунд. |
| `STATE_PATH` | нет | `data/state.sqlite` | Путь к SQLite-файлу. В Docker используйте `/app/data/state.sqlite`. |
| `WARFRAME_MARKET_PLATFORM` | нет | `pc` | Платформа для заголовков Warframe Market. |
| `WARFRAME_MARKET_LANGUAGE` | нет | `en` | Язык для заголовков Warframe Market. |
| `WARFRAME_MARKET_CROSSPLAY` | нет | `true` | Значение crossplay-заголовка. |

## Сброс состояния

Чтобы сервис снова мог отправить сообщения, которые уже были отмечены как доставленные, остановите контейнер и удалите SQLite-файл:

```bash
docker compose down
rm -f data/state.sqlite
docker compose up -d
```

## Разработка

Локальный запуск тестов:

```bash
pytest -q
```

Локальный запуск без Docker требует установленных зависимостей:

```bash
python -m pip install -e ".[dev]"
python -m market_message
```

## Диагностика

- `Configuration error`: проверьте `.env`, особенно обязательные переменные.
- `Warframe Market login failed`: проверьте логин/пароль, верификацию аккаунта и доступность Warframe Market.
- `Warframe Market session expired`: сервис перелогинится автоматически.
- `Telegram returned ...`: проверьте token, `TELEGRAM_CHAT_ID` и право бота писать в выбранный чат.
- Повторные уведомления после перезапуска обычно означают, что не сохраняется volume `./data:/app/data`.

## Ограничения

Сервис использует текущие приватные endpoints веб-приложения Warframe Market. Если Warframe Market изменит login flow, CSRF, Cloudflare-поведение или формат `/im/chats`, сервис может потребовать обновления.
