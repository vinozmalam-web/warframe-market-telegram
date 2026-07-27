# Инструкция по запуску и развертыванию Warframe Market Sniper

Данный документ описывает процессы локальной разработки (Local Setup) и развертывания в продакшн (Production Setup) через Docker и Cloudflare Tunnel.

---

## 1. Локальный запуск (Local Development)

### 1.1 Требования
- Python 3.12+
- Виртуальное окружение `.venv`
- Учетная запись на [Warframe Market](https://warframe.market)
- Токен бота Telegram от [@BotFather](https://t.me/BotFather)

### 1.2 Шаги настройки

1. **Создание и активация venv**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

2. **Создание конфигурационного файла `.env`**:
   Скопируйте пример конфигурации:
   ```bash
   cp .env.example .env
   ```
   Заполните переменные окружения в `.env`:
   ```env
   WARFRAME_MARKET_EMAIL=your_email@example.com
   WARFRAME_MARKET_PASSWORD=your_password
   TELEGRAM_BOT_TOKEN=123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
   TELEGRAM_CHAT_ID=987654321
   POLL_INTERVAL_SECONDS=30
   RIVEN_POLL_INTERVAL_SECONDS=5
   WEB_PORT=8080
   WEB_APP_URL=https://<your-tunnel-subdomain>.trycloudflare.com
   ```

3. **Локальный проброс HTTPS для Telegram Mini App (TMA)**:
   Telegram требует, чтобы Web App открывался строго по **HTTPS**. Для локального тестирования запустите туннель Cloudflare или ngrok:
   ```bash
   # Альтернатива 1: Cloudflare Tunnel (без регистрации)
   npx cloudflared tunnel --url http://localhost:8080

   # Альтернатива 2: ngrok
   ngrok http 8080
   ```
   Скопируйте полученный HTTPS URL и укажите его в `WEB_APP_URL` в файле `.env`.

4. **Запуск приложения**:
   ```bash
   source .venv/bin/activate
   python -m market_message
   ```
   После запуска в бот придет стартовое сообщение с кнопкой **"🎯 Открыть Снайпер (Mini App)"**.

---

## 2. Продакшн запуск (Production Setup via Docker & Cloudflare Tunnel)

### 2.1 Подготовка окружения
На сервере Linux установлены Docker и Docker Compose.

### 2.2 Получение адреса `WEB_APP_URL` в Cloudflare

 Telegram Mini App требует постоянный **HTTPS** адрес. В Cloudflare его можно получить двумя способами:

#### Вариант А: Если у вас есть свой домен на Cloudflare (Рекомендуется для продакшна)

1. Зайдите в [Cloudflare Dashboard](https://dash.cloudflare.com/) и перейдите в раздел **Networks** -> **Tunnels** (или через [Cloudflare Zero Trust](https://one.dash.cloudflare.com/)).
2. Нажмите **Add a Tunnel** -> выберите **Cloudflared** -> введите имя (например `wf-market-sniper`).
3. Скопируйте токен установки для вашего сервера (например `cloudflared service install eyJh...`).
4. В разделе **Public Hostname** добавьте новую запись:
   - **Subdomain**: `wf-sniper` (или любой другой, например `sniper`).
   - **Domain**: `yourdomain.com` (ваш домен в Cloudflare).
   - **Type**: `HTTP`
   - **URL**: `market-message:8080` (если запускаете контейнер `cloudflared` рядом в Docker Compose) или `localhost:8080` (если `cloudflared` установлен на самом сервере).
5. **Ваш `WEB_APP_URL` для `.env`**:
   `WEB_APP_URL=https://wf-sniper.yourdomain.com`

#### Вариант Б: Без своего домена (Использование беcплатного авто-домена Cloudflare)

Если собственного домена нет, вы можете запустить `cloudflared` через Docker Compose в режиме бесплатного туннеля (`trycloudflare.com`):

1. В `docker-compose.yml` добавьте сервис `cloudflared`:
   ```yaml
   cloudflared:
     image: cloudflare/cloudflared:latest
     command: tunnel --no-autoupdate run --url http://market-message:8080
     restart: unless-stopped
   ```
2. При старте контейнера в логах `docker compose logs cloudflared` отобразится сгенерированная ссылка:
   `https://random-words.trycloudflare.com`
3. Скопируйте эту ссылку в `.env` в параметр `WEB_APP_URL`.

### 2.3 Запуск через Docker Compose

1. Клонируйте репозиторий на сервер и создайте `.env`:
   ```bash
   cp .env.example .env
   nano .env
   ```
2. Укажите ваши боевые данные и токен туннеля Cloudflare:
   ```env
   WARFRAME_MARKET_EMAIL=seller@example.com
   WARFRAME_MARKET_PASSWORD=strong_password
   TELEGRAM_BOT_TOKEN=123456789:AA...
   TELEGRAM_CHAT_ID=123456789
   WEB_APP_URL=https://wf-sniper.yourdomain.com
   TUNNEL_TOKEN=eyJh...
   ```
3. Запустите контейнеры в фоновом режиме:
   ```bash
   docker compose up -d --build
   ```
4. Проверьте статус и логи приложения:
   ```bash
   docker compose logs -f market-message
   ```

---

## 3. Настройка кнопки Mini App в Telegram через @BotFather

Чтобы открывать веб-интерфейс прямо из меню бота Telegram:
1. Перейдите в чат с [@BotFather](https://t.me/BotFather).
2. Отправьте команду `/mybots` и выберите вашего бота.
3. Перейдите в **Bot Settings** -> **Menu Button** -> **Configure menu button**.
4. Отправьте URL вашего веб-приложения (`WEB_APP_URL`) и название кнопки, например: `🎯 Снайпер Riven`.

---

## 4. Защита и ограничение доступа к WEB_APP_URL

Веб-приложение по умолчанию **строго ограничено** и доступно **только владельцу**:

1. **Доступ через Telegram Mini App (Автоматический)**:
   При открытии кнопки в Telegram приложение автоматически передает `initData`. Сервер криптографически проверяет подпись токеном бота (`TELEGRAM_BOT_TOKEN`) и проверяет, совпадает ли ID пользователя Telegram с настроенным `TELEGRAM_CHAT_ID`. Если ссылку откроет любой другой человек, он увидит заблокированный экран `401 Unauthorized` и не получит доступ к правилам.

2. **Доступ из обычного браузера ПК (По секретному токену)**:
   Если вы хотите открывать `WEB_APP_URL` из любого обычного браузера (например Chrome на компьютере), задайте секретную переменную в `.env`:
   ```env
   WEB_APP_SECRET_TOKEN=ваш_секретный_токен_123
   ```
   В браузере вы сможете либо ввести этот токен в поле на заблокированном экране, либо открыть ссылку вида `https://your-domain.com/?token=ваш_секретный_токен_123`.
